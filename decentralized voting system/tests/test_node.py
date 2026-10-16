import json
import threading
import urllib.error
import urllib.request

import pytest

from openballot.ballot import Ballot
from openballot.block import Block
from openballot.crypto import generate_keypair, public_key_to_hex, sign_message
from openballot.ledger import Ledger
from openballot.node import NodeHandler, NodeServer


@pytest.fixture
def running_node():
    ledger = Ledger(open_election=True)
    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", ledger
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _post(base_url, path, payload):
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def _signed_ballot(private_key, voter_id, proposal_id="PROP-1"):
    ballot = Ballot(voter_id, proposal_id, "YES")
    ballot.signature = sign_message(private_key, ballot.get_digest()).hex()
    return ballot.to_dict()


def test_duplicate_pending_and_case_variant_confirmed_ballots_are_rejected(running_node):
    base_url, ledger = running_node
    private_key, public_key = generate_keypair()
    voter_id = public_key_to_hex(public_key)

    first_status, _ = _post(
        base_url,
        "/api/v1/ballots",
        _signed_ballot(private_key, voter_id),
    )
    duplicate_status, _ = _post(
        base_url,
        "/api/v1/ballots",
        _signed_ballot(private_key, voter_id),
    )
    assert first_status == 202
    assert duplicate_status == 409

    mine_status, _ = _post(base_url, "/api/v1/mine", {})
    assert mine_status == 200

    alias_status, _ = _post(
        base_url,
        "/api/v1/ballots",
        _signed_ballot(private_key, voter_id.upper()),
    )
    assert alias_status == 409

    other_proposal_status, _ = _post(
        base_url,
        "/api/v1/ballots",
        _signed_ballot(private_key, voter_id, proposal_id="PROP-2"),
    )
    assert other_proposal_status == 202
    assert ledger.tally("PROP-1") == {"YES": 1}


def test_non_object_json_request_is_rejected(running_node):
    base_url, _ = running_node

    status, response = _post(base_url, "/api/v1/ballots", [])

    assert status == 400
    assert response["error"] == "JSON payload must be an object"


def test_invalid_ballot_field_type_is_rejected(running_node):
    base_url, _ = running_node
    private_key, public_key = generate_keypair()
    ballot = _signed_ballot(private_key, public_key_to_hex(public_key))
    ballot["weight"] = "not-an-integer"

    status, response = _post(base_url, "/api/v1/ballots", ballot)

    assert status == 400
    assert response["error"] == "Invalid ballot format"


def test_sync_rejects_untrusted_genesis_without_tallying_its_ballot(running_node):
    base_url, ledger = running_node
    attacker_ballot = Ballot("attacker", "PROP-ATTACK", "YES", weight=50)
    genesis = Block(
        index=0,
        prev_hash="untrusted",
        ballots=[attacker_ballot],
        timestamp=1700000001.0,
    )
    block1 = Block(index=1, prev_hash=genesis.hash, ballots=[])
    block1.mine(difficulty=1)
    block2 = Block(index=2, prev_hash=block1.hash, ballots=[])
    block2.mine(difficulty=1)

    status, response = _post(
        base_url,
        "/api/v1/sync",
        {"chain": [genesis.to_dict(), block1.to_dict(), block2.to_dict()]},
    )

    assert status == 200
    assert response["chain_replaced"] is False
    assert len(ledger.chain) == 1
    assert ledger.tally("PROP-ATTACK") == {}


def test_admin_token_protection():
    ledger = Ledger(open_election=True)
    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1, admin_token="test-secret-token")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    try:
        # 1. Unauthenticated admin requests should fail with 401
        for path in ["/api/v1/mine", "/api/v1/peers", "/api/v1/sync"]:
            status, res = _post(base_url, path, {})
            assert status == 401, f"{path} should return 401 without token"
            assert "Unauthorized" in res.get("error", "")

        # GET /api/v1/citizens and /api/v1/peers should fail with 401
        for path in ["/api/v1/citizens", "/api/v1/peers"]:
            req = urllib.request.Request(base_url + path)
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            assert exc.value.code == 401
            exc.value.close()

        # 2. Authenticated request with Bearer token succeeds
        req_auth = urllib.request.Request(
            base_url + "/api/v1/peers",
            headers={"Authorization": "Bearer test-secret-token"}
        )
        with urllib.request.urlopen(req_auth) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert "peers" in data

        # 3. Authenticated request with X-Admin-Token succeeds
        req_custom = urllib.request.Request(
            base_url + "/api/v1/mine",
            data=b"{}",
            headers={"Content-Type": "application/json", "X-Admin-Token": "test-secret-token"}
        )
        with urllib.request.urlopen(req_custom) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert data.get("status") == "mined"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_cors_localhost_only(running_node):
    base_url, _ = running_node

    # Untrusted external origin
    req_evil = urllib.request.Request(
        f"{base_url}/health",
        headers={"Origin": "https://malicious-site.example"}
    )
    with urllib.request.urlopen(req_evil) as resp:
        assert "Access-Control-Allow-Origin" not in resp.headers

    # Localhost origin allowed
    req_local = urllib.request.Request(
        f"{base_url}/health",
        headers={"Origin": "http://localhost:3000"}
    )
    with urllib.request.urlopen(req_local) as resp:
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    # 127.0.0.1 origin allowed
    req_ip = urllib.request.Request(
        f"{base_url}/health",
        headers={"Origin": "http://127.0.0.1:8080"}
    )
    with urllib.request.urlopen(req_ip) as resp:
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8080"


