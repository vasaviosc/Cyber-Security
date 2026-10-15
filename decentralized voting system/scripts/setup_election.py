#!/usr/bin/env python3
"""
Utility script to generate sample voters/citizens for an election demo.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openballot.crypto import generate_keypair, public_key_to_hex, private_key_to_hex

SAMPLE_NAMES = [
    ("aarav", "Aarav Sharma", "New Delhi Central (DL-04)"),
    ("priya", "Priya Patel", "Ahmedabad West (GJ-08)"),
    ("rahul", "Rahul Verma", "Bengaluru South (KA-26)"),
    ("ananya", "Ananya Iyer", "Chennai Central (TN-04)"),
    ("rohan", "Rohan Mukherjee", "Kolkata North (WB-24)"),
    ("sneha", "Sneha Reddy", "Hyderabad Secunderabad (TG-10)"),
    ("vikram", "Vikram Singh", "Jaipur Rural (RJ-06)"),
    ("pooja", "Pooja Deshmukh", "Pune City (MH-34)"),
    ("arjun", "Arjun Nair", "Thiruvananthapuram (KL-20)"),
    ("meera", "Meera Das", "Guwahati East (AS-07)"),
]


def main():
    parser = argparse.ArgumentParser(description="Generate sample voters for OpenBallot")
    parser.add_argument("--count", "-c", type=int, default=5, help="Number of sample voters to generate (default: 5)")
    args = parser.parse_args()

    count = max(1, min(args.count, len(SAMPLE_NAMES)))
    keyring = {}

    for i in range(count):
        slug, full_name, district = SAMPLE_NAMES[i]
        priv, pub = generate_keypair()
        pub_hex = public_key_to_hex(pub)
        priv_hex = private_key_to_hex(priv)

        keyring[slug] = {
            "name": full_name,
            "district": district,
            "voter_id": pub_hex,
            "secret_key": priv_hex
        }

    out_file = Path(__file__).parent.parent / "sample_voters.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(keyring, f, indent=2)

    print(f"Generated {count} citizen keypairs.")
    print(f"Keyring written to: {out_file}")
    print("\nSample Citizens:")
    for slug, data in keyring.items():
        print(f"  {data['name']:<18} ({data['district']:<20}) ID={data['voter_id'][:16]}... Secret={data['secret_key'][:16]}...")


if __name__ == "__main__":
    main()
