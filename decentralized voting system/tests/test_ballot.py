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


def test_ballot_proposal_binding_replay_defense():
    """
    CRITICAL SECURITY TEST:
    Ensures that a ballot digitally signed for Proposal A cannot be replayed on Proposal B.
    """
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)

    # Legitimate ballot signed for PROP-A
    ballot_a = Ballot(voter_id=voter_id, proposal_id="PROP-A", choice="YES", weight=1)
    sig = sign_message(priv, ballot_a.get_digest())
    ballot_a.signature = sig.hex()
    assert ballot_a.verify() is True

    # Attacker tries to replay signature on PROP-B
    replayed_ballot = Ballot(voter_id=voter_id, proposal_id="PROP-B", choice="YES", weight=1, signature=ballot_a.signature)
    assert replayed_ballot.verify() is False, "Security failure: signature replayed across proposals!"


def test_ballot_invalid_weight():
    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)

    zero_weight = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES", weight=0)
    sig = sign_message(priv, zero_weight.get_digest())
    zero_weight.signature = sig.hex()
    assert zero_weight.verify() is False

    neg_weight = Ballot(voter_id=voter_id, proposal_id="PROP-1", choice="YES", weight=-5)
    sig2 = sign_message(priv, neg_weight.get_digest())
    neg_weight.signature = sig2.hex()
    assert neg_weight.verify() is False