def test_peer_url_ssrf_validation(running_node):
    base_url, _ = running_node

    # 1. Non-http/https schemes should be rejected
    status, res = _post(base_url, "/api/v1/peers", {"peer": "ftp://example.com/chain"})
    assert status == 400
    assert "Invalid peer URL" in res.get("error", "")

    # 2. Localhost should be rejected
    status, res = _post(base_url, "/api/v1/peers", {"peer": "http://localhost:8000"})
    assert status == 400
    assert "Invalid peer URL" in res.get("error", "")

    # 3. Private and loopback IP ranges should be rejected
    for private_peer in [
        "http://127.0.0.1:9000",
        "http://192.168.1.100:8000",
        "http://10.0.0.5:8000",
        "http://172.16.0.1:8000",
        "http://169.254.169.254/latest"
    ]:
        status, res = _post(base_url, "/api/v1/peers", {"peer": private_peer})
        assert status == 400, f"{private_peer} should be rejected"
        assert "Invalid peer URL" in res.get("error", "")


def test_sync_rejects_unregistered_voter_on_pushed_chain():
    # Node with closed registry: only registered voters allowed
    ledger = Ledger(open_election=False)
    ledger.create_genesis_block()
    priv_reg, pub_reg = generate_keypair()
    reg_voter = public_key_to_hex(pub_reg)
    ledger.register_voter(reg_voter)

    server = NodeServer(("127.0.0.1", 0), NodeHandler, ledger=ledger, difficulty=1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        # Attacker crafts a longer chain from the node's genesis containing an unregistered voter
        priv_unreg, pub_unreg = generate_keypair()
        unreg_voter = public_key_to_hex(pub_unreg)
        unreg_ballot = Ballot(voter_id=unreg_voter, proposal_id="PROP-INFILTRATE", choice="YES", weight=1)
        unreg_ballot.signature = sign_message(priv_unreg, unreg_ballot.get_digest()).hex()

        genesis_dict = ledger.chain[0].to_dict()
        block1 = Block(index=1, prev_hash=ledger.chain[0].hash, ballots=[unreg_ballot])
        block1.mine(difficulty=1)
        block2 = Block(index=2, prev_hash=block1.hash, ballots=[])
        block2.mine(difficulty=1)

        candidate_chain = [genesis_dict, block1.to_dict(), block2.to_dict()]
        status, response = _post(base_url, "/api/v1/sync", {"chain": candidate_chain})

        assert status == 200
        assert response["chain_replaced"] is False
        assert len(ledger.chain) == 1
        assert ledger.tally("PROP-INFILTRATE") == {}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_concurrent_mine_requests(running_node):
    base_url, ledger = running_node
    import concurrent.futures

    # Cast 4 unique ballots
    for i in range(4):
        priv, pub = generate_keypair()
        vid = public_key_to_hex(pub)
        ballot = _signed_ballot(priv, vid, proposal_id=f"PROP-CONCURRENT-{i}")
        status, _ = _post(base_url, "/api/v1/ballots", ballot)
        assert status == 202

    # Send 10 concurrent /mine requests across multiple threads
    def mine_worker():
        s, r = _post(base_url, "/api/v1/mine", {})
        return s, r

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(mine_worker) for _ in range(8)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # All requests should return 200 without deadlock
    assert all(status == 200 for status, _ in results)

    # Ballots should all be sealed on the ledger without duplicate counting
    total_sealed = sum(len(block.ballots) for block in ledger.chain)
    assert total_sealed == 4


def test_secrets_strictly_absent_from_all_api_responses(running_node):
    base_url, _ = running_node

    # Helper to check no secret_key in text
    def assert_no_secret_key(raw_bytes: bytes, context: str):
        text = raw_bytes.decode("utf-8")
        assert "secret_key" not in text, f"Found secret_key in {context} response: {text}"

    # 1. Health
    with urllib.request.urlopen(f"{base_url}/health") as resp:
        assert_no_secret_key(resp.read(), "health")

    # 2. Create Citizen
    c_status, c_data = _post(base_url, "/api/v1/citizens", {"name": "Security Test Citizen", "district": "District 1"})
    assert c_status == 201
    assert "secret_key" not in c_data
    assert "secret_key" not in c_data.get("citizen", {})

    # 3. Citizens List
    with urllib.request.urlopen(f"{base_url}/api/v1/citizens") as resp:
        assert_no_secret_key(resp.read(), "GET /citizens")

    # 4. Bulk Citizens Generation
    b_status, b_data = _post(base_url, "/api/v1/citizens/bulk", {"count": 3, "district": "Precinct X"})
    assert b_status == 201
    for c in b_data.get("citizens", []):
        assert "secret_key" not in c

    # 5. Voters List
    with urllib.request.urlopen(f"{base_url}/api/v1/voters") as resp:
        assert_no_secret_key(resp.read(), "GET /voters")

    # 6. Chain
    with urllib.request.urlopen(f"{base_url}/api/v1/chain") as resp:
        assert_no_secret_key(resp.read(), "GET /chain")

    # 7. Mempool
    with urllib.request.urlopen(f"{base_url}/api/v1/mempool") as resp:
        assert_no_secret_key(resp.read(), "GET /mempool")



