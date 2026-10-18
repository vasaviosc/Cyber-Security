from fastapi import FastAPI, HTTPException, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from openballot.ballot import Ballot
from openballot.block import Block
from openballot.ledger import Ledger
from openballot.mempool import Mempool
from openballot.consensus import ConsensusEngine


app = FastAPI(
    title="OpenBallot High-Performance Node API",
    description="Scalable, asynchronous cryptographic voting node engine with Merkle integrity and BFT/PoW consensus.",
    version="2.0.0"
)

# Global shared node instances
ledger = Ledger()
ledger.create_genesis_block()
mempool = Mempool()
consensus = ConsensusEngine(ledger=ledger, difficulty=1)
difficulty = 1
peers: List[str] = []


class BallotSubmission(BaseModel):
    voter_id: str
    proposal_id: str
    choice: str
    signature: str
    weight: int = 1
    nonce: int = 0
    timestamp: Optional[float] = None
    commitment: Optional[str] = ""


class VoterRegistration(BaseModel):
    voter_id: Optional[str] = None
    voter_ids: Optional[List[str]] = Field(default_factory=list)


class PeerRegistration(BaseModel):
    peer: str


class SyncChainPayload(BaseModel):
    chain: List[Dict[str, Any]]


@app.get("/health")
def get_health():
    return {
        "status": "healthy",
        "blocks": len(ledger.chain),
        "mempool": mempool.size(),
        "peers": len(peers),
        "registered_voters": len(ledger.voter_registry)
    }


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    metrics = [
        "# HELP openballot_chain_height Total blocks in ledger",
        "# TYPE openballot_chain_height gauge",
        f"openballot_chain_height {len(ledger.chain)}",
        "# HELP openballot_mempool_size Total pending unconfirmed ballots",
        "# TYPE openballot_mempool_size gauge",
        f"openballot_mempool_size {mempool.size()}",
        "# HELP openballot_registered_voters Total authorized voters",
        "# TYPE openballot_registered_voters gauge",
        f"openballot_registered_voters {len(ledger.voter_registry)}",
        "# HELP openballot_peers_count Total connected peer nodes",
        "# TYPE openballot_peers_count gauge",
        f"openballot_peers_count {len(peers)}"
    ]
    return "\n".join(metrics) + "\n"


@app.get("/api/v1/chain")
def get_chain():
    chain_data = [b.to_dict() for b in ledger.chain]
    return {"length": len(chain_data), "chain": chain_data}


@app.get("/api/v1/mempool")
def get_mempool():
    ballots_data = [b.to_dict() for b in mempool.all()]
    return {"count": len(ballots_data), "ballots": ballots_data}


@app.get("/api/v1/tally")
def get_tally(proposal: str):
    if not proposal:
        raise HTTPException(status_code=400, detail="Missing proposal query parameter")
    tally_result = ledger.tally(proposal)
    return {"proposal": proposal.strip().upper(), "results": tally_result}


@app.get("/api/v1/proposals")
def get_proposals():
    return {"proposals": ledger.get_proposals()}


@app.get("/api/v1/snapshot")
def get_snapshot():
    return {
        "height": len(ledger.chain),
        "latest_block_hash": ledger.latest_block.hash,
        "tallies": ledger.get_proposals(),
        "registered_voters_count": len(ledger.voter_registry)
    }


@app.get("/api/v1/ballots/verify")
def verify_ballot(voter_id: str, proposal: str):
    if not voter_id or not proposal:
        raise HTTPException(status_code=400, detail="Missing voter_id or proposal query parameters")

    vote_info = ledger.get_vote(proposal, voter_id)
    if vote_info:
        return {"status": "confirmed", "vote": vote_info}
    elif mempool.has_voter_submitted(proposal, voter_id):
        return {"status": "pending_in_mempool", "proposal": proposal, "voter_id": voter_id}
    else:
        raise HTTPException(status_code=404, detail="No ballot found for this voter and proposal")


