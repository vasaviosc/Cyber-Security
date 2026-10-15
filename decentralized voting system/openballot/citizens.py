import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from openballot.crypto import generate_keypair, public_key_to_hex, private_key_to_hex


class Citizen:
    def __init__(
        self,
        name: str,
        voter_id: str,
        district: str = "General Precinct",
        secret_key: Optional[str] = None,
        registered_at: Optional[float] = None
    ):
        self.name = name.strip()
        self.voter_id = voter_id.strip().lower()
        self.district = district.strip() or "General Precinct"
        self.secret_key = secret_key.strip() if secret_key else None
        self.registered_at = registered_at or time.time()

    def to_dict(self, include_secret: bool = True) -> Dict[str, Any]:
        data = {
            "name": self.name,
            "voter_id": self.voter_id,
            "district": self.district,
            "registered_at": self.registered_at
        }
        if include_secret and self.secret_key:
            data["secret_key"] = self.secret_key
        return data


class CitizenManager:
    """
    Manages citizen/voter profiles, demographics, and keypairs.
    Integrates directly with the blockchain ledger whitelist.
    """
    def __init__(self, persistence_file: Optional[Path] = None):
        self._citizens: Dict[str, Citizen] = {}
        self.persistence_file = persistence_file

    def get_all(self, include_secrets: bool = True) -> List[Dict[str, Any]]:
        return [c.to_dict(include_secret=include_secrets) for c in self._citizens.values()]

    def get(self, voter_id: str) -> Optional[Citizen]:
        return self._citizens.get(voter_id.strip().lower())

    def add_citizen(
        self,
        name: str,
        voter_id: str,
        district: str = "General Precinct",
        secret_key: Optional[str] = None
    ) -> Citizen:
        vid = voter_id.strip().lower()
        citizen = Citizen(
            name=name,
            voter_id=vid,
            district=district,
            secret_key=secret_key
        )
        self._citizens[vid] = citizen
        self._persist()
        return citizen

    def create_citizen(
        self,
        name: str,
        district: str = "General Precinct"
    ) -> Citizen:
        """
        Generates a new Ed25519 keypair and creates an authorized citizen profile.
        """
        priv, pub = generate_keypair()
        pub_hex = public_key_to_hex(pub)
        priv_hex = private_key_to_hex(priv)

        return self.add_citizen(
            name=name,
            voter_id=pub_hex,
            district=district,
            secret_key=priv_hex
        )

    def load_from_file(self, filepath: Path, persist: bool = False):
        self.persistence_file = filepath if persist else None
        if not filepath.is_file():
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key_name, info in data.items():
                    vid = info.get("voter_id")
                    if vid:
                        name = info.get("name") or key_name.capitalize()
                        district = info.get("district") or "District Alpha"
                        secret = info.get("secret_key")
                        self.add_citizen(name=name, voter_id=vid, district=district, secret_key=secret)
        except Exception as e:
            # Silently tolerate parse issue or log
            pass

    def _persist(self):
        if not self.persistence_file:
            return
        try:
            out: Dict[str, Any] = {}
            for vid, c in self._citizens.items():
                # Use slugified name or vid as dictionary key
                slug = c.name.lower().replace(" ", "_") or vid[:8]
                out[slug] = c.to_dict(include_secret=True)
            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception:
            pass


# Global singleton
citizen_manager = CitizenManager()
