import json
import sqlite3
import threading
import urllib.request
from pathlib import Path

import pytest

from openballot.ballot import Ballot
from openballot.block import Block
from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ledger import Ledger
from openballot.node import NodeHandler, NodeServer
from openballot.storage import SQLiteStorage


def _signed_ballot(private_key, voter_id, proposal_id="PROP-PERSIST", choice="YES"):
    ballot = Ballot(voter_id, proposal_id, choice)
    ballot.signature = sign_message(private_key, ballot.get_digest()).hex()
    return ballot


def test_sqlite_storage_basic(tmp_path):
    db_file = tmp_path / "basic.db"
    storage = SQLiteStorage(db_file)

    genesis = Block(index=0, prev_hash="0" * 64, ballots=[])
    genesis.mine(difficulty=1)
    storage.save_block(genesis)

    assert storage.count_blocks() == 1
    loaded = storage.load_chain()
    assert len(loaded) == 1
    assert loaded[0].index == 0
    assert loaded[0].hash == genesis.hash


def test_node_restart_persistence(tmp_path):
    db_file = tmp_path / "node_restart.db"
    storage1 = SQLiteStorage(db_file)

    # 1. Start initial node instance
    ledger1 = Ledger(open_election=True)
    server1 = NodeServer(
        ("127.0.0.1", 0),
        NodeHandler,
        ledger=ledger1,
        difficulty=1,
        storage=storage1,
        allow_private_peers=True
    )
    thread1 = threading.Thread(target=server1.serve_forever, daemon=True)
    thread1.start()
    base_url1 = f"http://127.0.0.1:{server1.server_port}"

    try:
        priv, pub = generate_keypair()
        voter_id = public_key_to_hex(pub)
        ballot = _signed_ballot(priv, voter_id, proposal_id="PROP-RESTART", choice="YES")

        # Cast ballot
        req = urllib.request.Request(
            f"{base_url1}/api/v1/ballots",
            data=json.dumps(ballot.to_dict()).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 202

        # Mine block
        mine_req = urllib.request.Request(
            f"{base_url1}/api/v1/mine",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(mine_req) as resp:
            assert resp.status == 200

        assert len(ledger1.chain) == 2
        assert ledger1.tally("PROP-RESTART") == {"YES": 1}
        original_block_hash = ledger1.chain[1].hash
    finally:
        server1.shutdown()
        server1.server_close()
        thread1.join(timeout=2)

    # 2. Restart node from same storage and verify state is restored
    storage2 = SQLiteStorage(db_file)
    ledger2 = Ledger(open_election=True)
    server2 = NodeServer(
        ("127.0.0.1", 0),
        NodeHandler,
        ledger=ledger2,
        difficulty=1,
        storage=storage2,
        allow_private_peers=True
    )
    thread2 = threading.Thread(target=server2.serve_forever, daemon=True)
    thread2.start()
    base_url2 = f"http://127.0.0.1:{server2.server_port}"

    try:
        assert len(ledger2.chain) == 2
        assert ledger2.chain[1].hash == original_block_hash
        assert ledger2.tally("PROP-RESTART") == {"YES": 1}
        assert ledger2.has_voted("PROP-RESTART", voter_id) is True

        # Query /api/v1/chain from restarted node
        req_chain = urllib.request.Request(f"{base_url2}/api/v1/chain")
        with urllib.request.urlopen(req_chain) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            assert data["length"] == 2
            assert data["chain"][1]["hash"] == original_block_hash
    finally:
        server2.shutdown()
        server2.server_close()
        thread2.join(timeout=2)


def test_node_refuses_to_start_on_corrupt_chain(tmp_path):
    db_file = tmp_path / "corrupt.db"
    storage = SQLiteStorage(db_file)

    # 1. Start node and mine a block
    ledger = Ledger(open_election=True)
    server = NodeServer(
        ("127.0.0.1", 0),
        NodeHandler,
        ledger=ledger,
        difficulty=1,
        storage=storage
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        priv, pub = generate_keypair()
        voter_id = public_key_to_hex(pub)
        ballot = _signed_ballot(priv, voter_id, proposal_id="PROP-CORRUPT")
        req = urllib.request.Request(
            f"{base_url}/api/v1/ballots",
            data=json.dumps(ballot.to_dict()).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req)

        mine_req = urllib.request.Request(
            f"{base_url}/api/v1/mine",
            data=b"{}",
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(mine_req)
        assert len(ledger.chain) == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    # 2. Corrupt block #1 in SQLite database
    with sqlite3.connect(str(db_file)) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE blocks SET prev_hash = 'corrupted_prev_hash' WHERE block_index = 1")
        conn.commit()

    # 3. Attempt to start new node from corrupted storage; must refuse to start
    corrupt_storage = SQLiteStorage(db_file)
    corrupt_ledger = Ledger(open_election=True)
    with pytest.raises(ValueError, match="failed integrity validation"):
        NodeServer(
            ("127.0.0.1", 0),
            NodeHandler,
            ledger=corrupt_ledger,
            difficulty=1,
            storage=corrupt_storage
        )
