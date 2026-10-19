from openballot.ballot import Ballot
from openballot.mempool import Mempool


def test_mempool_duplicate_rejection():
    """
    CRITICAL SECURITY TEST:
    Mempool must reject duplicate submissions from the same voter on the same proposal.
    """
    pool = Mempool()
    b1 = Ballot(voter_id="VOTER-123", proposal_id="PROP-1", choice="YES", signature="sig1")
    b2 = Ballot(voter_id="VOTER-123", proposal_id="PROP-1", choice="NO", signature="sig2")

    # First submission should be accepted
    assert pool.add(b1) is True
    assert pool.size() == 1
    assert pool.has_ballot("PROP-1", "VOTER-123") is True
    assert pool.has_ballot("PROP-1", "voter-123") is True  # case-insensitive

    # Duplicate submission from same voter for same proposal must be rejected!
    assert pool.add(b2) is False
    assert pool.size() == 1, "Duplicate ballot was improperly accepted into mempool!"


def test_mempool_different_proposals():
    pool = Mempool()
    b1 = Ballot(voter_id="VOTER-123", proposal_id="PROP-A", choice="YES", signature="sig1")
    b2 = Ballot(voter_id="VOTER-123", proposal_id="PROP-B", choice="YES", signature="sig2")

    assert pool.add(b1) is True
    assert pool.add(b2) is True
    assert pool.size() == 2


def test_mempool_drain():
    pool = Mempool()
    b1 = Ballot(voter_id="VOTER-1", proposal_id="PROP-1", choice="YES", signature="sig1")
    b2 = Ballot(voter_id="VOTER-2", proposal_id="PROP-1", choice="NO", signature="sig2")
    pool.add(b1)
    pool.add(b2)

    drained = pool.drain()
    assert len(drained) == 2
    assert pool.size() == 0