@app.get("/api/v1/voters")
def get_voters():
    return {
        "count": len(ledger.voter_registry),
        "open_policy": len(ledger.voter_registry) == 0,
        "registered_voters": sorted(list(ledger.voter_registry))
    }


@app.post("/api/v1/voters")
def register_voters(payload: VoterRegistration):
    added = 0
    if payload.voter_id:
        ledger.register_voter(payload.voter_id)
        added += 1
    for vid in (payload.voter_ids or []):
        ledger.register_voter(vid)
        added += 1

    if ledger.storage_path:
        ledger.save_to_file()

    return {
        "status": "success",
        "added": added,
        "total_registered": len(ledger.voter_registry)
    }


@app.post("/api/v1/ballots", status_code=status.HTTP_202_ACCEPTED)
def submit_ballot(payload: BallotSubmission):
    ballot = Ballot(
        voter_id=payload.voter_id,
        proposal_id=payload.proposal_id,
        choice=payload.choice,
        signature=payload.signature,
        weight=payload.weight,
        nonce=payload.nonce,
        timestamp=payload.timestamp,
        commitment=payload.commitment or ""
    )

    if not ballot.voter_id or not ballot.proposal_id or not ballot.choice:
        raise HTTPException(status_code=400, detail="Missing required ballot fields")

    # 1. Verify digital signature
    if not ballot.verify():
        raise HTTPException(status_code=401, detail="Cryptographic signature verification failed")

    # 2. Verify voter registration whitelist
    if not ledger.is_registered(ballot.voter_id):
        raise HTTPException(status_code=403, detail="Voter ID not in authorized voter registry")

    # 3. Check if voter already cast ballot on confirmed ledger (O(1))
    if ledger.has_voted(ballot.proposal_id, ballot.voter_id):
        raise HTTPException(status_code=409, detail="Voter has already cast a ballot for this proposal on ledger")

    # 4. Check if voter already has a pending ballot in mempool (O(1))
    if mempool.has_voter_submitted(ballot.proposal_id, ballot.voter_id):
        raise HTTPException(status_code=409, detail="Voter has already submitted a pending ballot for this proposal in mempool")

    # Ingest ballot into mempool
    accepted = mempool.add(ballot)
    if not accepted:
        raise HTTPException(status_code=400, detail="Failed to add ballot to mempool")

    return {"status": "accepted", "proposal": ballot.proposal_id}


@app.post("/api/v1/mine")
def mine_block():
    pending = mempool.drain()

    unique_ballots = []
    seen = set()
    for b in pending:
        key = (b.proposal_id, b.voter_id)
        if key not in seen and not ledger.has_voted(b.proposal_id, b.voter_id):
            seen.add(key)
            unique_ballots.append(b)

    new_block = Block(
        index=len(ledger.chain),
        prev_hash=ledger.chain[-1].hash,
        ballots=unique_ballots
    )
    new_block.mine(difficulty=difficulty)
    ledger.append_block(new_block)

    if ledger.storage_path:
        ledger.save_to_file()

    return {
        "status": "mined",
        "block_index": new_block.index,
        "block_hash": new_block.hash,
        "merkle_root": new_block.merkle_root,
        "ballots_sealed": len(unique_ballots)
    }


@app.get("/api/v1/peers")
def get_peers():
    return {"peers": peers}


@app.post("/api/v1/peers")
def add_peer(payload: PeerRegistration):
    if payload.peer and payload.peer not in peers:
        peers.append(payload.peer)
    return {"peers": peers}


@app.post("/api/v1/sync")
def sync_chain(payload: SyncChainPayload):
    if not payload.chain:
        raise HTTPException(status_code=400, detail="Empty chain provided")
    try:
        candidate = [Block.from_dict(b) for b in payload.chain]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid block format: {e}")

    replaced = consensus.resolve_conflicts([candidate])
    return {
        "chain_replaced": replaced,
        "current_length": len(ledger.chain)
    }
