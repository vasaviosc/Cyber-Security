from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ballot import Ballot


def test_ballot_valid_signature():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ballot = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES")

    sig = sign_message(priv, ballot.get_digest())
    ballot.signature = sig.hex()

    assert ballot.verify() is True


def test_ballot_invalid_signature():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ballot = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES")

    # Set bad signature
    ballot.signature = "deadbeef" * 8
    assert ballot.verify() is False


def test_ballot_serialization():
    ballot = Ballot(voter_id="abc", proposal_id="PROP-1", choice="NO", signature="1234")
    data = ballot.to_dict()
    recovered = Ballot.from_dict(data)

    assert recovered.voter_id == ballot.voter_id
    assert recovered.proposal_id == ballot.proposal_id
    assert recovered.choice == ballot.choice
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
