import os
import json
import tempfile
from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ballot import Ballot
from openballot.block import Block
from openballot.mempool import Mempool
from openballot.ledger import Ledger


def test_mempool_duplicate_prevention():
    mempool = Mempool()
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)

    b1 = Ballot(voter_id=voter_id, proposal_id="PROP-100", choice="YES")
    b1.signature = sign_message(priv, b1.get_digest()).hex()

    added_first = mempool.add(b1)
    assert added_first is True
    assert mempool.has_voter_submitted("PROP-100", voter_id) is True

    # Try submitting second ballot for same proposal & voter
    b2 = Ballot(voter_id=voter_id, proposal_id="PROP-100", choice="NO")
    b2.signature = sign_message(priv, b2.get_digest()).hex()

    added_second = mempool.add(b2)
    assert added_second is False
    assert mempool.size() == 1


def test_ledger_persistence():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        db_path = tmp.name

    try:
        ledger1 = Ledger(storage_path=db_path)
        ledger1.create_genesis_block()
        ledger1.register_voter("voter1_hex")

        priv, pub = generate_keypair()
        voter_id = public_key_to_hex(pub)
        ledger1.register_voter(voter_id)

        b = Ballot(voter_id=voter_id, proposal_id="PROP-GOV-1", choice="YES")
        b.signature = sign_message(priv, b.get_digest()).hex()

        blk = Block(index=1, prev_hash=ledger1.latest_block.hash, ballots=[b])
        blk.mine(difficulty=1)
        ledger1.chain.append(blk)
        ledger1.save_to_file()

        # Reload ledger from file
        ledger2 = Ledger.load_from_file(db_path)
        assert len(ledger2.chain) == 2
        assert ledger2.is_registered("voter1_hex") is True
        assert ledger2.is_registered(voter_id) is True
        assert ledger2.has_voted("PROP-GOV-1", voter_id) is True
        assert ledger2.tally("PROP-GOV-1") == {"YES": 1}

        vote_info = ledger2.get_vote("PROP-GOV-1", voter_id)
        assert vote_info is not None
        assert vote_info["choice"] == "YES"
        assert vote_info["block_index"] == 1

        proposals = ledger2.get_proposals()
        assert len(proposals) == 1
        assert proposals[0]["proposal_id"] == "PROP-GOV-1"
        assert proposals[0]["total_ballots"] == 1
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_voter_registry_file_loading():
    voter_data = {
        "alice": {"voter_id": "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"},
        "bob": {"voter_id": "ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100"}
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(voter_data, tmp)
        file_path = tmp.name

    try:
        ledger = Ledger()
        ledger.load_voter_registry_file(file_path)
        assert len(ledger.voter_registry) == 2
        assert ledger.is_registered("00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff") is True
        assert ledger.is_registered("ffeeddccbbaa99887766554433221100ffeeddccbbaa99887766554433221100") is True
        assert ledger.is_registered("unknown_voter") is False
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
