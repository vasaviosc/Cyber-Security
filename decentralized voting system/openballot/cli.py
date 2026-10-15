import argparse
import json
import sys
import urllib.request
import urllib.error

from openballot.crypto import (
    generate_keypair,
    public_key_to_hex,
    private_key_to_hex,
    private_key_from_hex,
    sign_message
)
from openballot.ballot import Ballot
from openballot.ledger import Ledger
from openballot.node import NodeServer, NodeHandler


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            return json.loads(err_msg)
        except Exception:
            return {"error": f"HTTP {e.code}: {err_msg}"}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            return json.loads(err_msg)
        except Exception:
            return {"error": f"HTTP {e.code}: {err_msg}"}


def cmd_keygen(args):
    priv, pub = generate_keypair()
    priv_hex = private_key_to_hex(priv)
    pub_hex = public_key_to_hex(pub)
    print("Generated Ed25519 Keypair:")
    print(f"  Voter ID (Public Key): {pub_hex}")
    print(f"  Secret Key           : {priv_hex}")
    if args.save:
        with open(args.save, "w") as f:
            json.dump({"voter_id": pub_hex, "secret_key": priv_hex}, f, indent=2)
        print(f"Saved keypair to {args.save}")


def cmd_vote(args):
    try:
        priv = private_key_from_hex(args.key)
        pub = priv.public_key()
        voter_id = public_key_to_hex(pub)
    except Exception as e:
        print(f"Error loading private key: {e}", file=sys.stderr)
        sys.exit(1)

    ballot = Ballot(
        voter_id=voter_id,
        proposal_id=args.proposal,
        choice=args.choice.upper(),
        weight=args.weight
    )
    sig = sign_message(priv, ballot.get_digest())
    ballot.signature = sig.hex()

    endpoint = f"{args.node.rstrip('/')}/api/v1/ballots"
    res = _post_json(endpoint, ballot.to_dict())
    print("Server response:", json.dumps(res, indent=2))


def cmd_mine(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/mine"
    res = _post_json(endpoint, {})
    print("Miner response:", json.dumps(res, indent=2))


def cmd_tally(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/tally?proposal={args.proposal}"
    res = _get_json(endpoint)
    print("Election Results:")
    print(json.dumps(res, indent=2))


def cmd_status(args):
    endpoint = f"{args.node.rstrip('/')}/health"
    res = _get_json(endpoint)
    print("Node Status:")
    print(json.dumps(res, indent=2))


def cmd_citizen_create(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/citizens"
    payload = {"name": args.name, "district": args.district}
    res = _post_json(endpoint, payload)
    print("Citizen Created & Whitelisted:")
    print(json.dumps(res, indent=2))


def cmd_citizen_list(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/citizens"
    res = _get_json(endpoint)
    print(f"Registered Citizens ({res.get('count', 0)}):")
    for c in res.get("citizens", []):
        print(f"  {c['name']:<20} | {c['district']:<18} | ID: {c['voter_id'][:16]}... | Voted: {c['has_voted']}")


def cmd_serve(args):
    from pathlib import Path
    ledger = Ledger()
    ledger.create_genesis_block()

    # Load sample_voters.json if present
    sample_file = Path(__file__).parent.parent / "sample_voters.json"
    if sample_file.is_file():
        try:
            with open(sample_file, "r") as f:
                voters_data = json.load(f)
                for voter_info in voters_data.values():
                    vid = voter_info.get("voter_id")
                    if vid:
                        ledger.register_voter(vid)
            print(f"[*] Loaded {len(ledger.voter_registry)} authorized voters from sample_voters.json")
        except Exception as e:
            print(f"[*] Notice: Could not load sample_voters.json: {e}")

    server = NodeServer(("0.0.0.0", args.port), NodeHandler, ledger=ledger, difficulty=args.difficulty)
    print(f"[*] OpenBallot node running on http://127.0.0.1:{args.port} (difficulty={args.difficulty})")
    print(f"[*] OpenBallot Web Interface: http://127.0.0.1:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down node.")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(prog="openballot", description="OpenBallot CLI tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # keygen
    p_keygen = subparsers.add_parser("keygen", help="Generate a new voter keypair")
    p_keygen.add_argument("--save", type=str, help="Save keypair to JSON file")
    p_keygen.set_defaults(func=cmd_keygen)

    # vote
    p_vote = subparsers.add_parser("vote", help="Cast a digitally signed ballot")
    p_vote.add_argument("--key", required=True, help="Voter secret key (hex)")
    p_vote.add_argument("--proposal", required=True, help="Proposal ID (e.g. PROP-2026-01)")
    p_vote.add_argument("--choice", required=True, help="Vote choice (e.g. YES, NO)")
    p_vote.add_argument("--weight", type=int, default=1, help="Ballot stake weight (default 1)")
    p_vote.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_vote.set_defaults(func=cmd_vote)

    # mine
    p_mine = subparsers.add_parser("mine", help="Seal pending ballots into a block")
    p_mine.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_mine.set_defaults(func=cmd_mine)

    # tally
    p_tally = subparsers.add_parser("tally", help="Query election results")
    p_tally.add_argument("--proposal", required=True, help="Proposal ID")
    p_tally.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_tally.set_defaults(func=cmd_tally)

    # status
    p_status = subparsers.add_parser("status", help="Get node status")
    p_status.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_status.set_defaults(func=cmd_status)

    # serve
    p_serve = subparsers.add_parser("serve", help="Run node HTTP daemon")
    p_serve.add_argument("--port", type=int, default=8000, help="Listen port")
    p_serve.add_argument("--difficulty", type=int, default=1, help="PoW block difficulty")
    p_serve.set_defaults(func=cmd_serve)

    # citizen-create
    p_cit_create = subparsers.add_parser("citizen-create", help="Create and whitelist a new citizen")
    p_cit_create.add_argument("--name", required=True, help="Citizen full name")
    p_cit_create.add_argument("--district", default="General Precinct", help="Citizen district/precinct")
    p_cit_create.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_cit_create.set_defaults(func=cmd_citizen_create)

    # citizen-list
    p_cit_list = subparsers.add_parser("citizen-list", help="List all registered citizens")
    p_cit_list.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_cit_list.set_defaults(func=cmd_citizen_list)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
