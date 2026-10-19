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
        Validates block continuity, Proof-of-Work proofs, and transaction cryptographic integrity.
        Enforces Genesis integrity, sequential indexing, monotonic timestamps, and zero duplicate votes.
        """
        if not chain:
            return False

        # 1. Validate Genesis block integrity (Block #0)
        genesis = chain[0]
        if genesis.index != 0:
            logger.warning("Invalid genesis block index: %d", genesis.index)
            return False
        if genesis.prev_hash != "0" * 64:
            logger.warning("Invalid genesis previous hash: %s", genesis.prev_hash)
            return False
        if genesis.compute_hash() != genesis.hash:
            logger.warning("Genesis block hash mismatch: %s != %s", genesis.compute_hash(), genesis.hash)
            return False

        target = "0" * self.difficulty
        seen_votes = set()

        # Check any ballots in Genesis if present
        for ballot in genesis.ballots:
            if not ballot.verify():
                return False
            vote_key = (ballot.proposal_id.strip(), ballot.voter_id.strip().lower())
            seen_votes.add(vote_key)

        # 2. Verify sequential block transitions and proofs
        for i in range(1, len(chain)):
            prev = chain[i - 1]
            curr = chain[i]

            # Sequential block height
            if curr.index != prev.index + 1:
                logger.warning("Non-sequential block index at #%d (prev was #%d)", curr.index, prev.index)
                return False

            # Hash linkage
            if curr.prev_hash != prev.hash:
                logger.warning("Hash mismatch at block %d: %s != %s", curr.index, curr.prev_hash, prev.hash)
                return False

            # Hash proof
            if curr.compute_hash() != curr.hash:
                logger.warning("Invalid block hash at block %d", curr.index)
                return False

            # Difficulty target
            if not curr.hash.startswith(target):
                logger.warning("Block %d does not meet difficulty target", curr.index)
                return False

            # Chronological timestamp validation
            if curr.timestamp < prev.timestamp:
                logger.warning("Chronological violation: block %d timestamp %f < block %d timestamp %f",
                               curr.index, curr.timestamp, prev.index, prev.timestamp)
                return False

            # Ballot cryptographic validity and duplicate check
            for ballot in curr.ballots:
                if not ballot.verify():
                    logger.warning("Corrupt ballot signature in block %d", curr.index)
                    return False
                vote_key = (ballot.proposal_id.strip(), ballot.voter_id.strip().lower())
                if vote_key in seen_votes:
                    logger.warning("Double voting attack detected in block %d for voter %s on %s",
                                   curr.index, ballot.voter_id, ballot.proposal_id)
                    return False
                seen_votes.add(vote_key)

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
