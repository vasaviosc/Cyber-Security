from typing import Dict, Set, List, Optional, Any
from openballot.block import Block

GENESIS_PREV_HASH = "0" * 64


class Ledger:
    def __init__(self, voter_registry: Optional[Set[str]] = None):
        self.chain: List[Block] = []
        self.voter_registry: Set[str] = {v.strip().lower() for v in voter_registry} if voter_registry else set()

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
        norm_prop = proposal_id.strip()
        norm_voter = voter_id.strip().lower()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id.strip() == norm_prop and ballot.voter_id.strip().lower() == norm_voter:
                    return True
        return False

    def tally(self, proposal_id: str) -> Dict[str, int]:
        norm_prop = proposal_id.strip()
        results: Dict[str, int] = {}
        voted_voters: Set[str] = set()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id.strip() == norm_prop:
                    voter_key = ballot.voter_id.strip().lower()
                    # Defense-in-depth: count each voter's ballot at most once per proposal
                    if voter_key not in voted_voters:
                        voted_voters.add(voter_key)
                        results[ballot.choice] = results.get(ballot.choice, 0) + ballot.weight
        return results

    def get_proposals(self) -> List[str]:
        proposals: Set[str] = set()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id:
                    proposals.add(ballot.proposal_id.strip())
        return sorted(list(proposals))

    def get_total_ballots(self) -> int:
        return sum(len(block.ballots) for block in self.chain)

    @property
    def latest_block(self) -> Block:
        if not self.chain:
            self.create_genesis_block()
        return self.chain[-1]
