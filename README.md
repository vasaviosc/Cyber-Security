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

Ballots use the versioned `openballot:ballot:v1` signing payload, which binds the voter public key, proposal ID, choice, and weight. Signatures created with the previous payload format are not compatible and must be recreated by the voter.

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
| `POST` | `/api/v1/ballots` | Submit a digitally signed ballot |
| `GET` | `/api/v1/mempool` | Inspect unconfirmed ballots |
| `POST` | `/api/v1/mine` | Seal mempool into a new block |
| `GET` | `/api/v1/chain` | Retrieve full blockchain ledger |
| `GET` | `/api/v1/tally?proposal=<id>` | Calculate verified election tally |
| `POST` | `/api/v1/sync` | Sync and resolve chain forks with peers |
| `GET` / `POST` | `/api/v1/peers` | View or register peer node URLs |

---

## Running Tests

Execute the unit test suite:

```bash
pytest -v
```

---

## Architecture Details

- `openballot/crypto.py`: Ed25519 keypair generation, raw hex serialization, and message signatures.
- `openballot/ballot.py`: Ballot data structure and signature verification.
- `openballot/block.py`: Block header, transaction payload serialization, and Proof-of-Work hashing.
- `openballot/ledger.py`: Genesis state initialization, voter registration, duplicate check, and tally engine.
- `openballot/mempool.py`: In-memory transaction staging area.
- `openballot/consensus.py`: Peer chain validation and Nakamoto-style longest-chain conflict resolution.
- `openballot/node.py`: Embedded HTTP API server.
- `openballot/cli.py`: Administrative and voter CLI tooling.

---

## Security & Bug Bounty

OpenBallot is undergoing continuous security audits. If you identify vulnerabilities or design weaknesses in our consensus, mempool ingestion, or ballot cryptographic verification, please consult [CONTRIBUTING.md](CONTRIBUTING.md) to report issues and submit fixes.
