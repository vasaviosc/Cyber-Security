# Hexanova Cybersecurity SOC Dashboard — OpenBallot 🛡️🗳️

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](pyproject.toml)
[![Tests: 28 Passing](https://img.shields.io/badge/tests-28%20passing-success.svg)](tests/)
[![Security: Hardened](https://img.shields.io/badge/security-hardened-00f2fe.svg)](#security-fixes-and-stabilization)

A high-assurance, decentralized cryptographic voting node and Security Operations Center (SOC) dashboard engineered for tamper-evident digital governance, live threat mitigation, and auditable consensus.

---

## Academic Project & Team Information

- **Project Name:** Cyber-Security Dashboard (OpenBallot SOC)
- **Institution:** Vasavi College of Engineering (Affiliated to Osmania University)
- **Department:** Department of Computer Science and Engineering (CSE)
- **Team Name:** **HEXANOVA**

### Team Members
1. **Vishnu Vardhan** — Roll No: `1602-25-733-064`
2. **Sri Vatsav** — Roll No: `1602-25-733-052`
3. **Teja** — Roll No: `1602-25-733-056`

---

## System Overview & Architecture

Hexanova OpenBallot combines an immutable Proof-of-Work blockchain with an embedded, real-time Security Operations Center (SOC) Dashboard. Voter identities and votes are cryptographically verified using **Ed25519** asymmetric digital signatures, validated against mempool double-voting and cross-proposal replay attacks, and sealed into sequentially validated blocks.

```
                  +----------------------------------------------+
                  |  Hexanova SOC Cybersecurity Dashboard (Web)  |
                  |  [Live Telemetry | Explorer | Threat Logs]   |
                  +----------------------------------------------+
                                         |
                                (HTTP / REST + CORS)
                                         v
   [ Voter CLI ]  ======>>   [ Node Daemon (node.py) ]  <<======  [ Peer Nodes ]
 (Ed25519 Sign)              |  - Security Audit Log |           (Consensus Sync)
                             |  - CORS & OPTIONS     |
                             |  - Mempool Inspector  |
                             +-----------------------+
                                         |
                       +-----------------+-----------------+
                       v                                   v
             [ Ingest Mempool ]                  [ Consensus Engine ]
             - Duplicate check                   - Genesis check
             - Signature check                   - Sequence continuity
             - Voter whitelist                   - Fork resolution
                       |                                   |
                       +-----------------+-----------------+
                                         v
                            +--------------------------+
                            |     Blockchain Ledger    |
                            | [Genesis]<-[B1]<-[B2]... |
                            +--------------------------+
                                         |
                                         v
                                [ Tally Engine (PoW) ]
```

---

## Security Fixes and Stabilization

Hexanova conducted an extensive security audit and stabilized the entire codebase:

1. **Cross-Proposal Replay Attack Elimination (`openballot/ballot.py`):**
   - *Bug:* The original digest serialization only signed `voter_id:choice:weight`, leaving `proposal_id` unbound. An attacker could take a valid signature from Proposal A and replay it onto Proposal B.
   - *Fix:* Cryptographic digest now binds `f"{self.proposal_id}:{self.voter_id.lower()}:{self.choice}:{self.weight}"`, eliminating cross-proposal replay attacks while retaining backward-compatible verification for legacy ballots.

2. **Mempool Double-Voting & Denial-of-Service Defense (`openballot/mempool.py` & `openballot/node.py`):**
   - *Bug:* Mempool accepted duplicate ballots from the same voter for the same proposal before block mining, inflating tally weights.
   - *Fix:* Implemented thread-safe duplicate detection on `(proposal_id, voter_id)` in the mempool and added strict HTTP 409 rejection if an unconfirmed ballot is already queued.

3. **Consensus Engine Sequence & Genesis Validation (`openballot/consensus.py`):**
   - *Bug:* Peer chains were checked only from block 1 onwards; block 0 (Genesis), sequential indexing (`curr.index == prev.index + 1`), and chronological timestamps were not enforced.
   - *Fix:* Complete structural verification of Genesis block, monotonic timestamp ordering, strict sequential heights, and chain-wide double-voting prevention.

4. **CORS & Preflight Compliance (`openballot/node.py`):**
   - *Bug:* Browsers were blocked from communicating with the node API due to missing CORS headers and lack of `OPTIONS` preflight handling.
   - *Fix:* Implemented full CORS headers (`Access-Control-Allow-Origin: *`, `Methods`, `Headers`) and automated `do_OPTIONS` handler.

5. **Integrated SOC Cybersecurity Dashboard (`openballot/dashboard/`):**
   - *Bug:* Running the daemon returned `404 Endpoint not found` upon visiting `http://127.0.0.1:8000/`.
   - *Fix:* Engineered and integrated a responsive SOC Dashboard served directly at `/`, `/index.html`, `/dashboard`, and `/static/*`.

6. **Real-time Threat & Security Audit Log Subsystem (`openballot/node.py`):**
   - In-memory circular event buffer tracking security events with severity classifications (`CRITICAL`, `SUSPICIOUS`, `WARNING`, `INFO`).

7. **Data Canonicalization & Precision Consistency (`openballot/ledger.py` & `openballot/block.py`):**
   - Fixed case-sensitivity mismatch (`.strip().lower()`) across voter registries and confirmed ledgers.
   - Standardized float timestamps to 4 decimal places across block hashes and JSON serialization.

---

## Getting Started

### 1. Requirements

- Python 3.10+ (tested on Python 3.13)
- Dependencies: `cryptography`, `pytest`, `requests`

```bash
# Clone the repository
git clone https://github.com/vasaviosc/Cyber-Security.git
cd "Cyber-Security/decentralized voting system"

# Install dependencies
pip install -r requirements.txt   # or: pip install cryptography pytest requests
```

### 2. Generate Sample Voters

```bash
python scripts/setup_election.py
```
This generates `sample_voters.json` with Alice, Bob, Charlie, Dave, and Eve keypairs.

### 3. Start Node Daemon & SOC Dashboard

```bash
python -m openballot.cli serve --port 8000 --difficulty 1 --voters sample_voters.json
```

Once started, open your web browser to:
👉 **`http://127.0.0.1:8000/`**

### 4. Interactive CLI Tooling

Open a new terminal window:

```bash
# 1. Generate keypair for a new voter
python -m openballot.cli keygen --save my_voter.json

# 2. Cast a vote on proposal PROP-2026-01 using Alice's key
python -m openballot.cli vote \
  --key "bb2656668db27a0b..." \
  --proposal "PROP-2026-01" \
  --choice "YES" \
  --node "http://127.0.0.1:8000"

# 3. Mine pending mempool ballots into a new block
python -m openballot.cli mine --node "http://127.0.0.1:8000"

# 4. View election results
python -m openballot.cli tally --proposal "PROP-2026-01" --node "http://127.0.0.1:8000"

# 5. Check node health
python -m openballot.cli status --node "http://127.0.0.1:8000"

# 6. Run a security simulation (signature forgery detection)
python -m openballot.cli simulate --type signature_tamper --node "http://127.0.0.1:8000"
```

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` or `/index.html` | Hexanova SOC Cybersecurity Operations Dashboard |
| `GET` | `/health` | Node health status, uptime, blocks, mempool, alert summary |
| `GET` | `/api/v1/stats` | Comprehensive SOC telemetry and blockchain metrics |
| `POST` | `/api/v1/ballots` | Submit a digitally signed ballot (with Ed25519 verification) |
| `GET` | `/api/v1/mempool` | Inspect unconfirmed ballots in the mempool |
| `POST` | `/api/v1/mine` | Seal mempool ballots into a new block using Proof-of-Work |
| `GET` | `/api/v1/chain` | Retrieve full immutable blockchain ledger |
| `GET` | `/api/v1/proposals` | List all proposals and live tallies |
| `GET` | `/api/v1/tally?proposal=<id>` | Query verified tally results for a proposal |
| `GET` | `/api/v1/security/events` | Query SOC threat & security audit logs (with severity filter) |
| `POST` | `/api/v1/security/simulate` | Test cyber attack defenses (signature tamper, double vote, fork) |
| `POST` | `/api/v1/voters/register` | Register an authorized voter ID in the node whitelist |
| `GET` / `POST` | `/api/v1/peers` | View or register peer node URLs |
| `POST` | `/api/v1/sync` | Sync and resolve blockchain forks with peer chains |

---

## Running the Automated Test Suite

To execute all 28 automated unit, integration, and security regression tests:

```bash
pytest -v
```

### Test Coverage Highlights
- ✅ Ed25519 signature generation and verification (`test_crypto.py`)
- ✅ Cross-proposal replay attack defense (`test_ballot.py`)
- ✅ Invalid stake weight rejection (`test_ballot.py`)
- ✅ Mempool duplicate rejection on same proposal (`test_mempool.py`)
- ✅ Confirmed ledger double-voting rejection (`test_node_api.py`)
- ✅ Consensus Genesis block integrity & sequential height checking (`test_consensus.py`)
- ✅ Monotonic timestamp chronology enforcement (`test_consensus.py`)
- ✅ CORS headers & preflight `OPTIONS` handling (`test_node_api.py`)
- ✅ Static dashboard delivery at root (`test_node_api.py`)
- ✅ SOC security threat event logging & attack simulation (`test_node_api.py`)

---

## License

This project is licensed under the MIT License — see the [LICENSE](decentralized%20voting%20system/LICENSE) file for details.
