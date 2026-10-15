import logging
from typing import List, Dict, Any, Optional
from openballot.block import Block
from openballot.ledger import Ledger

logger = logging.getLogger("openballot.consensus")


class ConsensusEngine:
    def __init__(self, ledger: Ledger, difficulty: int = 1):
        self.ledger = ledger
        self.difficulty = difficulty

    def verify_chain_detailed(self, chain: Optional[List[Block]] = None) -> Dict[str, Any]:
        """
        Runs comprehensive block-by-block continuity and transaction verification.
        Returns a detailed report suitable for audit display and UI verification.
        """
        target_chain = chain if chain is not None else self.ledger.chain
        if not target_chain:
            return {"valid": False, "message": "Blockchain is empty", "total_blocks": 0, "blocks": []}

        block_results = []
        is_overall_valid = True

        # Genesis check
        genesis = target_chain[0]
        genesis_err = None

        if self.ledger.chain and genesis.to_dict() != self.ledger.chain[0].to_dict():
            genesis_err = "Genesis block does not match the node's trusted genesis block"
        elif type(genesis.index) is not int or genesis.index != 0:
            genesis_err = "Genesis block index must be integer 0"
        elif genesis.prev_hash != "0" * 64:
            genesis_err = "Genesis block prev_hash must be 64 zeros"
        elif genesis.compute_hash() != genesis.hash:
            genesis_err = "Genesis block hash does not match computed SHA-256 payload"

        seen_votes = set()
        if not genesis_err:
            for ballot in genesis.ballots:
                if (
                    not ballot.voter_id
                    or not ballot.proposal_id
                    or not ballot.choice
                    or not ballot.verify()
                    or not self.ledger.is_registered(ballot.voter_id)
                ):
                    genesis_err = "Corrupt ballot signature or unregistered voter in genesis block"
                    break
                key = (ballot.proposal_id, ballot.voter_id.lower())
                if key in seen_votes:
                    genesis_err = "Duplicate ballot in genesis block"
                    break
                seen_votes.add(key)

        if genesis_err:
            is_overall_valid = False
            logger.warning("Genesis block validation failed: %s", genesis_err)
            block_results.append({
                "index": 0,
                "status": "INVALID",
                "reason": genesis_err,
                "hash": getattr(genesis, "hash", "")
            })
        else:
            block_results.append({
                "index": 0,
                "status": "VALID",
                "reason": "Genesis block structure valid",
                "hash": genesis.hash
            })

        for i in range(1, len(target_chain)):
            prev = target_chain[i - 1]
            curr = target_chain[i]
            block_err = None

            if type(curr.index) is not int or curr.index != prev.index + 1:
                block_err = f"Index mismatch: expected #{prev.index + 1}, found #{curr.index}"
            elif curr.prev_hash != prev.hash:
                block_err = f"Hash mismatch: prev_hash does not match block #{prev.index} hash"
            elif curr.compute_hash() != curr.hash:
                block_err = "Block hash does not match computed SHA-256 payload"
            elif not curr.hash.startswith("0" * self.difficulty):
                block_err = f"Block does not meet difficulty target ('0' * {self.difficulty})"
            else:
                for ballot in curr.ballots:
                    if (
                        not ballot.voter_id
                        or not ballot.proposal_id
                        or not ballot.choice
                        or not ballot.verify()
                        or not self.ledger.is_registered(ballot.voter_id)
                    ):
                        block_err = f"Invalid cryptographic signature or unregistered voter on ballot from voter {ballot.voter_id[:8]}"
                        break
                    key = (ballot.proposal_id, ballot.voter_id.lower())
                    if key in seen_votes:
                        block_err = f"Double voting detected: voter {ballot.voter_id[:8]} already voted on {ballot.proposal_id}"
                        break
                    seen_votes.add(key)

            if block_err:
                is_overall_valid = False
                logger.warning("Block validation failed for block %s: %s", getattr(curr, 'index', i), block_err)
                block_results.append({
                    "index": getattr(curr, "index", i),
                    "status": "INVALID",
                    "reason": block_err,
                    "hash": getattr(curr, "hash", ""),
                    "ballots_count": len(getattr(curr, "ballots", []))
                })
            else:
                block_results.append({
                    "index": curr.index,
                    "status": "VALID",
                    "reason": "Proof-of-work, continuity, and signatures verified",
                    "hash": curr.hash,
                    "ballots_count": len(curr.ballots)
                })

        return {
            "valid": is_overall_valid,
            "total_blocks": len(target_chain),
            "message": "Blockchain integrity verified" if is_overall_valid else "Blockchain integrity compromised",
            "blocks": block_results
        }

    def is_valid_chain(self, chain: List[Block]) -> bool:
        """
        Validates block continuity and transaction integrity using verify_chain_detailed.
        """
        if not chain or not self.ledger.chain:
            return False
        return self.verify_chain_detailed(chain)["valid"]

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
