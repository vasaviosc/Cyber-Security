from fastapi.testclient import TestClient
from openballot.api_app import app, ledger
from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ballot import Ballot

client = TestClient(app)


def test_fastapi_health_and_metrics():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"

    res_metrics = client.get("/metrics")
    assert res_metrics.status_code == 200
    assert "openballot_chain_height" in res_metrics.text


def test_fastapi_ballot_flow():
    priv, pub = generate_keypair()
    vid = public_key_to_hex(pub)
    ledger.register_voter(vid)

    b = Ballot(voter_id=vid, proposal_id="PROP-FASTAPI", choice="YES")
    sig = sign_message(priv, b.get_digest())

    payload = {
        "voter_id": vid,
        "proposal_id": "PROP-FASTAPI",
        "choice": "YES",
        "signature": sig.hex()
    }

    # Submit ballot
    res = client.post("/api/v1/ballots", json=payload)
    assert res.status_code == 202

    # Mine block
    mine_res = client.post("/api/v1/mine")
    assert mine_res.status_code == 200
    assert mine_res.json()["ballots_sealed"] >= 1

    # Check tally
    tally_res = client.get("/api/v1/tally?proposal=PROP-FASTAPI")
    assert tally_res.status_code == 200
    assert tally_res.json()["results"].get("YES") == 1
