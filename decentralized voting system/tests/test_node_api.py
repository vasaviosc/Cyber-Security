import json
import threading
import time
import urllib.request
import urllib.error
from openballot.crypto import generate_keypair, public_key_to_hex, private_key_to_hex, sign_message
from openballot.ballot import Ballot
from openballot.ledger import Ledger
from openballot.node import NodeServer, NodeHandler


def _http_get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _http_post(url, data):
    raw = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=raw, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def test_node_http_api_endpoints():
    ledger = Ledger()
    ledger.create_genesis_block()

    priv, pub = generate_keypair()
    voter_id = public_key_to_hex(pub)
    ledger.register_voter(voter_id)

    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)

    try:
        # 1. /health
        status, res = _http_get(f"{base_url}/health")
        assert status == 200
        assert res["status"] == "healthy"
        assert res["blocks"] == 1
        assert res["mempool"] == 0

        # 2. /api/v1/voters GET & POST
        status, res = _http_get(f"{base_url}/api/v1/voters")
        assert status == 200
        assert voter_id in res["registered_voters"]

        priv2, pub2 = generate_keypair()
        voter_id2 = public_key_to_hex(pub2)
        status, res = _http_post(f"{base_url}/api/v1/voters", {"voter_id": voter_id2})
        assert status == 200
        assert res["added"] == 1

        # 3. /api/v1/ballots POST (Valid vote)
        b = Ballot(voter_id=voter_id, proposal_id="PROP-ELECTION-1", choice="YES")
        sig = sign_message(priv, b.get_digest())
        b.signature = sig.hex()

        status, res = _http_post(f"{base_url}/api/v1/ballots", b.to_dict())
        assert status == 202
        assert res["status"] == "accepted"

        # 4. Duplicate vote attempt in mempool -> 409 Conflict
        status, res = _http_post(f"{base_url}/api/v1/ballots", b.to_dict())
        assert status == 409
        assert "mempool" in res["error"]

        # 5. Invalid signature vote attempt -> 401 Unauthorized
        b_bad = Ballot(voter_id=voter_id2, proposal_id="PROP-ELECTION-1", choice="NO", signature="deadbeef" * 8)
        status, res = _http_post(f"{base_url}/api/v1/ballots", b_bad.to_dict())
        assert status == 401

        # 6. Vote for voter_id2
        b2 = Ballot(voter_id=voter_id2, proposal_id="PROP-ELECTION-1", choice="NO")
        b2.signature = sign_message(priv2, b2.get_digest()).hex()
        status, res = _http_post(f"{base_url}/api/v1/ballots", b2.to_dict())
        assert status == 202

        # Check mempool
        status, res = _http_get(f"{base_url}/api/v1/mempool")
        assert status == 200
        assert res["count"] == 2

        # 7. Mine block
        status, res = _http_post(f"{base_url}/api/v1/mine", {})
        assert status == 200
        assert res["block_index"] == 1
        assert res["ballots_sealed"] == 2

        # 8. Check tally
        status, res = _http_get(f"{base_url}/api/v1/tally?proposal=PROP-ELECTION-1")
        assert status == 200
        assert res["results"] == {"YES": 1, "NO": 1}

        # 9. Verify vote inclusion
        status, res = _http_get(f"{base_url}/api/v1/ballots/verify?voter_id={voter_id}&proposal=PROP-ELECTION-1")
        assert status == 200
        assert res["status"] == "confirmed"
        assert res["vote"]["choice"] == "YES"

        # 10. Proposals overview
        status, res = _http_get(f"{base_url}/api/v1/proposals")
        assert status == 200
        assert len(res["proposals"]) == 1
        assert res["proposals"][0]["proposal_id"] == "PROP-ELECTION-1"

        # 11. Duplicate vote on ledger attempt -> 409 Conflict
        b_dup = Ballot(voter_id=voter_id, proposal_id="PROP-ELECTION-1", choice="NO")
        b_dup.signature = sign_message(priv, b_dup.get_digest()).hex()
        status, res = _http_post(f"{base_url}/api/v1/ballots", b_dup.to_dict())
        assert status == 409
        assert "ledger" in res["error"]
    finally:
        server.shutdown()
        server.server_close()
