from openballot.ballot import Ballot
from openballot.block import Block
from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ledger import Ledger
from openballot.consensus import ConsensusEngine


def _signed_ballot(proposal_id="PROP-1"):
    private_key, public_key = generate_keypair()
    ballot = Ballot(public_key_to_hex(public_key), proposal_id, "YES")
    ballot.signature = sign_message(private_key, ballot.get_digest()).hex()
    return ballot


def test_chain_validation_valid():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)

    b1 = Block(index=1, prev_hash=ledger.chain[0].hash, ballots=[])
    b1.mine(difficulty=1)
    ledger.chain.append(b1)

    assert engine.is_valid_chain(ledger.chain) is True


def test_chain_validation_broken_link():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)

    b1 = Block(index=1, prev_hash="bad_previous_hash" + "0" * 47, ballots=[])
    b1.mine(difficulty=1)
    ledger.chain.append(b1)

    assert engine.is_valid_chain(ledger.chain) is False


def test_chain_validation_rejects_untrusted_genesis_and_unsigned_genesis_ballot():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)

    altered_genesis = Block(
        index=0,
        prev_hash="untrusted",
        ballots=[Ballot("attacker", "PROP-1", "YES", weight=50)],
        timestamp=1700000001.0,
    )
    block1 = Block(index=1, prev_hash=altered_genesis.hash, ballots=[])
    block1.mine(difficulty=1)
    block2 = Block(index=2, prev_hash=block1.hash, ballots=[])
    block2.mine(difficulty=1)
    candidate = [altered_genesis, block1, block2]

    assert engine.is_valid_chain(candidate) is False
    assert engine.resolve_conflicts([candidate]) is False
    assert ledger.tally("PROP-1") == {}


def test_chain_validation_rejects_nonsequential_block_indices():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)

    block1 = Block(index=7, prev_hash=ledger.chain[0].hash, ballots=[])
    block1.mine(difficulty=1)
    candidate = [ledger.chain[0], block1]

    assert engine.is_valid_chain(candidate) is False


def test_chain_validation_rejects_duplicate_ballots():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)
    ballot = _signed_ballot()

    block1 = Block(index=1, prev_hash=ledger.chain[0].hash, ballots=[ballot])
    block1.mine(difficulty=1)
    block2 = Block(index=2, prev_hash=block1.hash, ballots=[ballot])
    block2.mine(difficulty=1)

    assert engine.is_valid_chain([ledger.chain[0], block1, block2]) is False


def test_chain_validation_rejects_invalid_ballot_signature():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)
    ballot = _signed_ballot()
    ballot.choice = "NO"

    block1 = Block(index=1, prev_hash=ledger.chain[0].hash, ballots=[ballot])
    block1.mine(difficulty=1)

    assert engine.is_valid_chain([ledger.chain[0], block1]) is False


def test_chain_validation_rejects_corrupted_block_hash():
    ledger = Ledger()
    ledger.create_genesis_block()
    engine = ConsensusEngine(ledger=ledger, difficulty=1)
    block1 = Block(index=1, prev_hash=ledger.chain[0].hash, ballots=[])
    block1.mine(difficulty=1)
    block1.hash = "f" * 64

    assert engine.is_valid_chain([ledger.chain[0], block1]) is False


def test_conflict_resolution_honest_fork():
    ledger_a = Ledger()
    ledger_a.create_genesis_block()
    engine_a = ConsensusEngine(ledger=ledger_a, difficulty=1)

    # Node B builds 2 blocks from the same genesis
    ledger_b = Ledger()
    genesis_b = Block.from_dict(ledger_a.chain[0].to_dict())
    ledger_b.chain = [genesis_b]

    b1 = Block(index=1, prev_hash=genesis_b.hash, ballots=[])
    b1.mine(difficulty=1)
    ledger_b.chain.append(b1)

    b2 = Block(index=2, prev_hash=b1.hash, ballots=[])
    b2.mine(difficulty=1)
    ledger_b.chain.append(b2)

    # Node A syncs with Node B's longer chain
    result = engine_a.resolve_conflicts([ledger_b.chain])
    assert result is True
    assert len(ledger_a.chain) == 3
