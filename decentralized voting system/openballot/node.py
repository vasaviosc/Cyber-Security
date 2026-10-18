import json
import logging
import socketserver
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict, Any

from openballot.ballot import Ballot
from openballot.block import Block
from openballot.ledger import Ledger
from openballot.mempool import Mempool
from openballot.consensus import ConsensusEngine

logger = logging.getLogger("openballot.node")


def _post_peer_json(url: str, payload: dict, timeout: float = 2.0):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


class NodeServer(socketserver.ThreadingMixIn, HTTPServer):
    """
    Multi-threaded asynchronous HTTP server daemon with automatic P2P gossip propagation.
    """
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, ledger: Ledger, difficulty: int = 1):
        super().__init__(server_address, RequestHandlerClass)
        self.ledger = ledger
        self.mempool = Mempool()
        self.consensus = ConsensusEngine(ledger=self.ledger, difficulty=difficulty)
        self.difficulty = difficulty
        self.peers: List[str] = []
        if not self.ledger.chain:
            self.ledger.create_genesis_block()

    def broadcast_ballot(self, ballot: Ballot):
        """
        Asynchronously gossips a newly submitted ballot to all registered peers.
        """
        if not self.peers:
            return
        payload = ballot.to_dict()

        def _worker():
            for peer in list(self.peers):
                endpoint = f"{peer.rstrip('/')}/api/v1/ballots"
                _post_peer_json(endpoint, payload, timeout=1.5)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()

    def broadcast_block(self, new_block: Block):
        """
        Asynchronously gossips newly mined blocks to all peers for network consensus sync.
        """
        if not self.peers:
            return
        payload = {"chain": [b.to_dict() for b in self.ledger.chain]}

        def _worker():
            for peer in list(self.peers):
                endpoint = f"{peer.rstrip('/')}/api/v1/sync"
                _post_peer_json(endpoint, payload, timeout=2.5)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()


