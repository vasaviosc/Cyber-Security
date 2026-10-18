import threading
from typing import List, Optional, Set, Tuple
from openballot.ballot import Ballot


class Mempool:
    """
    Thread-safe, bounded, high-throughput in-memory transaction staging pool.
    Provides O(1) duplicate checks and atomic drain operations.
    """
    def __init__(self, max_size: int = 50000):
        self.max_size = max_size
        self._pool: List[Ballot] = []
        self._submitted: Set[Tuple[str, str]] = set()
        self._lock = threading.RLock()

    def has_voter_submitted(self, proposal_id: str, voter_id: str) -> bool:
        """
        O(1) lookup to determine if voter has an unconfirmed ballot in pool.
        """
        prop_norm = proposal_id.strip().upper()
        voter_norm = voter_id.strip().lower()
        with self._lock:
            return (prop_norm, voter_norm) in self._submitted

    def add(self, ballot: Ballot) -> bool:
        """
        O(1) duplicate rejection and atomic pool insertion.
        If pool reaches max_size, drops oldest transaction to prevent memory exhaustion DoS.
        """
        prop_norm = ballot.proposal_id.strip().upper()
        voter_norm = ballot.voter_id.strip().lower()
        key = (prop_norm, voter_norm)

        with self._lock:
            if key in self._submitted:
                return False

            if len(self._pool) >= self.max_size:
                evicted = self._pool.pop(0)
                self._submitted.discard((evicted.proposal_id.strip().upper(), evicted.voter_id.strip().lower()))

            self._pool.append(ballot)
            self._submitted.add(key)
            return True

    def drain(self, limit: Optional[int] = None) -> List[Ballot]:
        """
        Atomically extracts pending transactions for block inclusion.
        """
        with self._lock:
            if limit is None or limit >= len(self._pool):
                items = self._pool[:]
                self._pool.clear()
                self._submitted.clear()
                return items

            items = self._pool[:limit]
            self._pool = self._pool[limit:]
            for b in items:
                self._submitted.discard((b.proposal_id.strip().upper(), b.voter_id.strip().lower()))
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
            self._submitted.clear()
