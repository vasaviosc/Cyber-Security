#!/usr/bin/env python3
"""
Utility script to generate sample voters for an election demo.
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openballot.crypto import generate_keypair, public_key_to_hex, private_key_to_hex


def main():
    voters = ["alice", "bob", "charlie", "dave", "eve"]
    registry = {}
    keyring = {}

    for name in voters:
        priv, pub = generate_keypair()
        pub_hex = public_key_to_hex(pub)
        priv_hex = private_key_to_hex(priv)

        keyring[name] = {
            "voter_id": pub_hex,
            "secret_key": priv_hex
        }
        registry[pub_hex] = name

    out_file = Path(__file__).parent.parent / "sample_voters.json"
    with open(out_file, "w") as f:
        json.dump(keyring, f, indent=2)

    print(f"Generated {len(voters)} voter keypairs.")
    print(f"Keyring written to: {out_file}")
    print("\nSample voters:")
    for name, data in keyring.items():
        print(f"  {name.capitalize():<8}: ID={data['voter_id'][:16]}... Secret={data['secret_key'][:16]}...")
    print("\nTo start an OpenBallot node pre-loaded with these voters, run:")
    print("  python -m openballot.cli serve --voters sample_voters.json")


if __name__ == "__main__":
    main()

