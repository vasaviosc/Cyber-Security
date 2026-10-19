import hashlib
from typing import Dict, Any, Optional
from openballot.crypto import verify_signature, public_key_from_hex


class Ballot:
    def __init__(self, voter_id: str, proposal_id: str, choice: str, signature: str = "", weight: int = 1):
        self.voter_id = voter_id.strip()
        self.proposal_id = proposal_id.strip()
        self.choice = choice.strip()
        self.signature = signature.strip()
        self.weight = int(weight)

    def get_digest(self, legacy: bool = False) -> bytes:
        # Cryptographic digest of ballot contents
        # Securely binds proposal_id, voter_id, choice, and weight to eliminate cross-proposal replay attacks
        if legacy:
            payload = f"{self.voter_id}:{self.choice}:{self.weight}"
        else:
            payload = f"{self.proposal_id}:{self.voter_id.lower()}:{self.choice}:{self.weight}"
        return hashlib.sha256(payload.encode("utf-8")).digest()

    def verify(self) -> bool:
        if not self.signature or not self.voter_id or not self.proposal_id:
            return False
        if self.weight <= 0:
            return False
        try:
            pubkey = public_key_from_hex(self.voter_id)
            sig_bytes = bytes.fromhex(self.signature)
            # 1. Try modern proposal-bound digest
            if verify_signature(pubkey, sig_bytes, self.get_digest(legacy=False)):
                return True
            # 2. Backward compatibility fallback for legacy ballots
            return verify_signature(pubkey, sig_bytes, self.get_digest(legacy=True))
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "voter_id": self.voter_id,
            "proposal_id": self.proposal_id,
            "choice": self.choice,
            "signature": self.signature,
            "weight": self.weight
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ballot":
        return cls(
            voter_id=str(data.get("voter_id", "")).strip(),
            proposal_id=str(data.get("proposal_id", "")).strip(),
            choice=str(data.get("choice", "")).strip(),
            signature=str(data.get("signature", "")).strip(),
            weight=int(data.get("weight", 1))
        )

    def __repr__(self) -> str:
        return f"<Ballot voter={self.voter_id[:8]}... prop={self.proposal_id} choice={self.choice}>"
