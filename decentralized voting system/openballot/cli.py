import argparse
import json
import sys
import urllib.request
import urllib.error
from typing import Optional

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
    except urllib.error.URLError as e:
        return {"error": f"Failed to connect to node at {url}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


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
    except urllib.error.URLError as e:
        return {"error": f"Failed to connect to node at {url}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


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
        choice=args.choice,
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


def cmd_register_voter(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/voters"
    res = _post_json(endpoint, {"voter_id": args.voter_id})
    print("Registration response:", json.dumps(res, indent=2))


def cmd_load_voters(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/voters"
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
        voter_ids = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict) and "voter_id" in v:
                    voter_ids.append(v["voter_id"])
                else:
                    voter_ids.append(k)
        elif isinstance(data, list):
            for v in data:
                if isinstance(v, str):
                    voter_ids.append(v)
                elif isinstance(v, dict) and "voter_id" in v:
                    voter_ids.append(v["voter_id"])

        res = _post_json(endpoint, {"voter_ids": voter_ids})
        print("Voter Batch Load response:", json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error reading voter file: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_verify_vote(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/ballots/verify?voter_id={args.voter_id}&proposal={args.proposal}"
    res = _get_json(endpoint)
    print("Vote Audit Verification:")
    print(json.dumps(res, indent=2))


def cmd_proposals(args):
    endpoint = f"{args.node.rstrip('/')}/api/v1/proposals"
    res = _get_json(endpoint)
    print("Active Proposals Overview:")
    print(json.dumps(res, indent=2))


def cmd_serve(args):
    if args.db_file:
        ledger = Ledger.load_from_file(args.db_file)
    else:
        ledger = Ledger()
        ledger.create_genesis_block()

    if args.voters:
        try:
            ledger.load_voter_registry_file(args.voters)
            print(f"[*] Loaded voter registry with {len(ledger.voter_registry)} authorized voters from {args.voters}")
        except Exception as e:
            print(f"[!] Warning: Could not load voter file: {e}", file=sys.stderr)

    engine_type = getattr(args, "engine", "standard")
    if engine_type == "uvicorn":
        try:
            import uvicorn
            import openballot.api_app as api_module
            from openballot.consensus import ConsensusEngine
            api_module.ledger = ledger
            api_module.difficulty = args.difficulty
            api_module.consensus = ConsensusEngine(ledger=ledger, difficulty=args.difficulty, mode=getattr(args, "mode", "pow"))
            print(f"[*] Launching OpenBallot high-performance ASGI daemon on http://127.0.0.1:{args.port} (Uvicorn)")
            uvicorn.run(api_module.app, host="0.0.0.0", port=args.port, log_level="info")
            return
        except ImportError:
            print("[!] Uvicorn not installed, falling back to standard threaded HTTP server.", file=sys.stderr)

    server = NodeServer(("0.0.0.0", args.port), NodeHandler, ledger=ledger, difficulty=args.difficulty)
    print(f"[*] OpenBallot node running on http://127.0.0.1:{args.port} (difficulty={args.difficulty}, threaded=True)")
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

    # register-voter
    p_reg = subparsers.add_parser("register-voter", help="Register a single voter public key")
    p_reg.add_argument("--voter-id", required=True, help="Voter public key hex string")
    p_reg.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_reg.set_defaults(func=cmd_register_voter)

    # load-voters
    p_load_v = subparsers.add_parser("load-voters", help="Load batch of authorized voters from file")
    p_load_v.add_argument("--file", required=True, help="JSON keyring or array file of voter IDs")
    p_load_v.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_load_v.set_defaults(func=cmd_load_voters)

    # verify-vote
    p_verify = subparsers.add_parser("verify-vote", help="Audit and verify inclusion of a ballot")
    p_verify.add_argument("--voter-id", required=True, help="Voter public key hex string")
    p_verify.add_argument("--proposal", required=True, help="Proposal ID")
    p_verify.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_verify.set_defaults(func=cmd_verify_vote)

    # proposals
    p_props = subparsers.add_parser("proposals", help="List active election proposals")
    p_props.add_argument("--node", default="http://127.0.0.1:8000", help="Node URL")
    p_props.set_defaults(func=cmd_proposals)

    # serve
    p_serve = subparsers.add_parser("serve", help="Run node HTTP daemon")
    p_serve.add_argument("--port", type=int, default=8000, help="Listen port")
    p_serve.add_argument("--difficulty", type=int, default=1, help="PoW block difficulty")
    p_serve.add_argument("--db-file", type=str, help="Path to JSON or SQLite (.db) file for persistence")
    p_serve.add_argument("--voters", type=str, help="Path to voter keyring/registry JSON file")
    p_serve.add_argument("--engine", choices=["standard", "uvicorn"], default="standard", help="Web server engine")
    p_serve.add_argument("--mode", choices=["pow", "poa"], default="pow", help="Consensus mode")
    p_serve.set_defaults(func=cmd_serve)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()

