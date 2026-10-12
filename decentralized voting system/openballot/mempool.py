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

    def add(self, ballot: Ballot) -> bool:
        with self._lock:
            if any(
                pending.proposal_id == ballot.proposal_id
                and pending.voter_id.lower() == ballot.voter_id.lower()
                for pending in self._pool
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
