import json
import urllib.request

from openballot.citizens import CitizenManager


def test_citizen_creation_and_keypair():
    cm = CitizenManager()
    citizen = cm.create_citizen(name="Maya Lin", district="Architecture Precinct")
    assert citizen.name == "Maya Lin"
    assert citizen.district == "Architecture Precinct"
    assert len(citizen.voter_id) == 64
    assert len(citizen.secret_key) == 64

    # Fetch back
    fetched = cm.get(citizen.voter_id)
    assert fetched is not None
    assert fetched.name == "Maya Lin"


def test_api_create_and_list_citizen(running_server):
    base_url, ledger = running_server

    # 1. Create Citizen via POST /api/v1/citizens
    payload = json.dumps({"name": "Elena Rostova", "district": "Physics Ward"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/citizens",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        data = json.loads(resp.read().decode())
        assert data["status"] == "created"
        assert data["citizen"]["name"] == "Elena Rostova"
        assert data["citizen"]["district"] == "Physics Ward"
        assert len(data["citizen"]["voter_id"]) == 64
        assert len(data["citizen"]["secret_key"]) == 64
        voter_id = data["citizen"]["voter_id"]

    # Verify citizen was automatically whitelisted in ledger
    assert ledger.is_registered(voter_id)

    # 2. Verify citizen appears in GET /api/v1/citizens
    req_get = urllib.request.Request(f"{base_url}/api/v1/citizens")
    with urllib.request.urlopen(req_get) as resp_get:
        assert resp_get.status == 200
        get_data = json.loads(resp_get.read().decode())
        assert "citizens" in get_data
        matches = [c for c in get_data["citizens"] if c["voter_id"] == voter_id]
        assert len(matches) == 1
        assert matches[0]["authorized"] is True


def test_api_bulk_citizen_generation(running_server):
    base_url, ledger = running_server

    payload = json.dumps({"count": 5, "district": "District Tech"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/citizens/bulk",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        data = json.loads(resp.read().decode())
        assert data["status"] == "bulk_created"
        assert data["count"] == 5
        assert len(data["citizens"]) == 5
        for c in data["citizens"]:
            assert ledger.is_registered(c["voter_id"])


def test_api_create_custom_election(running_server):
    base_url, _ = running_server

    election_payload = json.dumps({
        "proposal_id": "PROP-2026-99",
        "title": "Solar Canopy Campus Initiative",
        "description": "Student referendum to construct solar shades over campus parking lots.",
        "category": "Sustainability",
        "choices": ["APPROVE", "REJECT", "ABSTAIN"]
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/api/v1/elections",
        data=election_payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 201
        data = json.loads(resp.read().decode())
        assert data["status"] == "created"
        assert data["election"]["proposal_id"] == "PROP-2026-99"
        assert data["election"]["choices"] == ["APPROVE", "REJECT", "ABSTAIN"]


def test_api_security_attack_simulation(running_server):
    base_url, _ = running_server

    # Test all 4 attack vectors
    attacks = ["DOUBLE_VOTE", "UNAUTHORIZED_VOTER", "SIGNATURE_TAMPER", "WEIGHT_TAMPER"]
    expected_codes = {
        "DOUBLE_VOTE": 409,
        "UNAUTHORIZED_VOTER": 403,
        "SIGNATURE_TAMPER": 401,
        "WEIGHT_TAMPER": 400
    }

    for atk in attacks:
        payload = json.dumps({"attack_type": atk, "proposal_id": "PROP-2026-01"}).encode()
        req = urllib.request.Request(
            f"{base_url}/api/v1/security/simulate-attack",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data["blocked"] is True
            assert data["status_code"] == expected_codes[atk]
            assert "layer" in data
            assert "security_defense" in data
