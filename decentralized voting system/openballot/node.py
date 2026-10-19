import json
import logging
import os
import time
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict, Any

from openballot.ballot import Ballot
from openballot.block import Block
from openballot.ledger import Ledger
from openballot.mempool import Mempool
from openballot.consensus import ConsensusEngine

logger = logging.getLogger("openballot.node")


class SecurityEventLogger:
    """
    Security Operations Center (SOC) Event Logger.
    Maintains a high-performance in-memory audit log of authentication attempts,
    integrity checks, consensus decisions, and detected cyber threats.
    """
    def __init__(self, max_events: int = 300):
        self.max_events = max_events
        self.events: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.log(
            category="SYSTEM",
            severity="INFO",
            message="SOC Security Event Audit Subsystem initialized",
            details={"max_events": max_events}
        )

    def log(self, category: str, severity: str, message: str, details: Optional[Dict[str, Any]] = None):
        event = {
            "id": f"SEC-{int(time.time() * 1000)}-{len(self.events) + 1}",
            "timestamp": round(time.time(), 3),
            "iso_time": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "category": category.upper(),   # AUTHENTICATION, INTEGRITY, CONSENSUS, NETWORK, SYSTEM, MINING
            "severity": severity.upper(),   # INFO, WARNING, SUSPICIOUS, CRITICAL
            "message": message,
            "details": details or {}
        }
        with self._lock:
            self.events.insert(0, event)
            if len(self.events) > self.max_events:
                self.events.pop()

    def get_events(self, limit: int = 50, severity: Optional[str] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            res = self.events
            if severity and severity.upper() != "ALL":
                res = [e for e in res if e["severity"] == severity.upper()]
            if category and category.upper() != "ALL":
                res = [e for e in res if e["category"] == category.upper()]
            return list(res[:limit])

    def get_summary(self) -> Dict[str, int]:
        with self._lock:
            counts = {"INFO": 0, "WARNING": 0, "SUSPICIOUS": 0, "CRITICAL": 0, "TOTAL": len(self.events)}
            for e in self.events:
                sev = e.get("severity", "INFO")
                if sev in counts:
                    counts[sev] += 1
            return counts


class NodeServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass, ledger: Ledger, difficulty: int = 1):
        super().__init__(server_address, RequestHandlerClass)
        self.ledger = ledger
        self.mempool = Mempool()
        self.consensus = ConsensusEngine(ledger=self.ledger, difficulty=difficulty)
        self.difficulty = difficulty
        self.peers: List[str] = []
        self.start_time = time.time()
        self.security_logger = SecurityEventLogger()
        if not self.ledger.chain:
            self.ledger.create_genesis_block()
            self.security_logger.log(
                category="CONSENSUS",
                severity="INFO",
                message="Created Genesis block #0",
                details={"prev_hash": self.ledger.chain[0].prev_hash, "hash": self.ledger.chain[0].hash}
            )


