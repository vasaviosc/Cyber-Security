import hashlib
import json
import time
from typing import List, Dict, Any
from openballot.ballot import Ballot


class Block:
    def __init__(
        self,
        index: int,
        prev_hash: str,
        ballots: List[Ballot],
        timestamp: float = None,
        nonce: int = 0
    ):
        self.index = int(index)
        self.prev_hash = str(prev_hash)
        self.ballots = ballots
        self.timestamp = round(float(timestamp), 4) if timestamp is not None else round(time.time(), 4)
        self.nonce = int(nonce)
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        payload = {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "ballots": [b.to_dict() for b in self.ballots],
            "timestamp": round(self.timestamp, 4),
            "nonce": self.nonce
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def mine(self, difficulty: int = 1):
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

    def has_ballot(self, proposal_id: str, voter_id: str) -> bool:
        norm_voter = voter_id.strip().lower()
        norm_prop = proposal_id.strip()
        return any(
            b.proposal_id.strip() == norm_prop and b.voter_id.strip().lower() == norm_voter
            for b in self.ballots
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "ballots": [b.to_dict() for b in self.ballots],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Block":
        ballots = [Ballot.from_dict(b) for b in data.get("ballots", [])]
        blk = cls(
            index=int(data["index"]),
            prev_hash=str(data["prev_hash"]),
            ballots=ballots,
            timestamp=float(data["timestamp"]),
            nonce=int(data.get("nonce", 0))
        )
        blk.hash = str(data.get("hash", blk.compute_hash()))
        return blk

    def __repr__(self) -> str:
        return f"<Block #{self.index} hash={self.hash[:10]}... txs={len(self.ballots)}>"
