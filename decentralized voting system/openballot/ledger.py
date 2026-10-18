import json
import os
import sqlite3
import threading
from typing import Dict, Set, List, Optional, Any, Tuple
from openballot.block import Block
from openballot.ballot import Ballot

GENESIS_PREV_HASH = "0" * 64


class Ledger:
    def __init__(self, voter_registry: Optional[Set[str]] = None, storage_path: Optional[str] = None):
        self.lock = threading.RLock()
        self.chain: List[Block] = []
        self.voter_registry: Set[str] = set(v.strip().lower() for v in (voter_registry or []))
        self.storage_path: Optional[str] = storage_path

        # O(1) Fast Indexing Caches
        self._votes_index: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._tally_cache: Dict[str, Dict[str, int]] = {}
        self._proposals_cache: Dict[str, Dict[str, Any]] = {}
        self._indexed_chain_length: int = 0

    def _index_ballot(self, ballot: Ballot, block: Block):
        prop_norm = ballot.proposal_id.strip().upper()
        voter_norm = ballot.voter_id.strip().lower()
        key = (prop_norm, voter_norm)

        self._votes_index[key] = {
            "voter_id": ballot.voter_id,
            "proposal_id": ballot.proposal_id,
            "choice": ballot.choice,
            "weight": ballot.weight,
            "signature": ballot.signature,
            "block_index": block.index,
            "block_hash": block.hash,
            "block_timestamp": block.timestamp
        }

        if prop_norm not in self._tally_cache:
            self._tally_cache[prop_norm] = {}
        self._tally_cache[prop_norm][ballot.choice] = (
            self._tally_cache[prop_norm].get(ballot.choice, 0) + ballot.weight
        )

        if prop_norm not in self._proposals_cache:
            self._proposals_cache[prop_norm] = {
                "proposal_id": prop_norm,
                "total_ballots": 0,
                "total_weight": 0,
                "results": {}
            }
        p_info = self._proposals_cache[prop_norm]
        p_info["total_ballots"] += 1
        p_info["total_weight"] += ballot.weight
        p_info["results"][ballot.choice] = (
            p_info["results"].get(ballot.choice, 0) + ballot.weight
        )

    def _needs_reindex(self) -> bool:
        return self._indexed_chain_length != len(self.chain)

    def _rebuild_indexes(self):
        with self.lock:
            self._votes_index.clear()
            self._tally_cache.clear()
            self._proposals_cache.clear()
            for block in self.chain:
                for ballot in block.ballots:
                    self._index_ballot(ballot, block)
            self._indexed_chain_length = len(self.chain)

    def append_block(self, block: Block):
        with self.lock:
            self.chain.append(block)
            for ballot in block.ballots:
                self._index_ballot(ballot, block)
            self._indexed_chain_length = len(self.chain)

    def create_genesis_block(self) -> Block:
        with self.lock:
            if self.chain:
                return self.chain[0]
            genesis = Block(
                index=0,
                prev_hash=GENESIS_PREV_HASH,
                ballots=[],
                timestamp=1700000000.0,
                nonce=0
            )
            self.chain.append(genesis)
            self._indexed_chain_length = len(self.chain)
            return genesis

    def register_voter(self, voter_id: str):
        if voter_id and voter_id.strip():
            with self.lock:
                self.voter_registry.add(voter_id.strip().lower())

    def load_voter_registry_file(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Voter registry file not found: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            with self.lock:
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict) and "voter_id" in v:
                            self.register_voter(v["voter_id"])
                        else:
                            self.register_voter(k)
                elif isinstance(data, list):
                    for v in data:
                        if isinstance(v, str):
                            self.register_voter(v)
                        elif isinstance(v, dict) and "voter_id" in v:
                            self.register_voter(v["voter_id"])

    def is_registered(self, voter_id: str) -> bool:
        with self.lock:
            if not self.voter_registry:
                return True
            return voter_id.strip().lower() in self.voter_registry

    def has_voted(self, proposal_id: str, voter_id: str) -> bool:
        """
        O(1) duplicate voting check against cached ledger state.
        """
        prop_norm = proposal_id.strip().upper()
        voter_norm = voter_id.strip().lower()
        with self.lock:
            if self._needs_reindex():
                self._rebuild_indexes()
            return (prop_norm, voter_norm) in self._votes_index

    def get_vote(self, proposal_id: str, voter_id: str) -> Optional[Dict[str, Any]]:
        """
        O(1) verified vote inclusion lookup.
        """
        prop_norm = proposal_id.strip().upper()
        voter_norm = voter_id.strip().lower()
        with self.lock:
            if self._needs_reindex():
                self._rebuild_indexes()
            vote = self._votes_index.get((prop_norm, voter_norm))
            return dict(vote) if vote else None

    def tally(self, proposal_id: str) -> Dict[str, int]:
        """
        O(1) election tally retrieval from cached accumulator.
        """
        prop_norm = proposal_id.strip().upper()
        with self.lock:
            if self._needs_reindex():
                self._rebuild_indexes()
            return dict(self._tally_cache.get(prop_norm, {}))

    def get_proposals(self) -> List[Dict[str, Any]]:
        """
        O(P) aggregated proposals overview where P = number of proposals.
        """
        with self.lock:
            if self._needs_reindex():
                self._rebuild_indexes()
            return [dict(p) for p in self._proposals_cache.values()]

    def save_to_file(self, filepath: Optional[str] = None):
        target = filepath or self.storage_path
        if not target:
            return
        with self.lock:
            if target.endswith((".db", ".sqlite", ".sqlite3")):
                self._save_to_sqlite(target)
            else:
                self._save_to_json_atomic(target)

    def _save_to_json_atomic(self, filepath: str):
        """
        Atomically saves ledger state to JSON file via tempfile replace to prevent corruption.
        """
        target_dir = os.path.dirname(os.path.abspath(filepath)) or "."
        os.makedirs(target_dir, exist_ok=True)
        tmp_path = f"{filepath}.tmp.{os.getpid()}"
        data = {
            "voter_registry": list(self.voter_registry),
            "chain": [b.to_dict() for b in self.chain]
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)

    def _save_to_sqlite(self, filepath: str):
        """
        High-performance SQLite relational storage with WAL mode.
        """
        conn = sqlite3.connect(filepath)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS voter_registry (
                voter_id TEXT PRIMARY KEY
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                block_index INTEGER PRIMARY KEY,
                hash TEXT UNIQUE,
                prev_hash TEXT,
                merkle_root TEXT,
                timestamp REAL,
                nonce INTEGER,
                ballots_json TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ballots (
                proposal_id TEXT,
                voter_id TEXT,
                choice TEXT,
                weight INTEGER,
                signature TEXT,
                block_index INTEGER,
                PRIMARY KEY (proposal_id, voter_id)
            )
        """)

        # Sync voters
        for vid in self.voter_registry:
            cur.execute("INSERT OR IGNORE INTO voter_registry (voter_id) VALUES (?)", (vid,))

        # Sync blocks and ballots
        for b in self.chain:
            ballots_raw = json.dumps([bal.to_dict() for bal in b.ballots])
            cur.execute("""
                INSERT OR REPLACE INTO blocks 
                (block_index, hash, prev_hash, merkle_root, timestamp, nonce, ballots_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (b.index, b.hash, b.prev_hash, b.merkle_root, b.timestamp, b.nonce, ballots_raw))

            for bal in b.ballots:
                cur.execute("""
                    INSERT OR REPLACE INTO ballots 
                    (proposal_id, voter_id, choice, weight, signature, block_index)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (bal.proposal_id, bal.voter_id, bal.choice, bal.weight, bal.signature, b.index))

        conn.commit()
        conn.close()

    @classmethod
    def load_from_file(cls, filepath: str) -> "Ledger":
        if not os.path.exists(filepath):
            ledger = cls(storage_path=filepath)
            ledger.create_genesis_block()
            ledger.save_to_file()
            return ledger

        if filepath.endswith((".db", ".sqlite", ".sqlite3")):
            return cls._load_from_sqlite(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        voter_registry = set(data.get("voter_registry", []))
        ledger = cls(voter_registry=voter_registry, storage_path=filepath)
        chain_raw = data.get("chain", [])
        if chain_raw:
            ledger.chain = [Block.from_dict(b) for b in chain_raw]
        else:
            ledger.create_genesis_block()
        ledger._rebuild_indexes()
        return ledger

    @classmethod
    def _load_from_sqlite(cls, filepath: str) -> "Ledger":
        conn = sqlite3.connect(filepath)
        cur = conn.cursor()

        # Load voters
        cur.execute("SELECT voter_id FROM voter_registry")
        voters = set(row[0] for row in cur.fetchall())
        ledger = cls(voter_registry=voters, storage_path=filepath)

        # Load blocks
        cur.execute("SELECT block_index, prev_hash, hash, merkle_root, timestamp, nonce, ballots_json FROM blocks ORDER BY block_index ASC")
        rows = cur.fetchall()
        if rows:
            for r in rows:
                b_idx, prev_h, h, m_root, ts, nonce, b_json = r
                ballots = [Ballot.from_dict(d) for d in json.loads(b_json)]
                blk = Block(index=b_idx, prev_hash=prev_h, ballots=ballots, timestamp=ts, nonce=nonce, merkle_root=m_root)
                blk.hash = h
                ledger.chain.append(blk)
        else:
            ledger.create_genesis_block()

        conn.close()
        ledger._rebuild_indexes()
        return ledger

    @property
    def latest_block(self) -> Block:
        with self.lock:
            if not self.chain:
                self.create_genesis_block()
            return self.chain[-1]
