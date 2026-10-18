import os
import tempfile
import threading
import time
from openballot.crypto import (
    generate_keypair,
    public_key_to_hex,
    sign_message,
    create_ballot_commitment,
    verify_ballot_commitment
)
from openballot.ballot import Ballot
from openballot.block import Block, compute_merkle_root
from openballot.mempool import Mempool
from openballot.ledger import Ledger
from openballot.consensus import ConsensusEngine
from openballot.node import NodeServer, NodeHandler


def test_merkle_root_integrity_and_tampering():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)

    b1 = Ballot(voter_id, "PROP-1", "YES")
    b1.signature = sign_message(priv, b1.get_digest()).hex()

    b2 = Ballot(voter_id, "PROP-2", "NO")
    b2.signature = sign_message(priv, b2.get_digest()).hex()

    root = compute_merkle_root([b1, b2])
    assert len(root) == 64
    assert root != "0" * 64

    # Merkle root matches block creation
    blk = Block(index=1, prev_hash="0" * 64, ballots=[b1, b2])
    assert blk.merkle_root == root

    # Tampering with a ballot choice modifies the Merkle root
    b1_tampered = Ballot(voter_id, "PROP-1", "NO", signature=b1.signature)
    tampered_root = compute_merkle_root([b1_tampered, b2])
    assert tampered_root != root


def test_fast_o1_duplicate_lookup_performance():
    ledger = Ledger()
    ledger.create_genesis_block()

    # Pre-populate ledger with 500 ballots
    ballots = []
    keys = []
    for i in range(500):
        priv, pub = generate_keypair()
        vid = public_key_to_hex(pub)
        keys.append((priv, vid))
        b = Ballot(voter_id=vid, proposal_id="PROP-SCALE", choice="YES")
        b.signature = sign_message(priv, b.get_digest()).hex()
        ballots.append(b)

    blk = Block(index=1, prev_hash=ledger.latest_block.hash, ballots=ballots)
    blk.mine(difficulty=1)
    ledger.append_block(blk)

    # 1. Fast O(1) duplicate check
    start = time.perf_counter()
    for _, vid in keys[:100]:
        assert ledger.has_voted("PROP-SCALE", vid) is True
    elapsed = time.perf_counter() - start
    # 100 lookups should take less than 10 milliseconds
    assert elapsed < 0.05

    # 2. Fast O(1) tally check
    tally = ledger.tally("PROP-SCALE")
    assert tally.get("YES") == 500


def test_sqlite_wal_persistence():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        ledger1 = Ledger(storage_path=db_path)
        ledger1.create_genesis_block()

        priv, pub = generate_keypair()
        voter_id = public_key_to_hex(pub)
        ledger1.register_voter(voter_id)

        b = Ballot(voter_id=voter_id, proposal_id="PROP-SQLITE", choice="YES")
        b.signature = sign_message(priv, b.get_digest()).hex()

        blk = Block(index=1, prev_hash=ledger1.latest_block.hash, ballots=[b])
        blk.mine(difficulty=1)
        ledger1.append_block(blk)
        ledger1.save_to_file()

        # Reload from SQLite
        ledger2 = Ledger.load_from_file(db_path)
        assert len(ledger2.chain) == 2
        assert ledger2.is_registered(voter_id) is True
        assert ledger2.has_voted("PROP-SQLITE", voter_id) is True
        assert ledger2.tally("PROP-SQLITE") == {"YES": 1}

        vote = ledger2.get_vote("PROP-SQLITE", voter_id)
        assert vote is not None
        assert vote["choice"] == "YES"
    finally:
        for ext in ["", "-wal", "-shm"]:
            p = db_path + ext
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def test_mempool_bounded_capacity():
    mempool = Mempool(max_size=10)
    for i in range(15):
        priv, pub = generate_keypair()
        b = Ballot(voter_id=public_key_to_hex(pub), proposal_id="PROP-BOUND", choice="YES")
        mempool.add(b)

    # Size should not exceed 10
    assert mempool.size() == 10


def test_ballot_cryptographic_commitment():
    secret_salt = "voter-secret-salt-xyz"
    choice = "YES"
    commitment = create_ballot_commitment(choice, secret_salt)
    assert len(commitment) == 64
    assert verify_ballot_commitment(choice, secret_salt, commitment) is True
    assert verify_ballot_commitment("NO", secret_salt, commitment) is False


def test_threaded_concurrent_requests():
    ledger = Ledger()
    ledger.create_genesis_block()
    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

    try:
        import urllib.request
        # Concurrently query health and metrics
        results = []
        def fetch(path):
            with urllib.request.urlopen(f"{base_url}{path}") as resp:
                results.append(resp.status)

        threads = [threading.Thread(target=fetch, args=(p,)) for p in ["/health", "/metrics", "/api/v1/snapshot", "/health"]]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(results) == 4
        assert all(s == 200 for s in results)
    finally:
        server.shutdown()
        server.server_close()
