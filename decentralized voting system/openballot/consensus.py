import logging
from typing import List, Set, Tuple, Optional
from openballot.block import Block, compute_merkle_root
from openballot.ledger import Ledger, GENESIS_PREV_HASH
from openballot.crypto import verify_signature, public_key_from_hex

logger = logging.getLogger("openballot.consensus")


class ConsensusEngine:
    def __init__(
        self,
        ledger: Ledger,
        difficulty: int = 1,
        mode: str = "pow",
        validators: Optional[Set[str]] = None
    ):
        self.ledger = ledger
        self.difficulty = difficulty
        self.mode = mode.lower()  # "pow" or "poa"
        self.validators = set(v.strip().lower() for v in (validators or []))

    def is_valid_chain(self, chain: List[Block]) -> bool:
        """
        Validates genesis integrity, sequential block continuity, Proof-of-Work/Authority target,
        Merkle root integrity, ballot signatures, voter registration, and double-voting prevention.
        """
        if not chain:
            return False

        # 1. Validate Genesis Block (Index 0)
        genesis = chain[0]
        if genesis.index != 0:
            logger.warning("Genesis block index must be 0, got %d", genesis.index)
            return False
        if genesis.prev_hash != GENESIS_PREV_HASH:
            logger.warning("Invalid genesis prev_hash: %s", genesis.prev_hash)
            return False
        if genesis.compute_hash() != genesis.hash and genesis.compute_hash(legacy=True) != genesis.hash:
            logger.warning("Genesis block hash invalid")
            return False

        # Match local genesis block hash if local chain initialized
        if self.ledger.chain and self.ledger.chain[0].hash != genesis.hash:
            logger.warning("Peer genesis hash does not match local genesis hash")
            return False

        seen_votes: Set[Tuple[str, str]] = set()
        target = "0" * self.difficulty

        # 2. Validate blocks sequentially
        for i in range(len(chain)):
            blk = chain[i]

            if blk.index != i:
                logger.warning("Block index mismatch at position %d: block index %d", i, blk.index)
                return False

            if i > 0:
                prev = chain[i - 1]
                if blk.prev_hash != prev.hash:
                    logger.warning("Hash mismatch at block %d: %s != %s", blk.index, blk.prev_hash, prev.hash)
                    return False

                if self.mode == "pow":
                    if not blk.hash.startswith(target):
                        logger.warning("Block %d does not meet difficulty target (%s)", blk.index, target)
                        return False

            # Verify computed hash (supports both modern header Merkle root and legacy payload)
            if blk.compute_hash() != blk.hash and blk.compute_hash(legacy=True) != blk.hash:
                logger.warning("Invalid computed block hash at block %d", blk.index)
                return False

            # Verify Merkle root integrity if present
            if blk.merkle_root and blk.merkle_root != compute_merkle_root(blk.ballots):
                logger.warning("Merkle root mismatch at block %d", blk.index)
                return False

            for ballot in blk.ballots:
                if not ballot.verify():
                    logger.warning("Invalid ballot signature in block %d for voter %s", blk.index, ballot.voter_id)
                    return False

                if not self.ledger.is_registered(ballot.voter_id):
                    logger.warning("Voter %s in block %d is not in registered voter list", ballot.voter_id, blk.index)
                    return False

                vote_key = (ballot.proposal_id.strip().upper(), ballot.voter_id.strip().lower())
                if vote_key in seen_votes:
                    logger.warning("Double voting detected in chain for voter %s on proposal %s", ballot.voter_id, ballot.proposal_id)
                    return False
                seen_votes.add(vote_key)

        return True

    def resolve_conflicts(self, peer_chains: List[List[Block]]) -> bool:
        """
        Nakamoto-style longest valid chain resolution.
        Rebuilds in-memory ledger indexes upon chain replacement.
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
            self.ledger._rebuild_indexes()
            if self.ledger.storage_path:
                self.ledger.save_to_file()
            return True

        return False
