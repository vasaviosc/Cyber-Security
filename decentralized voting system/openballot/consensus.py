import logging
from typing import List
from openballot.block import Block
from openballot.ledger import Ledger

logger = logging.getLogger("openballot.consensus")


class ConsensusEngine:
    def __init__(self, ledger: Ledger, difficulty: int = 1):
        self.ledger = ledger
        self.difficulty = difficulty

    def is_valid_chain(self, chain: List[Block]) -> bool:
        """
        Validates the trusted genesis, block transitions, proofs, and ballots.
        """
        if not chain or not self.ledger.chain:
            return False

        if chain[0].to_dict() != self.ledger.chain[0].to_dict():
            logger.warning("Candidate chain does not match the trusted genesis block")
            return False

        seen_ballots = set()
        target = "0" * self.difficulty
        for index, curr in enumerate(chain):
            if type(curr.index) is not int or curr.index != index:
                logger.warning("Unexpected block index %r at position %d", curr.index, index)
                return False

            if curr.compute_hash() != curr.hash:
                logger.warning("Invalid block hash at block %d", curr.index)
                return False

            if index == 0:
                continue

            prev = chain[index - 1]
            if curr.prev_hash != prev.hash:
                logger.warning("Hash mismatch at block %d: %s != %s", curr.index, curr.prev_hash, prev.hash)
                return False

            if not curr.hash.startswith(target):
                logger.warning("Block %d does not meet difficulty target", curr.index)
                return False

            for ballot in curr.ballots:
                if (
                    not ballot.voter_id
                    or not ballot.proposal_id
                    or not ballot.choice
                    or not ballot.verify()
                    or not self.ledger.is_registered(ballot.voter_id)
                ):
                    logger.warning("Corrupt ballot signature in block %d", curr.index)
                    return False

                ballot_key = (ballot.proposal_id, ballot.voter_id.lower())
                if ballot_key in seen_ballots:
                    logger.warning("Duplicate ballot in block %d", curr.index)
                    return False
                seen_ballots.add(ballot_key)

        return True

    def resolve_conflicts(self, peer_chains: List[List[Block]]) -> bool:
        """
        Nakamoto-style longest valid chain resolution.
        """
        longest = None
        max_len = len(self.ledger.chain)

        for candidate in peer_chains:
            if len(candidate) > max_len and self.is_valid_chain(candidate):
                max_len = len(candidate)
                longest = candidate

        if longest:
            logger.info("Adopting peer chain of length %d (replaced %d)", len(longest), len(self.ledger.chain))
            self.ledger.chain = longest
            return True

        return False
