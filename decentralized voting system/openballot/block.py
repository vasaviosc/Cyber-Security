import hashlib
import json
import time
from typing import List, Dict, Any, Optional
from openballot.ballot import Ballot


def compute_merkle_root(ballots: List[Ballot]) -> str:
    """
    Computes cryptographic Merkle root hash for a list of ballots.
    Returns 64-char hex string. Empty list returns 64 zeroes.
    """
    if not ballots:
        return "0" * 64
    leaves = [hashlib.sha256(b.get_digest()).hexdigest() for b in ballots]
    while len(leaves) > 1:
        if len(leaves) % 2 != 0:
            leaves.append(leaves[-1])
        new_level = []
        for i in range(0, len(leaves), 2):
            combined = leaves[i] + leaves[i + 1]
            new_level.append(hashlib.sha256(combined.encode("utf-8")).hexdigest())
        leaves = new_level
    return leaves[0]


class Block:
    def __init__(
        self,
        index: int,
        prev_hash: str,
        ballots: List[Ballot],
        timestamp: Optional[float] = None,
        nonce: int = 0,
        merkle_root: Optional[str] = None
    ):
        self.index = index
        self.prev_hash = prev_hash
        self.ballots = ballots
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.nonce = nonce
        self.merkle_root = merkle_root if merkle_root is not None else compute_merkle_root(self.ballots)
        self.legacy_hash_mode: bool = False
        self.hash = self.compute_hash()

    def compute_hash(self, legacy: bool = False) -> str:
        """
        Computes SHA-256 block hash.
        In modern mode, hashes the fixed-size header (index, prev_hash, merkle_root, timestamp, nonce).
        In legacy mode, serializes all ballots into JSON.
        """
        if legacy or self.legacy_hash_mode:
            payload = {
                "index": self.index,
                "prev_hash": self.prev_hash,
                "ballots": [b.to_dict() for b in self.ballots],
                "timestamp": round(self.timestamp, 4),
                "nonce": self.nonce
            }
        else:
            payload = {
                "index": self.index,
                "merkle_root": self.merkle_root,
                "nonce": self.nonce,
                "prev_hash": self.prev_hash,
                "timestamp": round(self.timestamp, 4)
            }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def mine(self, difficulty: int = 1):
        """
        Proof-of-Work mining.
        Hashes block header without re-serializing transactions on every iteration.
        """
        target = "0" * difficulty
        # Fast header-based mining loop
        prefix = f'{{"index": {self.index}, "merkle_root": "{self.merkle_root}", "nonce": '
        suffix = f', "prev_hash": "{self.prev_hash}", "timestamp": {round(self.timestamp, 4)}}}'
        prefix_b = prefix.encode("utf-8")
        suffix_b = suffix.encode("utf-8")

        nonce = self.nonce
        while True:
            raw_b = prefix_b + str(nonce).encode("ascii") + suffix_b
            h = hashlib.sha256(raw_b).hexdigest()
            if h.startswith(target):
                self.nonce = nonce
                self.hash = h
                break
            nonce += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "ballots": [b.to_dict() for b in self.ballots],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        ballots = [Ballot.from_dict(b) for b in data.get("ballots", [])]
        blk = cls(
            index=data["index"],
            prev_hash=data["prev_hash"],
            ballots=ballots,
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            merkle_root=data.get("merkle_root")
        )
        saved_hash = data.get("hash")
        if saved_hash:
            if blk.compute_hash() == saved_hash:
                blk.hash = saved_hash
            elif blk.compute_hash(legacy=True) == saved_hash:
                blk.legacy_hash_mode = True
                blk.hash = saved_hash
            else:
                blk.hash = saved_hash
        return blk

    def __repr__(self) -> str:
        return f"<Block #{self.index} hash={self.hash[:10]}... txs={len(self.ballots)}>"
