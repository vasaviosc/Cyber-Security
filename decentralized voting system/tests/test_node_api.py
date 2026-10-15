import json
import urllib.request
import urllib.error

# pyrefly: ignore [missing-import]
import pytest

from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ballot import Ballot





def test_api_health(running_server):
    base_url, _ = running_server
    req = urllib.request.Request(f"{base_url}/health")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["status"] == "healthy"
        assert data["blocks"] >= 1
        assert "difficulty" in data


def test_api_elections(running_server):
    base_url, _ = running_server
    req = urllib.request.Request(f"{base_url}/api/v1/elections")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert "elections" in data
        assert len(data["elections"]) >= 2
        assert data["elections"][0]["proposal_id"] == "PROP-2026-01"


def test_api_ballot_submission_and_weight_validation(running_server):
    base_url, ledger = running_server
    priv, pub = generate_keypair()
    vid = public_key_to_hex(pub)
    ledger.register_voter(vid)

    # 1. Invalid weight should be rejected
    ballot_bad_weight = {
        "voter_id": vid,
        "proposal_id": "PROP-2026-01",
        "choice": "YES",
        "weight": 5,
        "signature": "1234"
    }
    req_bad = urllib.request.Request(
        f"{base_url}/api/v1/ballots",
        data=json.dumps(ballot_bad_weight).encode(),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req_bad)
    assert exc_info.value.code == 400
    exc_info.value.read()
    exc_info.value.close()

    # 2. Valid ballot submission
    ballot = Ballot(vid, "PROP-2026-01", "YES", weight=1)
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()

    req_good = urllib.request.Request(
        f"{base_url}/api/v1/ballots",
        data=json.dumps(ballot.to_dict()).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req_good) as resp:
        assert resp.status == 202
        res = json.loads(resp.read().decode())
        assert res["status"] == "accepted"
        assert "vote_id" in res

    # 3. Duplicate submission while in mempool should be rejected (409)
    req_dup = urllib.request.Request(
        f"{base_url}/api/v1/ballots",
        data=json.dumps(ballot.to_dict()).encode(),
        headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as exc_dup:
        urllib.request.urlopen(req_dup)
    assert exc_dup.value.code == 409
    exc_dup.value.read()
    exc_dup.value.close()


def test_api_verify_ballot_and_chain(running_server):
    base_url, _ = running_server

    # Verify chain
    req_chain = urllib.request.Request(f"{base_url}/api/v1/verify-chain")
    with urllib.request.urlopen(req_chain) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode())
        assert data["valid"] is True
        assert len(data["blocks"]) >= 1

    # Verify audit log
    req_audit = urllib.request.Request(f"{base_url}/api/v1/audit-log")
    with urllib.request.urlopen(req_audit) as resp:
        assert resp.status == 200
        audit_data = json.loads(resp.read().decode())
        assert "events" in audit_data
        assert len(audit_data["events"]) > 0


def test_api_receipt_verification(running_server):
    base_url, ledger = running_server
    priv, pub = generate_keypair()
    vid = public_key_to_hex(pub)
    ledger.register_voter(vid)

    ballot = Ballot(vid, "PROP-2026-02", "YES", weight=1)
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()

    req = urllib.request.Request(
        f"{base_url}/api/v1/ballots",
        data=json.dumps(ballot.to_dict()).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        receipt_hash = res["receipt_hash"]
        assert receipt_hash == ballot.receipt_hash

    # Query verify-ballot using receipt_hash
    req_verify = urllib.request.Request(f"{base_url}/api/v1/verify-ballot?query={receipt_hash}")
    with urllib.request.urlopen(req_verify) as v_resp:
        v_data = json.loads(v_resp.read().decode())
        assert v_data["found"] is True
        assert v_data["receipt_hash"] == receipt_hash
        assert v_data["signature_valid"] is True


def test_api_register_voter_and_immediate_vote(running_server):
    base_url, _ = running_server
    priv, pub = generate_keypair()
    vid = public_key_to_hex(pub)

    # 1. Register voter via /api/v1/register
    reg_req = urllib.request.Request(
        f"{base_url}/api/v1/register",
        data=json.dumps({"voter_id": vid, "name": "Dynamic Test Citizen"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(reg_req) as reg_resp:
        assert reg_resp.status == 200
        reg_data = json.loads(reg_resp.read().decode())
        assert reg_data["status"] == "registered"
        assert reg_data["voter_id"] == vid.lower()

    # 2. Immediately cast a ballot with the registered voter ID
    ballot = Ballot(vid, "PROP-2026-01", "NO", weight=1)
    ballot.signature = sign_message(priv, ballot.get_digest()).hex()

    ballot_req = urllib.request.Request(
        f"{base_url}/api/v1/ballots",
        data=json.dumps(ballot.to_dict()).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(ballot_req) as b_resp:
        assert b_resp.status == 202
        b_data = json.loads(b_resp.read().decode())
        assert b_data["status"] == "accepted"
