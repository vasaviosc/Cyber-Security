# OpenBallot 🗳️

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](pyproject.toml)
[![Tests: Passing](https://img.shields.io/badge/tests-passing-success.svg)](tests/)

A lightweight, decentralized, and verifiable cryptographic voting node designed for tamper-evident digital elections and community governance.

---

## Overview

OpenBallot implements a decentralized ledger tailored specifically for balloting and referendums. Instead of relying on a centralized election database, ballots are cryptographically signed by voters using **Ed25519** public keys, ingested into an unconfirmed transaction pool (**mempool**), and sealed into blocks through **Proof-of-Work (PoW)** Nakamoto-style consensus.

```
       [ Voter CLI ]
             |
    (Sign with Ed25519)
             |
             v
     [ POST /api/v1/ballots ]
             |
             v
       +------------+           +------------------+
       |  Mempool   |  ===>>    |  Block Assembler |
       +------------+  (drain)  +------------------+
                                         |
                                         v
                            +--------------------------+
                            |     Blockchain Ledger    |
                            | [Genesis]<-[B1]<-[B2]... |
                            +--------------------------+
                                         |
                                         v
                                  [ Tally Engine ]
```

---

## Features

- **Ed25519 Cryptography**: Fast, secure asymmetric signatures for ballot authenticity.
- **Auditable Ledger**: Chained blocks containing cryptographically signed voter choices.
- **Decentralized Consensus**: Longest-chain conflict resolution across peer nodes.
- **Zero Heavy Dependencies**: Built on top of Python's standard HTTP libraries and `cryptography`.
- **Developer CLI**: Full command-line client for key generation, vote casting, mining, and tally verification.

---

## Getting Started

### 1. Installation

Ensure you have Python 3.10 or later installed:

```bash
# Clone the repository
git clone https://github.com/openballot/openballot.git
cd openballot

# Install dependencies (or run directly in your environment)
pip install cryptography pytest requests
```

### 2. Run the Node Daemon

Start a local OpenBallot node:

```bash
python3 -m openballot.cli serve --port 8000 --difficulty 1
```

Check node health:

```bash
curl http://127.0.0.1:8000/health
```

### 3. Generate Voter Keys & Cast a Ballot

Open a new terminal window:

```bash
# 1. Generate keypair for Alice
python3 -m openballot.cli keygen --save alice.json

# 2. Cast a vote on proposal PROP-2026-01
SECRET=$(jq -r '.secret_key' alice.json)
python3 -m openballot.cli vote \
  --key "$SECRET" \
  --proposal "PROP-2026-01" \
  --choice "YES" \
  --node "http://127.0.0.1:8000"

# 3. Mine pending ballots into the blockchain
python3 -m openballot.cli mine --node "http://127.0.0.1:8000"

# 4. View election results
python3 -m openballot.cli tally --proposal "PROP-2026-01" --node "http://127.0.0.1:8000"
```

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Node uptime, chain height, mempool count |
| `GET` | `/metrics` | Prometheus metrics for scraping chain and node performance |
| `POST` | `/api/v1/ballots` | Submit a digitally signed ballot (O(1) dedup & auto-gossip) |
| `GET` | `/api/v1/mempool` | Inspect unconfirmed ballots |
| `POST` | `/api/v1/mine` | Seal mempool into a new block using Merkle root |
| `GET` | `/api/v1/chain` | Retrieve full blockchain ledger |
| `GET` | `/api/v1/snapshot` | Compact state snapshot for fast peer synchronization |
| `GET` | `/api/v1/tally?proposal=<id>` | Calculate verified election tally (O(1) accumulator) |
| `POST` | `/api/v1/sync` | Sync and resolve chain forks with peers |
| `GET` / `POST` | `/api/v1/peers` | View or register peer node URLs |

---

## High-Performance & Scalability Features

- **$O(1)$ Hash Indexing**: Replaces $O(N)$ linear blockchain scans for duplicate ballot checking, vote verification, and tally generation with constant-time state caches.
- **Merkle Tree Header Mining**: Decouples block hashing from transaction serialization by computing a cryptographic Merkle root across transactions, reducing PoW iteration overhead by orders of magnitude.
- **SQLite WAL & Atomic JSON Storage**: Supports ACID-compliant SQLite relational storage with Write-Ahead Logging (`--db-file ledger.db`) alongside atomic tempfile-replace JSON persistence.
- **Multi-Threaded & ASGI Architecture**: Built on non-blocking multi-threaded request processing (`NodeServer`) with optional enterprise FastAPI + Uvicorn server (`--engine uvicorn`).
- **Autonomous P2P Gossip**: Incoming ballots and mined blocks are automatically gossiped to connected network peers asynchronously in the background.
- **Vote Privacy & Commitments**: Provides cryptographic commitment helpers (`create_ballot_commitment`) for secret ballot voting schemes.

---

## Running Tests

Execute the unit and performance test suite:

```bash
pytest -v
```

---

## Architecture Details

- `openballot/crypto.py`: Ed25519 keypair generation, message signatures, batch verification, and cryptographic commitments.
- `openballot/ballot.py`: Ballot data structure with anti-replay nonces, timestamps, and commitment support.
- `openballot/block.py`: Merkle root calculation, block header serialization, and fast Proof-of-Work mining.
- `openballot/ledger.py`: Genesis state, voter registration, O(1) indexed lookups, atomic JSON and SQLite WAL persistence.
- `openballot/mempool.py`: Thread-safe, bounded in-memory transaction staging pool with O(1) duplicate checks.
- `openballot/consensus.py`: Longest-chain resolution, Merkle tree verification, and PoW/PoA consensus engines.
- `openballot/node.py`: Multi-threaded HTTP daemon with automatic P2P gossip and Prometheus monitoring.
- `openballot/api_app.py`: High-throughput ASGI FastAPI production application.
- `openballot/cli.py`: Administrative and voter CLI tooling with engine and storage flags.

---

## Security & Bug Bounty

OpenBallot is undergoing continuous security audits. If you identify vulnerabilities or design weaknesses in our consensus, mempool ingestion, or ballot cryptographic verification, please consult [CONTRIBUTING.md](CONTRIBUTING.md) to report issues and submit fixes.
