import threading
from typing import List, Optional
from openballot.ballot import Ballot


class Mempool:
    """
    Thread-safe in-memory transaction pool for unconfirmed ballots awaiting block inclusion.
    Enforces uniqueness per (proposal_id, voter_id) to prevent mempool ballot spamming and double-voting.
    """
    def __init__(self):
        self._pool: List[Ballot] = []
        self._lock = threading.Lock()

    def has_ballot(self, proposal_id: str, voter_id: str) -> bool:
        norm_voter = voter_id.strip().lower()
        norm_prop = proposal_id.strip()
        with self._lock:
            return any(
                b.proposal_id.strip() == norm_prop and b.voter_id.strip().lower() == norm_voter
                for b in self._pool
            )

    def add(self, ballot: Ballot) -> bool:
        norm_voter = ballot.voter_id.strip().lower()
        norm_prop = ballot.proposal_id.strip()
        with self._lock:
            # Reject duplicate ballot in mempool for same voter and proposal
            if any(b.proposal_id.strip() == norm_prop and b.voter_id.strip().lower() == norm_voter for b in self._pool):
                return False
            self._pool.append(ballot)
            return True

    def drain(self, limit: Optional[int] = None) -> List[Ballot]:
        with self._lock:
            if limit is None or limit >= len(self._pool):
                items = self._pool[:]
                self._pool.clear()
                return items
            items = self._pool[:limit]
            self._pool = self._pool[limit:]
            return items

    def all(self) -> List[Ballot]:
        with self._lock:
            return list(self._pool)

    def size(self) -> int:
        with self._lock:
            return len(self._pool)

    def clear(self):
        with self._lock:
            self._pool.clear()
