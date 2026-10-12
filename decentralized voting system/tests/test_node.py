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
    ledger = Ledger()
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
