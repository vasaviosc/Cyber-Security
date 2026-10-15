from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ballot import Ballot


def test_ballot_valid_signature():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ballot = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES")

    sig = sign_message(priv, ballot.get_digest())
    ballot.signature = sig.hex()

    assert ballot.verify() is True


def test_ballot_signature_is_bound_to_proposal():
    priv, pub = generate_keypair()
    ballot = Ballot(
        voter_id=public_key_to_hex(pub),
        proposal_id="PROP-1",
        choice="YES",
        weight=2,
    )
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()
    assert ballot.verify() is True

    ballot.proposal_id = "PROP-2"
    assert ballot.verify() is False


def test_ballot_signature_is_bound_to_voter_choice_and_weight():
    priv, pub = generate_keypair()
    _, other_pub = generate_keypair()
    ballot = Ballot(
        voter_id=public_key_to_hex(pub),
        proposal_id="PROP-1",
        choice="YES",
        weight=2,
    )
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()

    ballot.voter_id = public_key_to_hex(other_pub)
    assert ballot.verify() is False

    ballot.voter_id = public_key_to_hex(pub)
    ballot.choice = "NO"
    assert ballot.verify() is False

    ballot.choice = "YES"
    ballot.weight = 3
    assert ballot.verify() is False


def test_ballot_invalid_signature():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ballot = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES")

    # Set bad signature
    ballot.signature = "deadbeef" * 8
    assert ballot.verify() is False


def test_ballot_serialization():
    priv, pub = generate_keypair()
    ballot = Ballot(
        voter_id=public_key_to_hex(pub),
        proposal_id="PROP-1",
        choice="NO",
        weight=2,
    )
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()
    data = ballot.to_dict()
    recovered = Ballot.from_dict(data)

    assert recovered.verify() is True
    assert recovered.voter_id == ballot.voter_id
    assert recovered.proposal_id == ballot.proposal_id
    assert recovered.choice == ballot.choice
    assert recovered.weight == ballot.weight
    assert recovered.signature == ballot.signature


def test_ballot_cross_proposal_replay_rejected():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ballot1 = Ballot(voter_id=voter_id, proposal_id="PROP-LEGAL", choice="YES")
    sig = sign_message(priv, ballot1.get_digest())
    ballot1.signature = sig.hex()
    assert ballot1.verify() is True

    # Attempt replay with different proposal
    ballot2 = Ballot(voter_id=voter_id, proposal_id="PROP-MALICIOUS", choice="YES", signature=ballot1.signature)
    assert ballot2.verify() is False


def test_ballot_invalid_weight_rejected():
    import pytest
    with pytest.raises(ValueError):
        Ballot(voter_id="abc", proposal_id="PROP-1", choice="YES", weight=0)

    with pytest.raises(ValueError):
        Ballot(voter_id="abc", proposal_id="PROP-1", choice="YES", weight=-5)

    with pytest.raises(ValueError):
        Ballot(voter_id="abc", proposal_id="PROP-1", choice="YES", weight=999)


def test_shared_test_vector_python_and_javascript():
    import subprocess
    from pathlib import Path
    from openballot.crypto import private_key_from_hex, public_key_to_hex, sign_message

    secret_key_hex = "11" * 32
    priv = private_key_from_hex(secret_key_hex)
    voter_id = public_key_to_hex(priv.public_key())
    proposal_id = "PROP-2026-TEST"
    choice = "YES"
    weight = 1

    ballot = Ballot(voter_id=voter_id, proposal_id=proposal_id, choice=choice, weight=weight)
    digest = ballot.get_digest()
    sig = sign_message(priv, digest)

    expected_voter_id = "d04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737"
    expected_digest = "3f4df2f99f892e01cfcefa9dfade481f35518d41f85e1484384e813b31a5f7a9"
    expected_sig = "905abc13a792f817dc599eeee510198f9bbc949c292396a70160cb42fa207bdfbb21581a5aea809a440c1afe6c17ecc76aee0bd2d093b999d91a2d8ea7ed0f06"

    assert voter_id == expected_voter_id
    assert digest.hex() == expected_digest
    assert sig.hex() == expected_sig

    ballot.signature = sig.hex()
    assert ballot.verify() is True

    # Run the JavaScript test check
    js_test = Path(__file__).parent / "test_vector.js"
    res = subprocess.run(["node", str(js_test)], capture_output=True, text=True, check=True)
    assert "PASSED in JavaScript" in res.stdout