class NodeHandler(BaseHTTPRequestHandler):
    @property
    def node(self) -> NodeServer:
        return self.server

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain"):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Optional[Dict[str, Any]]:
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                return {}
            raw = self.rfile.read(content_len).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            return self._send_json({
                "status": "healthy",
                "blocks": len(self.node.ledger.chain),
                "mempool": self.node.mempool.size(),
                "peers": len(self.node.peers),
                "registered_voters": len(self.node.ledger.voter_registry)
            })

        elif path == "/metrics":
            # Prometheus monitoring metrics endpoint
            metrics = [
                "# HELP openballot_chain_height Total blocks in ledger",
                "# TYPE openballot_chain_height gauge",
                f"openballot_chain_height {len(self.node.ledger.chain)}",
                "# HELP openballot_mempool_size Total pending unconfirmed ballots",
                "# TYPE openballot_mempool_size gauge",
                f"openballot_mempool_size {self.node.mempool.size()}",
                "# HELP openballot_registered_voters Total authorized voters",
                "# TYPE openballot_registered_voters gauge",
                f"openballot_registered_voters {len(self.node.ledger.voter_registry)}",
                "# HELP openballot_peers_count Total connected peer nodes",
                "# TYPE openballot_peers_count gauge",
                f"openballot_peers_count {len(self.node.peers)}"
            ]
            return self._send_text("\n".join(metrics) + "\n", 200, "text/plain; version=0.0.4")

        elif path == "/api/v1/chain":
            chain_data = [b.to_dict() for b in self.node.ledger.chain]
            return self._send_json({"length": len(chain_data), "chain": chain_data})

        elif path == "/api/v1/mempool":
            ballots_data = [b.to_dict() for b in self.node.mempool.all()]
            return self._send_json({"count": len(ballots_data), "ballots": ballots_data})

        elif path == "/api/v1/tally":
            qs = parse_qs(parsed.query)
            proposal = qs.get("proposal", [""])[0]
            if not proposal:
                return self._send_json({"error": "Missing proposal query parameter"}, 400)
            tally = self.node.ledger.tally(proposal)
            return self._send_json({"proposal": proposal.strip().upper(), "results": tally})

        elif path == "/api/v1/proposals":
            proposals = self.node.ledger.get_proposals()
            return self._send_json({"proposals": proposals})

        elif path == "/api/v1/snapshot":
            # Fast snapshot sync endpoint
            return self._send_json({
                "height": len(self.node.ledger.chain),
                "latest_block_hash": self.node.ledger.latest_block.hash,
                "tallies": self.node.ledger.get_proposals(),
                "registered_voters_count": len(self.node.ledger.voter_registry)
            })

        elif path == "/api/v1/ballots/verify":
            qs = parse_qs(parsed.query)
            voter_id = qs.get("voter_id", [""])[0]
            proposal = qs.get("proposal", [""])[0]
            if not voter_id or not proposal:
                return self._send_json({"error": "Missing voter_id or proposal query parameters"}, 400)

            vote_info = self.node.ledger.get_vote(proposal, voter_id)
            if vote_info:
                return self._send_json({"status": "confirmed", "vote": vote_info})
            elif self.node.mempool.has_voter_submitted(proposal, voter_id):
                return self._send_json({"status": "pending_in_mempool", "proposal": proposal, "voter_id": voter_id})
            else:
                return self._send_json({"status": "not_found", "message": "No ballot found for this voter and proposal"}, 404)

        elif path == "/api/v1/voters":
            return self._send_json({
                "count": len(self.node.ledger.voter_registry),
                "open_policy": len(self.node.ledger.voter_registry) == 0,
                "registered_voters": sorted(list(self.node.ledger.voter_registry))
            })

        elif path == "/api/v1/peers":
            return self._send_json({"peers": self.node.peers})

        else:
            return self._send_json({"error": "Endpoint not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()

        if data is None:
            return self._send_json({"error": "Invalid JSON payload"}, 400)

        if path == "/api/v1/ballots":
            ballot = Ballot.from_dict(data)

            if not ballot.voter_id or not ballot.proposal_id or not ballot.choice:
                return self._send_json({"error": "Missing required ballot fields"}, 400)

            # 1. Verify digital signature
            if not ballot.verify():
                return self._send_json({"error": "Cryptographic signature verification failed"}, 401)

            # 2. Verify voter registration (case-insensitive whitelist)
            if not self.node.ledger.is_registered(ballot.voter_id):
                return self._send_json({"error": "Voter ID not in authorized voter registry"}, 403)

            # 3. Check if voter already cast ballot on confirmed ledger (O(1))
            if self.node.ledger.has_voted(ballot.proposal_id, ballot.voter_id):
                return self._send_json({"error": "Voter has already cast a ballot for this proposal on ledger"}, 409)

            # 4. Check if voter already has a pending ballot in mempool (O(1))
            if self.node.mempool.has_voter_submitted(ballot.proposal_id, ballot.voter_id):
                return self._send_json({"error": "Voter has already submitted a pending ballot for this proposal in mempool"}, 409)

            # Ingest ballot into mempool
            accepted = self.node.mempool.add(ballot)
            if not accepted:
                return self._send_json({"error": "Failed to add ballot to mempool"}, 400)

            # Automatically gossip ballot to network peers
            self.node.broadcast_ballot(ballot)
            return self._send_json({"status": "accepted", "proposal": ballot.proposal_id}, 202)

        elif path == "/api/v1/voters":
            voter_id = data.get("voter_id")
            voter_ids = data.get("voter_ids", [])
            added = 0
            if voter_id:
                self.node.ledger.register_voter(voter_id)
                added += 1
            for vid in voter_ids:
                self.node.ledger.register_voter(vid)
                added += 1

            if self.node.ledger.storage_path:
                self.node.ledger.save_to_file()

            return self._send_json({
                "status": "success",
                "added": added,
                "total_registered": len(self.node.ledger.voter_registry)
            })

        elif path == "/api/v1/mine":
            pending = self.node.mempool.drain()
            
            # Deduplicate intra-mempool ballots
            unique_ballots = []
            seen = set()
            for b in pending:
                key = (b.proposal_id, b.voter_id)
                if key not in seen and not self.node.ledger.has_voted(b.proposal_id, b.voter_id):
                    seen.add(key)
                    unique_ballots.append(b)

            new_block = Block(
                index=len(self.node.ledger.chain),
                prev_hash=self.node.ledger.chain[-1].hash,
                ballots=unique_ballots
            )
            new_block.mine(difficulty=self.node.difficulty)
            self.node.ledger.append_block(new_block)

            if self.node.ledger.storage_path:
                self.node.ledger.save_to_file()

            # Automatically gossip new block to network peers
            self.node.broadcast_block(new_block)

            return self._send_json({
                "status": "mined",
                "block_index": new_block.index,
                "block_hash": new_block.hash,
                "merkle_root": new_block.merkle_root,
                "ballots_sealed": len(unique_ballots)
            })

        elif path == "/api/v1/peers":
            peer = data.get("peer")
            if peer and peer not in self.node.peers:
                self.node.peers.append(peer)
            return self._send_json({"peers": self.node.peers})

        elif path == "/api/v1/sync":
            candidate_raw = data.get("chain", [])
            if not candidate_raw:
                return self._send_json({"error": "Empty chain provided"}, 400)
            try:
                candidate = [Block.from_dict(b) for b in candidate_raw]
            except Exception as e:
                return self._send_json({"error": f"Invalid block format: {e}"}, 400)

            replaced = self.node.consensus.resolve_conflicts([candidate])
            return self._send_json({
                "chain_replaced": replaced,
                "current_length": len(self.node.ledger.chain)
            })

        else:
            return self._send_json({"error": "Endpoint not found"}, 404)

    def log_message(self, format, *args):
        return
