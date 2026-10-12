from typing import Dict, Set, List, Optional
from openballot.block import Block

GENESIS_PREV_HASH = "0" * 64


class Ledger:
    def __init__(self, voter_registry: Optional[Set[str]] = None):
        self.chain: List[Block] = []
        self.voter_registry: Set[str] = voter_registry or set()

    def create_genesis_block(self) -> Block:
        if self.chain:
            return self.chain[0]
        genesis = Block(
            index=0,
            prev_hash=GENESIS_PREV_HASH,
            ballots=[],
            timestamp=1700000000.0,
            nonce=0
        )
        self.chain.append(genesis)
        return genesis

    def register_voter(self, voter_id: str):
        self.voter_registry.add(voter_id.strip().lower())

    def is_registered(self, voter_id: str) -> bool:
        if not self.voter_registry:
            # If no registry provided, open voter policy
            return True
        return voter_id.strip().lower() in self.voter_registry

    def has_voted(self, proposal_id: str, voter_id: str) -> bool:
        canonical_voter_id = voter_id.strip().lower()
        for block in self.chain:
            for ballot in block.ballots:
                if (
                    ballot.proposal_id == proposal_id
                    and ballot.voter_id.lower() == canonical_voter_id
                ):
                    return True
        return False

    def tally(self, proposal_id: str) -> Dict[str, int]:
        results: Dict[str, int] = {}
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id == proposal_id:
                    results[ballot.choice] = results.get(ballot.choice, 0) + ballot.weight
        return results

    @property
    def latest_block(self) -> Block:
        if not self.chain:
            self.create_genesis_block()
        return self.chain[-1]
