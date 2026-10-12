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
