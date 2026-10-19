import json
import threading
import time
import requests
import pytest
from openballot.crypto import generate_keypair, public_key_to_hex, private_key_to_hex, sign_message
from openballot.ballot import Ballot
from openballot.ledger import Ledger
from openballot.node import NodeServer, NodeHandler


@pytest.fixture(scope="module")
def running_node():
    """
    Spins up an OpenBallot node in a background thread on a local test port.
    """
    ledger = Ledger()
    ledger.create_genesis_block()

    # Pre-register Alice and Bob
    priv_a, pub_a = generate_keypair()
    alice_id = public_key_to_hex(pub_a)
    alice_priv = private_key_to_hex(priv_a)
    ledger.register_voter(alice_id)

    priv_b, pub_b = generate_keypair()
    bob_id = public_key_to_hex(pub_b)
    bob_priv = private_key_to_hex(priv_b)
    ledger.register_voter(bob_id)

    # Use a free port (e.g. 8912)
    port = 8912
    server = NodeServer(("127.0.0.1", port), NodeHandler, ledger=ledger, difficulty=1)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)  # Give server brief moment to bind

    base_url = f"http://127.0.0.1:{port}"
    yield {
        "base_url": base_url,
        "server": server,
        "alice": {"id": alice_id, "priv": priv_a, "priv_hex": alice_priv},
        "bob": {"id": bob_id, "priv": priv_b, "priv_hex": bob_priv}
    }

    server.shutdown()
    server.server_close()


def test_cors_and_options_headers(running_node):
    base_url = running_node["base_url"]

    # Preflight OPTIONS
    opt_res = requests.options(f"{base_url}/api/v1/ballots")
    assert opt_res.status_code == 204
    assert opt_res.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in opt_res.headers.get("Access-Control-Allow-Methods", "")

    # GET with CORS
    health_res = requests.get(f"{base_url}/health")
    assert health_res.status_code == 200
    assert health_res.headers.get("Access-Control-Allow-Origin") == "*"
    data = health_res.json()
    assert data["status"] == "healthy"


def test_static_dashboard_serving(running_node):
    base_url = running_node["base_url"]

    # Root / dashboard
    res_root = requests.get(f"{base_url}/")
    assert res_root.status_code == 200
    assert "text/html" in res_root.headers.get("Content-Type", "")
    assert "HEXANOVA" in res_root.text

    # Static CSS
    res_css = requests.get(f"{base_url}/style.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("Content-Type", "")

    # Static JS
    res_js = requests.get(f"{base_url}/app.js")
    assert res_js.status_code == 200
    assert "application/javascript" in res_js.headers.get("Content-Type", "")


def test_valid_ballot_and_mining_flow(running_node):
    base_url = running_node["base_url"]
    alice = running_node["alice"]

    # 1. Cast valid signed ballot
    b = Ballot(voter_id=alice["id"], proposal_id="TEST-PROP-1", choice="YES", weight=1)
    sig = sign_message(alice["priv"], b.get_digest())
    b.signature = sig.hex()

    res = requests.post(f"{base_url}/api/v1/ballots", json=b.to_dict())
    assert res.status_code == 202
    assert res.json()["status"] == "accepted"

    # Verify ballot is in mempool
    mem_res = requests.get(f"{base_url}/api/v1/mempool")
    assert mem_res.status_code == 200
    assert mem_res.json()["count"] >= 1

    # 2. Mine block
    mine_res = requests.post(f"{base_url}/api/v1/mine", json={})
    assert mine_res.status_code == 200
    assert mine_res.json()["status"] == "mined"
    assert mine_res.json()["ballots_sealed"] >= 1

    # Verify tally
    tally_res = requests.get(f"{base_url}/api/v1/tally?proposal=TEST-PROP-1")
    assert tally_res.status_code == 200
    assert tally_res.json()["results"].get("YES") == 1


def test_mempool_double_vote_rejection(running_node):
    base_url = running_node["base_url"]
    bob = running_node["bob"]

    # 1. First ballot into mempool
    b1 = Ballot(voter_id=bob["id"], proposal_id="PROP-DOUBLE-TEST", choice="YES", weight=1)
    b1.signature = sign_message(bob["priv"], b1.get_digest()).hex()

    res1 = requests.post(f"{base_url}/api/v1/ballots", json=b1.to_dict())
    assert res1.status_code == 202

    # 2. Second ballot while first is still unconfirmed in mempool
    b2 = Ballot(voter_id=bob["id"], proposal_id="PROP-DOUBLE-TEST", choice="NO", weight=1)
    b2.signature = sign_message(bob["priv"], b2.get_digest()).hex()

    res2 = requests.post(f"{base_url}/api/v1/ballots", json=b2.to_dict())
    assert res2.status_code == 409
    assert "DOUBLE_VOTE_MEMPOOL" in res2.json().get("code", "")

    # Clean up mempool by mining
    requests.post(f"{base_url}/api/v1/mine", json={})


def test_confirmed_ledger_double_vote_rejection(running_node):
    base_url = running_node["base_url"]
    alice = running_node["alice"]

    # Alice already had ballot confirmed for TEST-PROP-1 in test_valid_ballot_and_mining_flow
    b = Ballot(voter_id=alice["id"], proposal_id="TEST-PROP-1", choice="NO", weight=1)
    b.signature = sign_message(alice["priv"], b.get_digest()).hex()

    res = requests.post(f"{base_url}/api/v1/ballots", json=b.to_dict())
    assert res.status_code == 409
    assert "DOUBLE_VOTE_CONFIRMED" in res.json().get("code", "")


def test_forged_signature_rejection(running_node):
    base_url = running_node["base_url"]
    alice = running_node["alice"]

    # Submit ballot with corrupted signature
    b = Ballot(voter_id=alice["id"], proposal_id="TEST-PROP-FORGE", choice="YES", weight=1)
    b.signature = "deadbeef" * 16

    res = requests.post(f"{base_url}/api/v1/ballots", json=b.to_dict())
    assert res.status_code == 401
    assert res.json().get("code") == "INVALID_SIGNATURE"


def test_unregistered_voter_rejection(running_node):
    base_url = running_node["base_url"]
    # Generate unregistered voter
    priv_u, pub_u = generate_keypair()
    unreg_id = public_key_to_hex(pub_u)

    b = Ballot(voter_id=unreg_id, proposal_id="TEST-PROP-UNREG", choice="YES", weight=1)
    b.signature = sign_message(priv_u, b.get_digest()).hex()

    res = requests.post(f"{base_url}/api/v1/ballots", json=b.to_dict())
    assert res.status_code == 403
    assert res.json().get("code") == "UNAUTHORIZED_VOTER"


def test_security_events_audit_log(running_node):
    base_url = running_node["base_url"]

    # Query logged security events
    res = requests.get(f"{base_url}/api/v1/security/events?limit=20")
    assert res.status_code == 200
    data = res.json()
    assert "events" in data
    assert "summary" in data
    assert data["count"] > 0

    # Ensure critical events (like forged signature) were logged
    severities = [e["severity"] for e in data["events"]]
    assert "CRITICAL" in severities or "SUSPICIOUS" in severities


def test_attack_simulation_endpoint(running_node):
    base_url = running_node["base_url"]

    res_sig = requests.post(f"{base_url}/api/v1/security/simulate", json={"type": "signature_tamper"})
    assert res_sig.status_code == 200
    assert res_sig.json()["status"] == "BLOCKED"

    res_dv = requests.post(f"{base_url}/api/v1/security/simulate", json={"type": "double_vote"})
    assert res_dv.status_code == 200
    assert res_dv.json()["status"] == "BLOCKED"
