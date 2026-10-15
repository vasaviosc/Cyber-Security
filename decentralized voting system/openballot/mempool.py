from threading import Lock
from typing import Callable, List, Optional
from openballot.ballot import Ballot


class Mempool:
    """
    In-memory transaction pool for unconfirmed ballots awaiting block inclusion.
    """
    def __init__(self):
        self._pool: List[Ballot] = []
        self._lock = Lock()

    def has_ballot(self, proposal_id: str, voter_id: str) -> bool:
        v_id = voter_id.strip().lower()
        p_id = proposal_id.strip()
        with self._lock:
            return any(b.proposal_id == p_id and b.voter_id.lower() == v_id for b in self._pool)

    def add(self, ballot: Ballot) -> bool:
        v_id = ballot.voter_id.strip().lower()
        p_id = ballot.proposal_id.strip()
        with self._lock:
            if any(
                b.proposal_id == p_id and b.voter_id.lower() == v_id
                for b in self._pool
            ):
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

    def retain(self, predicate: Callable[[Ballot], bool]):
        with self._lock:
            self._pool = [ballot for ballot in self._pool if predicate(ballot)]
