from typing import Dict, Set, List, Optional
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
        v_id = voter_id.strip().lower()
        p_id = proposal_id.strip()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id == p_id and ballot.voter_id.strip().lower() == v_id:
                    return True
        return False

    def tally(self, proposal_id: str) -> Dict[str, int]:
        results: Dict[str, int] = {}
        counted_voters: Set[str] = set()
        p_id = proposal_id.strip()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id == p_id:
                    v_id = ballot.voter_id.strip().lower()
                    if v_id not in counted_voters:
                        counted_voters.add(v_id)
                        results[ballot.choice] = results.get(ballot.choice, 0) + ballot.weight
        return results

    def get_proposals(self) -> List[str]:
        proposals = []
        seen = set()
        for block in self.chain:
            for ballot in block.ballots:
                if ballot.proposal_id and ballot.proposal_id not in seen:
                    seen.add(ballot.proposal_id)
                    proposals.append(ballot.proposal_id)
        return proposals

    @property
    def latest_block(self) -> Block:
        if not self.chain:
            self.create_genesis_block()
        return self.chain[-1]
