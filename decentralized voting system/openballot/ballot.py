import hashlib
import time
from typing import Dict, Any, Optional
from openballot.crypto import verify_signature, public_key_from_hex


class Ballot:
    def __init__(
        self,
        voter_id: str,
        proposal_id: str,
        choice: str,
        signature: str = "",
        weight: int = 1,
        nonce: int = 0,
        timestamp: Optional[float] = None,
        commitment: str = ""
    ):
        self.voter_id = voter_id.strip().lower()
        self.proposal_id = proposal_id.strip().upper()
        self.choice = choice.strip().upper()
        self.signature = signature.strip()
        self.weight = int(weight)
        self.nonce = int(nonce)
        self.timestamp = timestamp
        self.commitment = commitment.strip()

    def get_digest(self) -> bytes:
        """
        Serialized message digest to sign.
        Binds proposal_id, voter_id, choice, and weight to prevent replay attacks.
        If nonce, timestamp, or commitment are specified, they are bound into the digest.
        """
        if self.nonce == 0 and self.timestamp is None and not self.commitment:
            payload = f"{self.proposal_id}:{self.voter_id}:{self.choice}:{self.weight}"
        else:
            ts_str = f"{self.timestamp:.4f}" if self.timestamp is not None else ""
            payload = f"{self.proposal_id}:{self.voter_id}:{self.choice}:{self.weight}:{self.nonce}:{ts_str}:{self.commitment}"
        return hashlib.sha256(payload.encode("utf-8")).digest()

    def verify(self) -> bool:
        if not self.signature or not self.voter_id or not self.proposal_id:
            return False
        try:
            pubkey = public_key_from_hex(self.voter_id)
            sig_bytes = bytes.fromhex(self.signature)
            return verify_signature(pubkey, sig_bytes, self.get_digest())
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "voter_id": self.voter_id,
            "proposal_id": self.proposal_id,
            "choice": self.choice,
            "signature": self.signature,
            "weight": self.weight
        }
        if self.nonce != 0:
            data["nonce"] = self.nonce
        if self.timestamp is not None:
            data["timestamp"] = self.timestamp
        if self.commitment:
            data["commitment"] = self.commitment
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ballot":
        return cls(
            voter_id=data.get("voter_id", ""),
            proposal_id=data.get("proposal_id", ""),
            choice=data.get("choice", ""),
            signature=data.get("signature", ""),
            weight=int(data.get("weight", 1)),
            nonce=int(data.get("nonce", 0)),
            timestamp=data.get("timestamp"),
            commitment=data.get("commitment", "")
        )

    def __repr__(self) -> str:
        return f"<Ballot voter={self.voter_id[:8]}... prop={self.proposal_id} choice={self.choice}>"