class NodeHandler(BaseHTTPRequestHandler):
    @property
    def node(self) -> NodeServer:
        return self.server

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: str, content_type: str):
        if not os.path.exists(file_path):
            return self._send_json({"error": "File not found"}, 404)
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            return self._send_json({"error": f"Failed reading file: {str(e)}"}, 500)

    def _read_json(self) -> Optional[Dict[str, Any]]:
        try:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                return {}
            raw = self.rfile.read(content_len).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            if not path:
                path = "/"

            dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")

            # Static dashboard routes
            if path in ["/", "/index.html", "/dashboard"]:
                index_path = os.path.join(dashboard_dir, "index.html")
                return self._send_file(index_path, "text/html; charset=utf-8")

            elif path.startswith("/static/") or path in ["/app.js", "/style.css"]:
                filename = os.path.basename(path)
                file_path = os.path.join(dashboard_dir, filename)
                ct = "text/plain"
                if filename.endswith(".js"):
                    ct = "application/javascript; charset=utf-8"
                elif filename.endswith(".css"):
                    ct = "text/css; charset=utf-8"
                elif filename.endswith(".html"):
                    ct = "text/html; charset=utf-8"
                elif filename.endswith(".json"):
                    ct = "application/json; charset=utf-8"
                elif filename.endswith(".svg"):
                    ct = "image/svg+xml"
                return self._send_file(file_path, ct)

            # Node Health & SOC Telemetry
            elif path == "/health" or path == "/api/v1/health":
                uptime = round(time.time() - self.node.start_time, 2)
                return self._send_json({
                    "status": "healthy",
                    "uptime_seconds": uptime,
                    "blocks": len(self.node.ledger.chain),
                    "mempool": self.node.mempool.size(),
                    "peers": len(self.node.peers),
                    "difficulty": self.node.difficulty,
                    "total_ballots": self.node.ledger.get_total_ballots(),
                    "security_alerts": self.node.security_logger.get_summary()
                })

            elif path == "/api/v1/stats":
                uptime = round(time.time() - self.node.start_time, 2)
                latest = self.node.ledger.latest_block
                return self._send_json({
                    "node": {
                        "name": "Hexanova OpenBallot SOC Daemon",
                        "status": "ONLINE",
                        "uptime_seconds": uptime,
                        "difficulty": self.node.difficulty,
                        "peer_count": len(self.node.peers)
                    },
                    "blockchain": {
                        "height": len(self.node.ledger.chain),
                        "latest_block_hash": latest.hash if latest else None,
                        "latest_block_index": latest.index if latest else 0,
                        "total_confirmed_ballots": self.node.ledger.get_total_ballots(),
                        "integrity": "VALID" if self.node.consensus.is_valid_chain(self.node.ledger.chain) else "ALERT"
                    },
                    "mempool": {
                        "pending_ballots": self.node.mempool.size()
                    },
                    "security": {
                        "summary": self.node.security_logger.get_summary(),
                        "registered_voters_count": len(self.node.ledger.voter_registry)
                    }
                })

            elif path == "/api/v1/chain":
                chain_data = [b.to_dict() for b in self.node.ledger.chain]
                return self._send_json({"length": len(chain_data), "chain": chain_data})

            elif path == "/api/v1/mempool":
                ballots_data = [b.to_dict() for b in self.node.mempool.all()]
                return self._send_json({"count": len(ballots_data), "ballots": ballots_data})

            elif path == "/api/v1/proposals":
                proposals = self.node.ledger.get_proposals()
                tallies = {p: self.node.ledger.tally(p) for p in proposals}
                return self._send_json({"proposals": proposals, "tallies": tallies})

            elif path == "/api/v1/tally":
                qs = parse_qs(parsed.query)
                proposal = qs.get("proposal", [""])[0].strip()
                if not proposal:
                    return self._send_json({"error": "Missing proposal query parameter"}, 400)
                tally = self.node.ledger.tally(proposal)
                return self._send_json({"proposal": proposal, "results": tally})

            elif path == "/api/v1/peers":
                return self._send_json({"peers": self.node.peers})

            elif path == "/api/v1/security/events":
                qs = parse_qs(parsed.query)
                limit = int(qs.get("limit", [50])[0])
                severity = qs.get("severity", [None])[0]
                category = qs.get("category", [None])[0]
                events = self.node.security_logger.get_events(limit=limit, severity=severity, category=category)
                summary = self.node.security_logger.get_summary()
                return self._send_json({"count": len(events), "summary": summary, "events": events})

            elif path == "/api/v1/voters":
                return self._send_json({
                    "count": len(self.node.ledger.voter_registry),
                    "voters": sorted(list(self.node.ledger.voter_registry))
                })

            else:
                return self._send_json({"error": "Endpoint not found", "path": path}, 404)

        except Exception as e:
            logger.exception("Unhandled error in do_GET: %s", e)
            return self._send_json({"error": f"Internal server error: {str(e)}"}, 500)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            data = self._read_json()

            if data is None:
                return self._send_json({"error": "Invalid JSON payload"}, 400)

            if path == "/api/v1/ballots":
                ballot = Ballot.from_dict(data)

                if not ballot.voter_id or not ballot.proposal_id or not ballot.choice:
                    self.node.security_logger.log(
                        category="AUTHENTICATION",
                        severity="WARNING",
                        message="Ballot rejected: missing required fields",
                        details={"payload": data}
                    )
                    return self._send_json({"error": "Missing required ballot fields"}, 400)

                # 1. Verify digital signature
                if not ballot.verify():
                    self.node.security_logger.log(
                        category="AUTHENTICATION",
                        severity="CRITICAL",
                        message="Cryptographic signature verification failed",
                        details={
                            "voter_id": ballot.voter_id,
                            "proposal_id": ballot.proposal_id,
                            "choice": ballot.choice,
                            "signature_snippet": ballot.signature[:16] + "..." if ballot.signature else "none"
                        }
                    )
                    return self._send_json({
                        "error": "Cryptographic signature verification failed",
                        "code": "INVALID_SIGNATURE"
                    }, 401)

                # 2. Verify voter registration (case-insensitive whitelist)
                if not self.node.ledger.is_registered(ballot.voter_id):
                    self.node.security_logger.log(
                        category="AUTHENTICATION",
                        severity="WARNING",
                        message="Unauthorized voter attempted ballot submission",
                        details={"voter_id": ballot.voter_id, "proposal_id": ballot.proposal_id}
                    )
                    return self._send_json({
                        "error": "Voter ID not in authorized voter registry",
                        "code": "UNAUTHORIZED_VOTER"
                    }, 403)

                # 3. Check if voter already cast ballot on confirmed ledger
                if self.node.ledger.has_voted(ballot.proposal_id, ballot.voter_id):
                    self.node.security_logger.log(
                        category="INTEGRITY",
                        severity="SUSPICIOUS",
                        message="Double-voting attempt detected: voter already confirmed on blockchain",
                        details={"voter_id": ballot.voter_id, "proposal_id": ballot.proposal_id}
                    )
                    return self._send_json({
                        "error": "Voter has already cast a ballot for this proposal",
                        "code": "DOUBLE_VOTE_CONFIRMED"
                    }, 409)

                # 4. Check if voter already has an unconfirmed ballot in the mempool
                if self.node.mempool.has_ballot(ballot.proposal_id, ballot.voter_id):
                    self.node.security_logger.log(
                        category="INTEGRITY",
                        severity="SUSPICIOUS",
                        message="Double-voting attempt detected: unconfirmed ballot already in mempool",
                        details={"voter_id": ballot.voter_id, "proposal_id": ballot.proposal_id}
                    )
                    return self._send_json({
                        "error": "Duplicate ballot already queued in mempool for this proposal",
                        "code": "DOUBLE_VOTE_MEMPOOL"
                    }, 409)

                # Ingest ballot into mempool
                self.node.mempool.add(ballot)
                self.node.security_logger.log(
                    category="INTEGRITY",
                    severity="INFO",
                    message="Ingested verified ballot into mempool",
                    details={"voter_id": ballot.voter_id[:16] + "...", "proposal_id": ballot.proposal_id, "choice": ballot.choice}
                )
                return self._send_json({
                    "status": "accepted",
                    "proposal": ballot.proposal_id,
                    "mempool_size": self.node.mempool.size()
                }, 202)

            elif path == "/api/v1/mine":
                pending = self.node.mempool.drain()
                prev_hash = self.node.ledger.chain[-1].hash if self.node.ledger.chain else ("0" * 64)
                start_mine = time.time()
                new_block = Block(
                    index=len(self.node.ledger.chain),
                    prev_hash=prev_hash,
                    ballots=pending
                )
                new_block.mine(difficulty=self.node.difficulty)
                mine_duration = round(time.time() - start_mine, 4)
                self.node.ledger.chain.append(new_block)

                self.node.security_logger.log(
                    category="MINING",
                    severity="INFO",
                    message=f"Sealed block #{new_block.index} with {len(pending)} ballots",
                    details={
                        "block_index": new_block.index,
                        "block_hash": new_block.hash,
                        "ballots_sealed": len(pending),
                        "duration_sec": mine_duration,
                        "nonce": new_block.nonce
                    }
                )
                return self._send_json({
                    "status": "mined",
                    "block_index": new_block.index,
                    "block_hash": new_block.hash,
                    "nonce": new_block.nonce,
                    "ballots_sealed": len(pending),
                    "duration_seconds": mine_duration
                })

            elif path == "/api/v1/voters/register":
                voter_id = data.get("voter_id", "").strip()
                if not voter_id:
                    return self._send_json({"error": "Missing voter_id"}, 400)
                self.node.ledger.register_voter(voter_id)
                self.node.security_logger.log(
                    category="AUTHENTICATION",
                    severity="INFO",
                    message="Registered authorized voter ID",
                    details={"voter_id": voter_id[:16] + "..."}
                )
                return self._send_json({
                    "status": "registered",
                    "voter_id": voter_id,
                    "total_registered": len(self.node.ledger.voter_registry)
                })

            elif path == "/api/v1/peers":
                peer = data.get("peer")
                if peer and peer not in self.node.peers:
                    self.node.peers.append(peer)
                    self.node.security_logger.log(
                        category="NETWORK",
                        severity="INFO",
                        message=f"Registered new peer node: {peer}",
                        details={"peer": peer}
                    )
                return self._send_json({"peers": self.node.peers})

            elif path == "/api/v1/sync":
                candidate_raw = data.get("chain", [])
                if not candidate_raw:
                    return self._send_json({"error": "Empty chain provided"}, 400)
                try:
                    candidate = [Block.from_dict(b) for b in candidate_raw]
                except Exception as e:
                    self.node.security_logger.log(
                        category="CONSENSUS",
                        severity="WARNING",
                        message="Malformed candidate chain rejected during sync",
                        details={"error": str(e)}
                    )
                    return self._send_json({"error": f"Invalid block format: {e}"}, 400)

                replaced = self.node.consensus.resolve_conflicts([candidate])
                if replaced:
                    self.node.security_logger.log(
                        category="CONSENSUS",
                        severity="WARNING",
                        message="Chain fork resolved: adopted longer peer chain",
                        details={"new_height": len(self.node.ledger.chain)}
                    )
                return self._send_json({
                    "chain_replaced": replaced,
                    "current_length": len(self.node.ledger.chain)
                })

            elif path == "/api/v1/security/simulate":
                attack_type = data.get("type", "signature_tamper")
                if attack_type == "signature_tamper":
                    self.node.security_logger.log(
                        category="AUTHENTICATION",
                        severity="CRITICAL",
                        message="[SIMULATION] Blocked forged cryptographic signature on ballot",
                        details={"attack_vector": "Ed25519 Forgery Simulation", "defense": "verify_signature() rejected"}
                    )
                    return self._send_json({
                        "simulation": "signature_tamper",
                        "status": "BLOCKED",
                        "code": "INVALID_SIGNATURE",
                        "defense": "Cryptographic signature validation rejected forged ballot payload."
                    })
                elif attack_type == "double_vote":
                    self.node.security_logger.log(
                        category="INTEGRITY",
                        severity="SUSPICIOUS",
                        message="[SIMULATION] Blocked double-voting replay attempt",
                        details={"attack_vector": "Mempool / Blockchain Double-Vote Injection", "defense": "has_voted() returned True"}
                    )
                    return self._send_json({
                        "simulation": "double_vote",
                        "status": "BLOCKED",
                        "code": "DOUBLE_VOTE_DETECTED",
                        "defense": "Mempool & Ledger duplicate verification prevented double-vote replay."
                    })
                elif attack_type == "fork_poisoning":
                    self.node.security_logger.log(
                        category="CONSENSUS",
                        severity="CRITICAL",
                        message="[SIMULATION] Rejected invalid peer chain with non-sequential index and corrupted hash",
                        details={"attack_vector": "Rogue Peer Fork Injection", "defense": "is_valid_chain() returned False"}
                    )
                    return self._send_json({
                        "simulation": "fork_poisoning",
                        "status": "BLOCKED",
                        "code": "INVALID_PEER_CHAIN",
                        "defense": "Consensus validation detected continuity violation and aborted chain adoption."
                    })
                else:
                    return self._send_json({"error": f"Unknown simulation type: {attack_type}"}, 400)

            else:
                return self._send_json({"error": "Endpoint not found", "path": path}, 404)

        except Exception as e:
            logger.exception("Unhandled error in do_POST: %s", e)
            return self._send_json({"error": f"Internal server error: {str(e)}"}, 500)

    def log_message(self, format, *args):
        # Silence default stderr logging for clean test runs
        return
