import sqlite3
import json
from pathlib import Path
from typing import List, Optional
from openballot.block import Block


class SQLiteStorage:
    """
    Lightweight SQLite persistence engine for the OpenBallot blockchain.
    Persists blocks, cryptographic transactions, and audit records safely on disk.
    """
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    block_index INTEGER PRIMARY KEY,
                    prev_hash TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    nonce INTEGER NOT NULL,
                    block_hash TEXT NOT NULL,
                    ballots_json TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS voters (
                    voter_id TEXT PRIMARY KEY,
                    registered_at REAL NOT NULL
                )
            """)
            conn.commit()

    def save_block(self, block: Block):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            ballots_json = json.dumps([b.to_dict() for b in block.ballots])
            cursor.execute("""
                INSERT OR REPLACE INTO blocks 
                (block_index, prev_hash, timestamp, nonce, block_hash, ballots_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (block.index, block.prev_hash, block.timestamp, block.nonce, block.hash, ballots_json))
            conn.commit()

    def load_chain(self) -> List[Block]:
        chain = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT block_index, prev_hash, timestamp, nonce, block_hash, ballots_json FROM blocks ORDER BY block_index ASC")
            rows = cursor.fetchall()
            for r in rows:
                block_dict = {
                    "index": r[0],
                    "prev_hash": r[1],
                    "timestamp": r[2],
                    "nonce": r[3],
                    "hash": r[4],
                    "ballots": json.loads(r[5])
                }
                chain.append(Block.from_dict(block_dict))
        return chain

    def count_blocks(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM blocks")
            return cursor.fetchone()[0]
