from typing import List, Optional
from openballot.ballot import Ballot


class Mempool:
    """
    In-memory transaction pool for unconfirmed ballots awaiting block inclusion.
    """
    def __init__(self):
        self._pool: List[Ballot] = []

    def has_ballot(self, proposal_id: str, voter_id: str) -> bool:
        v_id = voter_id.strip().lower()
        p_id = proposal_id.strip()
        return any(b.proposal_id == p_id and b.voter_id.lower() == v_id for b in self._pool)

    def add(self, ballot: Ballot) -> bool:
        if self.has_ballot(ballot.proposal_id, ballot.voter_id):
            return False
        self._pool.append(ballot)
        return True

    def drain(self, limit: Optional[int] = None) -> List[Ballot]:
        if limit is None or limit >= len(self._pool):
            items = self._pool[:]
            self._pool.clear()
            return items
        items = self._pool[:limit]
        self._pool = self._pool[limit:]
        return items

    def all(self) -> List[Ballot]:
        return list(self._pool)

    def size(self) -> int:
        return len(self._pool)

    def clear(self):
        self._pool.clear()
