import hashlib
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from typing import Tuple, List


def generate_keypair() -> Tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    return priv, pub


def sign_message(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> bytes:
    return private_key.sign(data)


def verify_signature(public_key: ed25519.Ed25519PublicKey, signature: bytes, data: bytes) -> bool:
    try:
        public_key.verify(signature, data)
        return True
    except Exception:
        return False


def batch_verify_signatures(items: List[Tuple[ed25519.Ed25519PublicKey, bytes, bytes]]) -> bool:
    """
    Validates multiple signatures. Can be processed in parallel across worker threads.
    """
    for pubkey, sig_bytes, digest in items:
        if not verify_signature(pubkey, sig_bytes, digest):
            return False
    return True


def create_ballot_commitment(choice: str, blinding_factor: str) -> str:
    """
    Creates a cryptographic commitment for secret-ballot voting.
    Hides voter choice until tally reveal phase.
    """
    raw = f"{choice.strip().upper()}:{blinding_factor.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def verify_ballot_commitment(choice: str, blinding_factor: str, expected_commitment: str) -> bool:
    return create_ballot_commitment(choice, blinding_factor) == expected_commitment.strip()


def public_key_to_hex(pubkey: ed25519.Ed25519PublicKey) -> str:
    return pubkey.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()


def public_key_from_hex(hex_str: str) -> ed25519.Ed25519PublicKey:
    return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))


def private_key_to_hex(privkey: ed25519.Ed25519PrivateKey) -> str:
    return privkey.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    ).hex()


def private_key_from_hex(hex_str: str) -> ed25519.Ed25519PrivateKey:
    return ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_str))
