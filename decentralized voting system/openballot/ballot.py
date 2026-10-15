import hashlib
from typing import Dict, Any
from openballot.crypto import verify_signature, public_key_from_hex


class Ballot:
    def __init__(self, voter_id: str, proposal_id: str, choice: str, signature: str = "", weight: int = 1):
        self.voter_id = voter_id.strip()
        self.proposal_id = proposal_id.strip()
        self.choice = choice.strip()
        self.signature = signature.strip()
        w = int(weight)
        if w < 1:
            raise ValueError("Vote weight must be a positive integer (minimum 1)")
        if w > 100:
            raise ValueError("Vote weight exceeds maximum authorized threshold")
        self.weight = w

    def get_digest(self) -> bytes:
        # Cryptographically binds voter_id, proposal_id, choice, and weight
        payload = f"{self.voter_id.lower()}:{self.proposal_id}:{self.choice}:{self.weight}"
        return hashlib.sha256(payload.encode("utf-8")).digest()

    def verify(self) -> bool:
        if not self.signature or not self.voter_id:
            return False
        try:
            pubkey = public_key_from_hex(self.voter_id)
            sig_bytes = bytes.fromhex(self.signature)
            return verify_signature(pubkey, sig_bytes, self.get_digest())
        except Exception:
            return False

    @property
    def receipt_hash(self) -> str:
        payload = f"{self.voter_id.lower()}:{self.proposal_id}:{self.signature}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "proposal_id": self.proposal_id,
            "choice": self.choice,
            "signature": self.signature,
            "weight": self.weight,
            "receipt_hash": self.receipt_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ballot":
        return cls(
            voter_id=data.get("voter_id", ""),
            proposal_id=data.get("proposal_id", ""),
            choice=data.get("choice", ""),
            signature=data.get("signature", ""),
            weight=int(data.get("weight", 1))
        )

    def __repr__(self) -> str:
        return f"<Ballot voter={self.voter_id[:8]}... prop={self.proposal_id} choice={self.choice}>"
