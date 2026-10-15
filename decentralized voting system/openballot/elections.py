from typing import Dict, List, Optional, Any


DEFAULT_ELECTIONS: Dict[str, Dict[str, Any]] = {
    "PROP-2026-01": {
        "proposal_id": "PROP-2026-01",
        "title": "Lok Sabha Parliamentary Constituency General Election 2026",
        "description": "General parliamentary election for democratic representation and constituency leadership.",
        "category": "Parliamentary / Lok Sabha",
        "status": "ACTIVE",
        "choices": ["Candidate Alpha", "Candidate Beta", "Candidate Gamma", "NOTA"]
    },
    "PROP-2026-02": {
        "proposal_id": "PROP-2026-02",
        "title": "National Digital Public Infrastructure & Green Energy Referendum",
        "description": "Referendum on allocating national development bond reserves for solar corridors and transit electrification.",
        "category": "National Referendum",
        "status": "ACTIVE",
        "choices": ["YES", "NO", "NOTA"]
    },
    "PROP-2026-03": {
        "proposal_id": "PROP-2026-03",
        "title": "Central University & IIT Student Council Presidential Election",
        "description": "Annual student body council presidential election for academic and campus welfare governance.",
        "category": "University Governance",
        "status": "ACTIVE",
        "choices": ["Candidate A (Progressive Council)", "Candidate B (Student Action)", "NOTA"]
    }
}


class ElectionManager:
    """
    Manages metadata and configuration for elections/proposals.
    Ensures proposals have human-readable context alongside raw ledger IDs.
    """
    def __init__(self):
        self._elections: Dict[str, Dict[str, Any]] = dict(DEFAULT_ELECTIONS)

    def get_all(self) -> List[Dict[str, Any]]:
        return list(self._elections.values())

    def get(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        return self._elections.get(proposal_id.strip())

    def register_proposal(self, proposal_id: str, title: str, description: str, choices: Optional[List[str]] = None, category: str = "Governance") -> Dict[str, Any]:
        p_id = proposal_id.strip()
        election = {
            "proposal_id": p_id,
            "title": title.strip() or f"Referendum {p_id}",
            "description": description.strip() or "General voting referendum.",
            "category": category.strip() or "Governance",
            "status": "ACTIVE",
            "choices": [c.strip() for c in (choices or ["YES", "NO", "ABSTAIN"]) if c.strip()]
        }
        self._elections[p_id] = election
        return election

    def ensure_exists(self, proposal_id: str):
        p_id = proposal_id.strip()
        if p_id and p_id not in self._elections:
            self.register_proposal(p_id, f"Proposal {p_id}", "Referendum recorded on the blockchain ledger.")


# Global instance
election_manager = ElectionManager()
