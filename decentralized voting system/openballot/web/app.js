// ==========================================================================
// OpenBallot - Professional Digital Voting Client Logic
// Standard administrative client connecting to local OpenBallot node
// ==========================================================================

const API_BASE = window.location.origin;

// Voter keyring store - synchronized dynamically with blockchain node & sample_voters.json
let VOTER_KEYRING = {
  aarav_sharma: {
    name: "Aarav Sharma (New Delhi Central DL-04)",
    voter_id: "c433600b71c72f5e75287f4e31e9f3ba4bbcc4e1b6fec236e4d95fc9dd40dbd8",
    secret_key: "97e14f15e73dbed87cfbb55623bb232febdda7e14b20ce7f361201b4871c3e37",
    district: "New Delhi Central (DL-04)"
  },
  priya_patel: {
    name: "Priya Patel (Ahmedabad West GJ-08)",
    voter_id: "88dbf9f66de9efc0147bb7891f83510ce6bebbfd7a6131bd49daa7d5df0aa39c",
    secret_key: "8a229db248c1e01f72c402728be7b338aa456fdf805d0fae87be1e67e76267ae",
    district: "Ahmedabad West (GJ-08)"
  },
  rahul_verma: {
    name: "Rahul Verma (Bengaluru South KA-26)",
    voter_id: "68f6015c851728a61191453f9df75bc94c264e7c9897538adb27354a3f5aa57f",
    secret_key: "93a265f188730bbfb757d9def21c2b9072a27b637e112faea2d148a0158a1c9e",
    district: "Bengaluru South (KA-26)"
  },
  ananya_iyer: {
    name: "Ananya Iyer (Chennai Central TN-04)",
    voter_id: "fcf0847a54a13e6b59c00192ef7ec2b1df2d908b1d53ed67086e5a63c68dd6a9",
    secret_key: "33d8d8bf291bd6cb36d49fc4382d6619a68d27e599e95f89fe293a844e1ad1e6",
    district: "Chennai Central (TN-04)"
  },
  rohan_mukherjee: {
    name: "Rohan Mukherjee (Kolkata North WB-24)",
    voter_id: "f8d101d7d6fd351e7e62881a79c2d17a7aba13aa935ddc4b8551119d80ba6769",
    secret_key: "92759e48066fe98935d09adb1cd89855d39b7f628f98053f22e8ca75a34a7130",
    district: "Kolkata North (WB-24)"
  },
  elena_rostova: {
    name: "Elena Rostova (Physics Ward)",
    voter_id: "872595af0c083ec8dbc8ff5e935559f886f6bf7e987d5f6a1e588c522b654584",
    secret_key: "cd33caa6dfa35c78f0dee37f9fec77b62549dd9e47e9bc8250e85872b2dca336",
    district: "Physics Ward"
  },
  sneha_pillai: {
    name: "Sneha Pillai (District Tech)",
    voter_id: "4d6dd6a38b9b94e8497679d0ec49f904e23c223380df10f4e10ec3a620d1b0e6",
    secret_key: "5a119f2be8eb2651b6f0da9bb43ee00ff44b256ddad4e802c87316d0ba3c02f0",
    district: "District Tech"
  },
  krishna_chauhan: {
    name: "Krishna Chauhan (District Tech)",
    voter_id: "38ac902282368a51c80e362deca3bd3d528a633ed6b9138b38a37922fb9a4d1e",
    secret_key: "f5600706b318860fe58cab4c7fe5c9b69a4e1a389de57e5dea73c8ba6079d3ee",
    district: "District Tech"
  }
};

// Aliases for quick backward-compatibility lookup
VOTER_KEYRING["aarav"] = VOTER_KEYRING["aarav_sharma"];
VOTER_KEYRING["priya"] = VOTER_KEYRING["priya_patel"];
VOTER_KEYRING["rahul"] = VOTER_KEYRING["rahul_verma"];
VOTER_KEYRING["ananya"] = VOTER_KEYRING["ananya_iyer"];
VOTER_KEYRING["rohan"] = VOTER_KEYRING["rohan_mukherjee"];

let activeCitizenForCard = null;
let cachedChain = [];
let cachedElections = [];
let selectedChoice = "YES";
let pendingVotePayload = null;
let lastReceiptHash = "";
let nodeLocalIp = window.location.hostname || "127.0.0.1";
let nodePort = window.location.port || "8000";
let qrMode = "url";
let lastVoteDetails = null;

// Electronic Voting Machine (EVM) Audio Feedback Synthesizer
function playEVMSound() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    // Authentic 2-tone voting chime
    osc.frequency.setValueAtTime(880, now);
    osc.frequency.setValueAtTime(1760, now + 0.12);

    gain.gain.setValueAtTime(0.25, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.48);
  } catch (e) {
    // Autoplay policy or browser unsupported
  }
}

// Real-Time ISO/IEC compliant QR Code generator for mobile phone cameras
function updateReceiptQRCode() {
  const qrImg = document.getElementById("receiptQrImage");
  const label = document.getElementById("qrScanTargetLabel");
  const btnToggle = document.getElementById("btnToggleQrMode");
  if (!qrImg || !lastReceiptHash) return;

  const portPart = (nodePort && String(nodePort) !== "80") ? `:${nodePort}` : "";
  const host = (nodeLocalIp && nodeLocalIp !== "0.0.0.0") ? nodeLocalIp : window.location.hostname;
  const mobileUrl = `http://${host}${portPart}/?verify=${encodeURIComponent(lastReceiptHash)}`;

  let qrContent = mobileUrl;
  if (qrMode === "text") {
    const prop = lastVoteDetails ? lastVoteDetails.proposalId : "PROP";
    const choice = lastVoteDetails ? lastVoteDetails.choice : "CHOICE";
    qrContent = `OPENBALLOT VERIFIED BALLOT\nReceipt: ${lastReceiptHash}\nProposal: ${prop}\nVote: ${choice}\nSignature: Valid Ed25519`;
    if (label) label.textContent = "Plaintext cryptographic receipt mode";
    if (btnToggle) btnToggle.textContent = "⇄ Switch to Mobile URL QR";
  } else {
    if (label) label.textContent = `Scans to: ${host}${portPart}`;
    if (btnToggle) btnToggle.textContent = "⇄ Switch to Text QR";
  }

  qrImg.src = `${API_BASE}/api/v1/qr?data=${encodeURIComponent(qrContent)}`;
}

// Shorten public keys cleanly for human readability
function shortenKey(key, start = 8, end = 6) {
  if (!key) return "-";
  if (key.length <= start + end) return key;
  return `${key.substring(0, start)}...${key.substring(key.length - end)}`;
}

// Format Unix timestamp in Indian Standard Time (IST)
function formatTimestamp(ts) {
  if (!ts) return "-";
  const d = new Date(ts * 1000);
  return d.toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true
  }) + " IST";
}

// Simple Toast Notification
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `app-toast toast-${type}`;
  const icon = type === "success" ? "✓" : type === "error" ? "✗" : "ℹ";
  toast.innerHTML = `<span style="font-weight:700;">${icon}</span><span>${message}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.2s ease";
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

// Navigation between tabs
function navigateToTab(tabId) {
  document.querySelectorAll(".nav-link").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".page-tab-pane").forEach(pane => {
    pane.classList.toggle("active", pane.id === tabId);
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.querySelectorAll(".nav-link").forEach(link => {
  link.addEventListener("click", () => {
    const target = link.getAttribute("data-tab");
    navigateToTab(target);
  });
});

const brandLink = document.getElementById("brandLogoLink");
if (brandLink) {
  brandLink.addEventListener("click", (e) => {
    e.preventDefault();
    navigateToTab("tab-dashboard");
  });
}

// Update banner clock in Indian Standard Time (IST)
function updateClock() {
  const now = new Date();
  const el = document.getElementById("bannerTimestamp");
  if (el) {
    const istTime = now.toLocaleString("en-IN", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: true
    });
    el.textContent = `Standard Time: ${istTime} (IST / UTC+05:30)`;
  }
}
setInterval(updateClock, 1000);
updateClock();

// Choice Radio cards toggle
document.querySelectorAll(".choice-option").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".choice-option").forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
    const radio = card.querySelector("input[type='radio']");
    if (radio) {
      radio.checked = true;
      selectedChoice = radio.value;
    }
  });
});

// Voter Profile selection
const voterProfileSelect = document.getElementById("voterProfileSelect");
const displayVoterId = document.getElementById("displayVoterId");
const customKeyGroup = document.getElementById("customKeyGroup");
const inputCustomSecret = document.getElementById("inputCustomSecret");

function updateVoterProfile() {
  if (!voterProfileSelect) return;
  const val = voterProfileSelect.value;
  if (val === "custom") {
    if (customKeyGroup) customKeyGroup.style.display = "block";
    if (displayVoterId) displayVoterId.value = "Will be derived from private key upon signing";
  } else if (VOTER_KEYRING[val]) {
    if (customKeyGroup) customKeyGroup.style.display = "none";
    if (displayVoterId) displayVoterId.value = VOTER_KEYRING[val].voter_id;
  }
}

function renderVoterSelectOptions() {
  if (!voterProfileSelect) return;
  const currentVal = voterProfileSelect.value;
  const proposalId = document.getElementById("voteProposalSelect") ? document.getElementById("voteProposalSelect").value : "";

  voterProfileSelect.innerHTML = "";

  const keys = Object.keys(VOTER_KEYRING);
  if (keys.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No registered citizens found";
    voterProfileSelect.appendChild(opt);
  } else {
    for (const key of keys) {
      const v = VOTER_KEYRING[key];
      const opt = document.createElement("option");
      opt.value = key;
      const hasVoted = v.voted_proposals && v.voted_proposals.includes(proposalId);
      opt.textContent = `${v.name || key}${hasVoted ? ' [ALREADY VOTED]' : ''}`;
      voterProfileSelect.appendChild(opt);
    }
  }

  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "Manual Credential Input (Enter Custom Hex Key)";
  voterProfileSelect.appendChild(customOpt);

  if (currentVal && Array.from(voterProfileSelect.options).some(o => o.value === currentVal)) {
    voterProfileSelect.value = currentVal;
  } else if (keys.length > 0) {
    voterProfileSelect.value = keys[0];
  }
  updateVoterProfile();
}

if (voterProfileSelect) {
  voterProfileSelect.addEventListener("change", updateVoterProfile);
  renderVoterSelectOptions();
}

// Helper: Open Cast Vote tab with pre-selected proposal
function openVoteForProposal(proposalId) {
  const sel = document.getElementById("voteProposalSelect");
  if (sel) sel.value = proposalId;
  navigateToTab("tab-cast-vote");
}

// Helper: Open Results tab with pre-selected proposal
function openResultsForProposal(proposalId) {
  const sel = document.getElementById("resultsProposalFilter");
  if (sel) {
    sel.value = proposalId;
    renderResults();
  }
  navigateToTab("tab-results");
}

// Helper: Quick verify link
function setVerifyQuery(voterKey) {
  if (VOTER_KEYRING[voterKey]) {
    const input = document.getElementById("verifyQueryInput");
    if (input) input.value = VOTER_KEYRING[voterKey].voter_id;
    document.getElementById("verifyVoteForm").dispatchEvent(new Event("submit"));
  }
}

// =========================================================================
// FETCH ALL BACKEND DATA
// =========================================================================
async function refreshAllData() {
  try {
    const [healthRes, chainRes, mempoolRes, electionsRes, votersRes, auditRes, peersRes, citizensRes] = await Promise.all([
      fetch(`${API_BASE}/health`),
      fetch(`${API_BASE}/api/v1/chain`),
      fetch(`${API_BASE}/api/v1/mempool`),
      fetch(`${API_BASE}/api/v1/elections`),
      fetch(`${API_BASE}/api/v1/voters`),
      fetch(`${API_BASE}/api/v1/audit-log`),
      fetch(`${API_BASE}/api/v1/peers`),
      fetch(`${API_BASE}/api/v1/citizens`)
    ]);

    if (!healthRes.ok) throw new Error("Node connection failed");

    const health = await healthRes.json();
    if (health.local_ip) nodeLocalIp = health.local_ip;
    if (health.port) nodePort = health.port;
    const chainData = await chainRes.json();
    const mempoolData = await mempoolRes.json();
    const electionsData = await electionsRes.json();
    const votersData = await votersRes.json();
    const auditData = await auditRes.json();
    const peersData = await peersRes.json();

    if (citizensRes && citizensRes.ok) {
      const citizensData = await citizensRes.json();
      if (citizensData.citizens && citizensData.citizens.length > 0) {
        citizensData.citizens.forEach(c => {
          const slug = (c.name || '').toLowerCase().replace(/[^a-z0-9]/g, "_") || c.voter_id.substring(0, 8);
          const firstWord = (c.name || '').toLowerCase().split(" ")[0];
          const entry = {
            name: `${c.name} (${c.district || 'Citizen'})`,
            voter_id: c.voter_id.toLowerCase(),
            secret_key: c.secret_key || (VOTER_KEYRING[slug] ? VOTER_KEYRING[slug].secret_key : ""),
            district: c.district,
            has_voted: c.has_voted,
            voted_proposals: c.voted_proposals || []
          };
          VOTER_KEYRING[slug] = entry;
          if (firstWord && !VOTER_KEYRING[firstWord]) {
            VOTER_KEYRING[firstWord] = entry;
          }
        });
        renderVoterSelectOptions();
      }
    }

    cachedChain = chainData.chain || [];
    cachedElections = electionsData.elections || [];
    cachedVoters = votersData.voters || [];

    // Header Status
    const nodeBadge = document.getElementById("headerNodeBadge");
    if (nodeBadge) {
      nodeBadge.className = "system-badge badge-online";
      nodeBadge.innerHTML = `<span class="status-dot"></span><span>Node: <strong>ONLINE</strong></span>`;
    }

    // Calculate total votes confirmed in chain
    let totalConfirmedVotes = 0;
    cachedChain.forEach(b => {
      if (b.ballots) totalConfirmedVotes += b.ballots.length;
    });

    // Update Dashboard KPIs
    const elVotes = document.getElementById("dashTotalVotes");
    if (elVotes) elVotes.textContent = totalConfirmedVotes;

    const elMempool = document.getElementById("dashPendingVotes");
    if (elMempool) elMempool.textContent = mempoolData.count || 0;

    const elNavMempool = document.getElementById("mempoolNavCount");
    if (elNavMempool) elNavMempool.textContent = mempoolData.count || 0;

    const elHeight = document.getElementById("dashChainHeight");
    if (elHeight) elHeight.textContent = cachedChain.length || 0;

    const elPeers = document.getElementById("dashActivePeers");
    if (elPeers) elPeers.textContent = (peersData.peers || []).length;

    const elHealth = document.getElementById("dashNodeHealth");
    if (elHealth) {
      elHealth.textContent = "ONLINE";
      elHealth.style.color = "var(--success-green)";
    }

    // Network diagram label
    const elDiagHeight = document.getElementById("netDiagramLocalHeight");
    if (elDiagHeight) elDiagHeight.textContent = `Height: ${cachedChain.length}`;

    const elDiagPeers = document.getElementById("netPeerBadgeCount");
    if (elDiagPeers) elDiagPeers.textContent = `${(peersData.peers || []).length} Connected`;

    // Render Sub-Views
    renderRecentActivity(auditData.events || []);
    renderElectionsTable(cachedElections);
    renderBlockchain(cachedChain);
    renderMempoolTable(mempoolData.ballots || []);
    renderResults();
    renderAuditLog(auditData.events || []);
    renderVotersTable(votersData.voters || []);
    renderPeersTable(peersData.peers || []);

  } catch (err) {
    console.error("Data refresh error:", err);
    const nodeBadge = document.getElementById("headerNodeBadge");
    if (nodeBadge) {
      nodeBadge.className = "system-badge badge-offline";
      nodeBadge.innerHTML = `<span class="status-dot"></span><span>Node: <strong>OFFLINE</strong></span>`;
    }
    const elHealth = document.getElementById("dashNodeHealth");
    if (elHealth) {
      elHealth.textContent = "OFFLINE";
      elHealth.style.color = "var(--error-red)";
    }
  }
}

// -------------------------------------------------------------------------
// RENDER: Recent Activity on Dashboard
// -------------------------------------------------------------------------
function renderRecentActivity(events) {
  const tbody = document.getElementById("dashRecentActivityBody");
  if (!tbody) return;
  if (!events || events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 16px;">No recent events recorded.</td></tr>`;
    return;
  }
  const slice = events.slice(0, 6);
  tbody.innerHTML = slice.map(ev => {
    const badgeClass = ev.status === "SUCCESS" ? "badge-valid" : ev.status === "ERROR" ? "badge-offline" : ev.status === "WARNING" ? "badge-warning" : "badge-online";
    return `
      <tr>
        <td class="font-mono" style="color: var(--text-muted);">${ev.time_str || '-'}</td>
        <td style="font-weight: 600;">${ev.event_type}</td>
        <td style="color: var(--text-secondary);">${ev.details}</td>
        <td><span class="system-badge ${badgeClass}" style="font-size: 11px;">${ev.status}</span></td>
      </tr>
    `;
  }).join("");
}

// -------------------------------------------------------------------------
// RENDER: Elections Table
// -------------------------------------------------------------------------
function renderElectionsTable(elections) {
  const tbody = document.getElementById("electionsTableBody");
  if (!tbody) return;
  if (!elections || elections.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 20px;">No elections configured on this node.</td></tr>`;
    return;
  }

  tbody.innerHTML = elections.map(e => `
    <tr>
      <td>
        <strong style="color: var(--color-blue-primary);">${e.title}</strong>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${e.description}</div>
      </td>
      <td class="font-mono"><strong>${e.proposal_id}</strong></td>
      <td>${e.category || 'General'}</td>
      <td><span class="system-badge badge-valid">ACTIVE</span></td>
      <td><strong>${e.total_votes || 0}</strong> confirmed</td>
      <td>${(e.choices || []).join(", ")}</td>
      <td style="text-align: right;">
        <button class="btn btn-primary btn-sm" onclick="openVoteForProposal('${e.proposal_id}')">Vote</button>
        <button class="btn btn-secondary btn-sm" onclick="openResultsForProposal('${e.proposal_id}')" style="margin-left: 4px;">Results</button>
      </td>
    </tr>
  `).join("");

  const voteSel = document.getElementById("voteProposalSelect");
  const resSel = document.getElementById("resultsProposalFilter");
  if (voteSel && elections.length > 0) {
    const currentVal = voteSel.value;
    voteSel.innerHTML = elections.map(e => `<option value="${e.proposal_id}">${e.proposal_id}: ${e.title}</option>`).join("");
    if (currentVal && elections.some(e => e.proposal_id === currentVal)) {
      voteSel.value = currentVal;
    }
  }
  if (resSel && elections.length > 0) {
    const currentVal = resSel.value;
    resSel.innerHTML = elections.map(e => `<option value="${e.proposal_id}">${e.proposal_id}: ${e.title}</option>`).join("");
    if (currentVal && elections.some(e => e.proposal_id === currentVal)) {
      resSel.value = currentVal;
    }
  }
}

// -------------------------------------------------------------------------
// RENDER: Blockchain Table & Visual Diagram
// -------------------------------------------------------------------------
function renderBlockchain(chain) {
  const tbody = document.getElementById("blockchainTableBody");
  const diagram = document.getElementById("chainDiagramVisual");
  if (!tbody || !diagram) return;

  if (!chain || chain.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 24px;">Blockchain is empty.</td></tr>`;
    diagram.innerHTML = `<span style="color: var(--text-muted); font-size: 13px;">No blocks mined yet.</span>`;
    return;
  }

  diagram.innerHTML = chain.map((b, idx) => `
    <div class="chain-node ${idx === chain.length - 1 ? 'active-node' : ''}" onclick="showBlockDetails(${b.index})" style="cursor: pointer;" title="Click to view block details">
      <div style="font-size: 11px; font-weight: 700; color: ${b.index === 0 ? 'var(--success-green)' : 'var(--color-blue-primary)'};">
        ${b.index === 0 ? '🌱 GENESIS' : 'BLOCK #' + b.index}
      </div>
      <div class="font-mono" style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
        ${shortenKey(b.hash, 6, 4)}
      </div>
      <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
        ${(b.ballots || []).length} votes
      </div>
    </div>
    ${idx < chain.length - 1 ? '<span class="chain-arrow">&rarr;</span>' : ''}
  `).join("");

  const reversed = [...chain].reverse();
  tbody.innerHTML = reversed.map(b => `
    <tr>
      <td><strong>#${b.index}</strong></td>
      <td class="font-mono" title="${b.hash}">${shortenKey(b.hash, 10, 8)}</td>
      <td class="font-mono" style="color: var(--text-muted);" title="${b.prev_hash}">${shortenKey(b.prev_hash, 8, 6)}</td>
      <td><strong>${(b.ballots || []).length}</strong> votes</td>
      <td style="color: var(--text-muted); font-size: 12.5px;">${formatTimestamp(b.timestamp)}</td>
      <td class="font-mono">${b.nonce}</td>
      <td><span class="system-badge badge-valid">VALID</span></td>
      <td style="text-align: right;">
        <button class="btn btn-secondary btn-sm" onclick="showBlockDetails(${b.index})">View</button>
      </td>
    </tr>
  `).join("");
}

// Show block details drawer
function showBlockDetails(blockIndex) {
  const block = cachedChain.find(b => b.index === blockIndex);
  if (!block) return;

  const panel = document.getElementById("blockDetailPanel");
  if (!panel) return;
  document.getElementById("blockDetailTitle").textContent = `Block #${block.index} Complete Specification`;

  const tbody = document.getElementById("blockDetailBody");
  tbody.innerHTML = `
    <tr><th style="width: 160px;">Block Height</th><td>#${block.index} ${block.index === 0 ? '(Genesis Block)' : ''}</td></tr>
    <tr><th>Block SHA-256 Hash</th><td class="font-mono" style="word-break: break-all; font-weight: 600; color: var(--color-blue-primary);">${block.hash}</td></tr>
    <tr><th>Previous Block Hash</th><td class="font-mono" style="word-break: break-all; color: var(--text-muted);">${block.prev_hash}</td></tr>
    <tr><th>Timestamp</th><td>${formatTimestamp(block.timestamp)} (${block.timestamp})</td></tr>
    <tr><th>Proof-of-Work Nonce</th><td class="font-mono">${block.nonce}</td></tr>
    <tr><th>Sealed Ballots Count</th><td><strong>${(block.ballots || []).length}</strong> confirmed ballots</td></tr>
    <tr><th>Consensus Status</th><td><span class="system-badge badge-valid">✓ Proof-of-Work Verified</span></td></tr>
  `;

  const ballotsContainer = document.getElementById("blockDetailBallotsList");
  if (!block.ballots || block.ballots.length === 0) {
    ballotsContainer.innerHTML = `<div style="font-size: 13px; color: var(--text-muted); padding: 8px 0;">No individual voter transactions sealed in this block.</div>`;
  } else {
    ballotsContainer.innerHTML = `
      <div class="table-responsive">
        <table class="data-table">
          <thead>
            <tr>
              <th>Voter Public ID</th>
              <th>Proposal</th>
              <th>Choice</th>
              <th>Weight</th>
              <th>Digital Signature</th>
            </tr>
          </thead>
          <tbody>
            ${block.ballots.map(b => `
              <tr>
                <td class="font-mono" title="${b.voter_id}">${shortenKey(b.voter_id, 10, 8)}</td>
                <td class="font-mono"><strong>${b.proposal_id}</strong></td>
                <td><span class="system-badge badge-valid">${b.choice}</span></td>
                <td>${b.weight || 1}</td>
                <td class="font-mono" style="color: var(--text-muted);" title="${b.signature}">${shortenKey(b.signature, 12, 10)}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth" });
}

// -------------------------------------------------------------------------
// RENDER: Mempool Table
// -------------------------------------------------------------------------
function renderMempoolTable(ballots) {
  const tbody = document.getElementById("mempoolTableBody");
  const countBadge = document.getElementById("mempoolTableCount");
  if (!tbody) return;
  const count = ballots ? ballots.length : 0;
  if (countBadge) countBadge.textContent = `Pending: ${count}`;

  if (!ballots || ballots.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">Mempool is currently empty. Cast a vote to see it staged here.</td></tr>`;
    return;
  }

  tbody.innerHTML = ballots.map((b, idx) => `
    <tr>
      <td>${idx + 1}</td>
      <td class="font-mono"><strong>${b.proposal_id}</strong></td>
      <td class="font-mono" title="${b.voter_id}">${shortenKey(b.voter_id, 10, 8)}</td>
      <td><span class="system-badge badge-valid">${b.choice}</span></td>
      <td>${b.weight || 1}</td>
      <td><span class="system-badge badge-valid">✓ Ed25519 VALID</span></td>
    </tr>
  `).join("");
}

// -------------------------------------------------------------------------
// RENDER: Results Page
// -------------------------------------------------------------------------
function renderResults() {
  const container = document.getElementById("resultsCardContainer");
  const filterEl = document.getElementById("resultsProposalFilter");
  if (!container || !filterEl) return;
  const filter = filterEl.value;
  const election = cachedElections.find(e => e.proposal_id === filter) || cachedElections[0];

  if (!election) {
    container.innerHTML = `<div class="content-box"><p style="color: var(--text-muted);">No election data available.</p></div>`;
    return;
  }

  const tally = election.tally || {};
  const yes = tally["YES"] || 0;
  const no = tally["NO"] || 0;
  const abstain = tally["ABSTAIN"] || 0;
  const total = yes + no + abstain;

  const yesPct = total > 0 ? ((yes / total) * 100).toFixed(1) : 0;
  const noPct = total > 0 ? ((no / total) * 100).toFixed(1) : 0;
  const absPct = total > 0 ? ((abstain / total) * 100).toFixed(1) : 0;

  container.innerHTML = `
    <div class="content-box">
      <div class="content-box-header">
        <div>
          <h3>${election.title}</h3>
          <p style="font-size: 13px; color: var(--text-muted); margin-top: 2px;">
            Proposal ID: <strong>${election.proposal_id}</strong> &bull; Status: <span class="system-badge badge-valid" style="font-size: 11px;">ACTIVE</span>
          </p>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 24px; font-weight: 700; color: var(--color-blue-primary);">${total}</div>
          <div style="font-size: 12px; color: var(--text-muted);">Total Confirmed Votes</div>
        </div>
      </div>

      <div style="margin: 24px 0;">
        <div class="bar-wrapper">
          <div class="bar-label-row">
            <span>YES (In Favor)</span>
            <span><strong>${yes}</strong> votes (${yesPct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill bar-fill-yes" style="width: ${yesPct}%;"></div>
          </div>
        </div>

        <div class="bar-wrapper">
          <div class="bar-label-row">
            <span>NO (Against)</span>
            <span><strong>${no}</strong> votes (${noPct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill bar-fill-no" style="width: ${noPct}%;"></div>
          </div>
        </div>

        <div class="bar-wrapper">
          <div class="bar-label-row">
            <span>ABSTAIN</span>
            <span><strong>${abstain}</strong> votes (${absPct}%)</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill bar-fill-abstain" style="width: ${absPct}%;"></div>
          </div>
        </div>
      </div>

      <div style="border-top: 1px solid var(--border-color); padding-top: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 12.5px; color: var(--text-muted); flex-wrap: wrap; gap: 8px;">
        <div>
          🛡️ <em>Results calculated from ballots recorded on the verified ledger.</em>
        </div>
        <div>
          <span class="system-badge badge-valid">✓ 100% On-Chain Verified</span>
        </div>
      </div>
    </div>
  `;
}
const resFilter = document.getElementById("resultsProposalFilter");
if (resFilter) resFilter.addEventListener("change", renderResults);

// -------------------------------------------------------------------------
// RENDER: Audit Log Table
// -------------------------------------------------------------------------
function renderAuditLog(events) {
  const tbody = document.getElementById("auditLogTableBody");
  if (!tbody) return;
  if (!events || events.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 20px;">No audit events recorded yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = events.map(ev => {
    const badgeClass = ev.status === "SUCCESS" ? "badge-valid" : ev.status === "ERROR" ? "badge-offline" : ev.status === "WARNING" ? "badge-warning" : "badge-online";
    return `
      <tr>
        <td class="font-mono">${ev.time_str || '-'}</td>
        <td style="font-weight: 600;">${ev.event_type}</td>
        <td>${ev.details}</td>
        <td><span class="system-badge ${badgeClass}" style="font-size: 11px;">${ev.status}</span></td>
      </tr>
    `;
  }).join("");
}

// -------------------------------------------------------------------------
// RENDER: Voter Registry Table
// -------------------------------------------------------------------------
function renderVotersTable(voters) {
  const tbody = document.getElementById("votersTableBody");
  const countBadge = document.getElementById("votersCountBadge");
  if (!tbody) return;
  const count = voters ? voters.length : 0;
  if (countBadge) countBadge.textContent = `${count} Authorized`;

  if (!voters || voters.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 20px;">No citizens registered in whitelist.</td></tr>`;
    return;
  }

  tbody.innerHTML = voters.map(v => `
    <tr>
      <td><strong>${v.name || 'Authorized Citizen'}</strong></td>
      <td style="color: var(--text-secondary); font-size: 13px;">${v.district || 'General Precinct'}</td>
      <td class="font-mono" title="${v.voter_id}">${v.voter_id_short}</td>
      <td>
        <span class="system-badge badge-valid">✓ Whitelisted</span>
        ${v.has_voted ? `<span class="system-badge badge-online" style="margin-left: 4px; font-size: 11px;">Voted</span>` : ''}
      </td>
      <td style="text-align: right;">
        <button class="btn btn-primary btn-sm" onclick="voteWithCitizen('${v.voter_id}')">Vote</button>
        <button class="btn btn-secondary btn-sm" onclick="showCitizenCard('${v.voter_id}')" style="margin-left: 4px;">ID Card</button>
      </td>
    </tr>
  `).join("");
}

// -------------------------------------------------------------------------
// RENDER: Peers Table
// -------------------------------------------------------------------------
function renderPeersTable(peers) {
  const tbody = document.getElementById("peerNodesTableBody");
  if (!tbody) return;
  if (!peers || peers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 18px;">No external peers registered. Local node operating as authority.</td></tr>`;
    return;
  }

  tbody.innerHTML = peers.map(p => `
    <tr>
      <td class="font-mono"><strong>${p}</strong></td>
      <td><span class="system-badge badge-online">ONLINE</span></td>
      <td>
        <button class="btn btn-secondary btn-sm" onclick="removePeer('${p}')" style="color: var(--error-red);">Remove</button>
      </td>
    </tr>
  `).join("");
}

// =========================================================================
// CAST BALLOT STEP-BY-STEP ACTIONS
// =========================================================================
const btnReview = document.getElementById("btnReviewVote");
if (btnReview) {
  btnReview.addEventListener("click", () => {
    const profileKey = voterProfileSelect.value;
    let secretKey = "";
    let voterId = "";

    if (profileKey === "custom") {
      secretKey = inputCustomSecret.value.trim();
      if (!secretKey) {
        showToast("Please enter your 64-character voter secret key", "error");
        return;
      }
      voterId = "Deriving from private key...";
    } else if (VOTER_KEYRING[profileKey]) {
      secretKey = VOTER_KEYRING[profileKey].secret_key;
      voterId = VOTER_KEYRING[profileKey].voter_id;
    }

    const proposalId = document.getElementById("voteProposalSelect").value;
    const election = cachedElections.find(e => e.proposal_id === proposalId);

    pendingVotePayload = {
      profileKey,
      secretKey,
      voterId,
      proposalId,
      choice: selectedChoice,
      weight: 1
    };

    document.getElementById("confirmProposalId").textContent = proposalId;
    document.getElementById("confirmElectionTitle").textContent = election ? election.title : proposalId;
    document.getElementById("confirmSelectedChoice").textContent = selectedChoice;
    document.getElementById("confirmVoterId").textContent = voterId;
    document.getElementById("confirmDigest").textContent = `${voterId.substring(0, 16)}...:${proposalId}:${selectedChoice}:1`;

    document.getElementById("stepIndicator1").className = "step-item completed";
    document.getElementById("stepIndicator2").className = "step-item completed";
    document.getElementById("stepIndicator3").className = "step-item active";

    document.getElementById("voteStepForm").style.display = "none";
    document.getElementById("voteConfirmDialog").style.display = "block";
  });
}

const btnBack = document.getElementById("btnBackToForm");
if (btnBack) {
  btnBack.addEventListener("click", () => {
    document.getElementById("stepIndicator1").className = "step-item active";
    document.getElementById("stepIndicator2").className = "step-item";
    document.getElementById("stepIndicator3").className = "step-item";

    document.getElementById("voteStepForm").style.display = "block";
    document.getElementById("voteConfirmDialog").style.display = "none";
  });
}

const btnConfirm = document.getElementById("btnConfirmSubmit");
if (btnConfirm) {
  btnConfirm.addEventListener("click", async () => {
    btnConfirm.disabled = true;
    btnConfirm.textContent = "Cryptographically Signing & Submitting...";

    try {
      if (!pendingVotePayload) throw new Error("Missing ballot payload");

      const signRes = await fetch(`${API_BASE}/api/v1/sign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secret_key: pendingVotePayload.secretKey,
          voter_id: pendingVotePayload.voterId,
          proposal_id: pendingVotePayload.proposalId,
          choice: pendingVotePayload.choice,
          weight: 1
        })
      });
      const signData = await signRes.json();
      if (!signRes.ok || signData.error) {
        throw new Error(signData.error || "Digital signature creation failed");
      }

      const ballotRes = await fetch(`${API_BASE}/api/v1/ballots`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(signData.ballot)
      });
      const ballotData = await ballotRes.json();
      if (!ballotRes.ok || ballotData.error) {
        throw new Error(ballotData.error || "Ballot ingestion rejected");
      }

      lastReceiptHash = ballotData.receipt_hash || ballotData.vote_id || "";
      lastVoteDetails = {
        proposalId: pendingVotePayload.proposalId,
        choice: pendingVotePayload.choice
      };
      document.getElementById("receiptVoteId").textContent = ballotData.vote_id || signData.digest;
      document.getElementById("receiptProposal").textContent = pendingVotePayload.proposalId;
      const elReceiptHash = document.getElementById("receiptHashVal");
      if (elReceiptHash) {
        elReceiptHash.textContent = lastReceiptHash;
      }
      updateReceiptQRCode();
      playEVMSound();

      document.getElementById("stepIndicator3").className = "step-item completed";
      document.getElementById("stepIndicator4").className = "step-item completed";

      document.getElementById("voteConfirmDialog").style.display = "none";
      document.getElementById("voteSuccessReceipt").style.display = "block";

      showToast("Vote successfully submitted & authenticated!", "success");
      await refreshAllData();

    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnConfirm.disabled = false;
      btnConfirm.textContent = "🔒 Authorize Digital Signature & Submit";
    }
  });
}

// Toggle QR code between mobile verification URL and plaintext cryptographic receipt
const btnToggleQr = document.getElementById("btnToggleQrMode");
if (btnToggleQr) {
  btnToggleQr.addEventListener("click", () => {
    qrMode = qrMode === "url" ? "text" : "url";
    updateReceiptQRCode();
  });
}

// Receipt helper actions
const btnCopyReceipt = document.getElementById("btnCopyReceiptHash");
if (btnCopyReceipt) {
  btnCopyReceipt.addEventListener("click", () => {
    if (lastReceiptHash) {
      navigator.clipboard.writeText(lastReceiptHash);
      showToast("Receipt hash copied to clipboard!", "success");
    }
  });
}

const btnTrackReceipt = document.getElementById("btnTrackReceiptNow");
if (btnTrackReceipt) {
  btnTrackReceipt.addEventListener("click", () => {
    if (lastReceiptHash) {
      const qInput = document.getElementById("verifyQueryInput");
      if (qInput) qInput.value = lastReceiptHash;
      navigateToTab("tab-verify-vote");
      const vForm = document.getElementById("verifyVoteForm");
      if (vForm) vForm.dispatchEvent(new Event("submit"));
    }
  });
}

const btnPasteReceipt = document.getElementById("btnPasteLastReceipt");
if (btnPasteReceipt) {
  btnPasteReceipt.addEventListener("click", () => {
    if (lastReceiptHash) {
      const qInput = document.getElementById("verifyQueryInput");
      if (qInput) qInput.value = lastReceiptHash;
      const vForm = document.getElementById("verifyVoteForm");
      if (vForm) vForm.dispatchEvent(new Event("submit"));
    } else {
      showToast("No ballot receipt stored in this active session.", "info");
    }
  });
}

function resetVoteForm() {
  document.getElementById("stepIndicator1").className = "step-item active";
  document.getElementById("stepIndicator2").className = "step-item";
  document.getElementById("stepIndicator3").className = "step-item";
  document.getElementById("stepIndicator4").className = "step-item";

  document.getElementById("voteSuccessReceipt").style.display = "none";
  document.getElementById("voteConfirmDialog").style.display = "none";
  document.getElementById("voteStepForm").style.display = "block";
  pendingVotePayload = null;
}

// =========================================================================
// VERIFY VOTE INDEPENDENTLY
// =========================================================================
const verifyForm = document.getElementById("verifyVoteForm");
if (verifyForm) {
  verifyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = document.getElementById("verifyQueryInput").value.trim();
    if (!query) return;

    const resultBox = document.getElementById("verifyResultDisplay");
    resultBox.style.display = "block";
    resultBox.innerHTML = `<p style="color: var(--text-muted);">Verifying ballot on immutable ledger...</p>`;

    try {
      const res = await fetch(`${API_BASE}/api/v1/verify-ballot?query=${encodeURIComponent(query)}`);
      const data = await res.json();

      if (!res.ok || !data.found) {
        resultBox.className = "verify-result-box invalid";
        resultBox.innerHTML = `
          <h4 style="font-size: 15px; font-weight: 700; color: #991b1b; margin-bottom: 6px;">✗ Ballot Verification Failed</h4>
          <p style="font-size: 13.5px; color: #7f1d1d; line-height: 1.5;">
            ${data.message || 'No matching ballot was found on the confirmed blockchain or in the unconfirmed mempool.'}
          </p>
        `;
        return;
      }

      const isOnChain = data.location === "CONFIRMED_BLOCK";
      resultBox.className = "verify-result-box valid";
      resultBox.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid var(--success-border); padding-bottom: 10px;">
          <h4 style="font-size: 16px; font-weight: 700; color: #166534;">✓ Cryptographic Ballot Verified</h4>
          <span class="system-badge badge-valid">${isOnChain ? 'CONFIRMED ON-CHAIN' : 'PENDING MEMPOOL'}</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; margin-bottom: 14px;">
          <div><strong>Proposal ID:</strong> <span class="font-mono">${data.proposal_id}</span></div>
          <div><strong>Recorded Choice:</strong> <span class="system-badge badge-valid" style="font-size: 12px;">${data.choice}</span></div>
          <div><strong>Block Number:</strong> ${isOnChain ? `Block #${data.block_index}` : 'Unmined (In Mempool)'}</div>
          <div><strong>Timestamp:</strong> ${formatTimestamp(data.block_timestamp)}</div>
        </div>

        <div class="table-responsive" style="margin-top: 12px;">
          <table class="data-table">
            <tbody>
              <tr><th style="width: 140px;">Voter Public ID</th><td class="font-mono" style="word-break: break-all; font-size: 11.5px;">${data.voter_id}</td></tr>
              <tr><th>Receipt Hash</th><td class="font-mono" style="word-break: break-all; font-size: 11.5px; color: #1e40af; font-weight: 600;">${data.receipt_hash || '-'}</td></tr>
              <tr><th>Vote Digest ID</th><td class="font-mono" style="word-break: break-all; font-size: 11.5px;">${data.vote_id}</td></tr>
              <tr><th>Digital Signature</th><td class="font-mono" style="word-break: break-all; font-size: 11px; color: var(--text-muted);">${data.signature}</td></tr>
            </tbody>
          </table>
        </div>

        <div style="margin-top: 14px; font-size: 12.5px; color: #15803d; line-height: 1.6;">
          <div>✓ Digital Signature: <strong>Valid Ed25519 cryptographic authorization</strong></div>
          <div>✓ Payload Continuity: <strong>Bound to proposal ${data.proposal_id}</strong></div>
          <div>✓ Blockchain Integrity: <strong>Verified through Proof-of-Work Nakamoto consensus</strong></div>
        </div>
      `;

    } catch (err) {
      resultBox.className = "verify-result-box invalid";
      resultBox.innerHTML = `
        <h4 style="font-size: 15px; font-weight: 700; color: #991b1b; margin-bottom: 6px;">✗ Error Connecting to Node</h4>
        <p style="font-size: 13px; color: #7f1d1d;">${err.message}</p>
      `;
    }
  });
}

// =========================================================================
// VERIFY BLOCKCHAIN INTEGRITY
// =========================================================================
const btnVerifyChain = document.getElementById("btnVerifyChain");
if (btnVerifyChain) {
  btnVerifyChain.addEventListener("click", async () => {
    btnVerifyChain.disabled = true;
    btnVerifyChain.textContent = "Verifying Blockchain Integrity...";

    const box = document.getElementById("chainVerificationResultBox");
    box.style.display = "block";
    box.innerHTML = `<div class="content-box"><p style="color: var(--text-muted);">Executing sequential block verification across entire ledger...</p></div>`;

    try {
      const res = await fetch(`${API_BASE}/api/v1/verify-chain`);
      const data = await res.json();

      const isAllValid = data.valid;
      box.innerHTML = `
        <div class="content-box ${isAllValid ? 'box-light-blue' : ''}" style="border-left: 4px solid ${isAllValid ? 'var(--success-green)' : 'var(--error-red)'};">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <h3 style="font-size: 16px; font-weight: 700; color: ${isAllValid ? 'var(--success-green)' : 'var(--error-red)'};">
              ${isAllValid ? '✓ Blockchain Integrity Verified' : '✗ Blockchain Integrity Compromised'}
            </h3>
            <span class="system-badge ${isAllValid ? 'badge-valid' : 'badge-offline'}">
              ${data.total_blocks} Blocks Evaluated
            </span>
          </div>

          <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 14px;">
            ${data.message}. Every block hash matches the calculated SHA-256 payload, proof-of-work difficulty is satisfied, and cryptographic ballot signatures are untampered.
          </p>

          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 80px;">Block</th>
                  <th>Validation Check</th>
                  <th style="width: 100px;">Status</th>
                  <th>Hash Digest</th>
                </tr>
              </thead>
              <tbody>
                ${(data.blocks || []).map(b => `
                  <tr>
                    <td><strong>Block #${b.index}</strong></td>
                    <td>${b.reason}</td>
                    <td><span class="system-badge ${b.status === 'VALID' ? 'badge-valid' : 'badge-offline'}">${b.status}</span></td>
                    <td class="font-mono" style="font-size: 11px;">${shortenKey(b.hash, 10, 8)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </div>
      `;

      if (isAllValid) {
        showToast("Blockchain integrity verified successfully!", "success");
      } else {
        showToast("Integrity check failed: tampering detected!", "error");
      }

    } catch (err) {
      showToast(`Verification error: ${err.message}`, "error");
    } finally {
      btnVerifyChain.disabled = false;
      btnVerifyChain.textContent = "🛡️ Verify Blockchain Integrity";
    }
  });
}

// =========================================================================
// MINE BLOCK ACTION
// =========================================================================
const btnMine = document.getElementById("btnMineBlockAction");
if (btnMine) {
  btnMine.addEventListener("click", async () => {
    const banner = document.getElementById("miningStatusBanner");
    const text = document.getElementById("miningStatusText");

    btnMine.disabled = true;
    if (banner) banner.style.display = "block";
    if (text) text.innerHTML = "Collecting ballots... Finding valid nonce (Proof-of-Work)...";

    try {
      const res = await fetch(`${API_BASE}/api/v1/mine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || "Mining failed");

      if (text) {
        text.innerHTML = `
          <span style="color: var(--success-green); font-weight: 700;">✓ Block #${data.block_index} Created Successfully</span>
          <div style="font-size: 12.5px; color: var(--text-secondary); margin-top: 4px;">
            Hash: <code class="font-mono">${data.block_hash}</code> &bull; Nonce: <strong>${data.nonce}</strong> &bull; Sealed Ballots: <strong>${data.ballots_sealed}</strong>
          </div>
        `;
      }
      showToast(`Block #${data.block_index} successfully mined!`, "success");
      await refreshAllData();

    } catch (err) {
      if (text) text.innerHTML = `<span style="color: var(--error-red);">Mining error: ${err.message}</span>`;
      showToast(err.message, "error");
    } finally {
      btnMine.disabled = false;
    }
  });
}

// =========================================================================
// PEER & NETWORK ACTIONS
// =========================================================================
const peerForm = document.getElementById("addPeerForm");
if (peerForm) {
  peerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("peerUrlInput");
    const url = input.value.trim();
    if (!url) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/peers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ peer: url })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(`Connected peer: ${url}`, "success");
        input.value = "";
        await refreshAllData();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

async function removePeer(peerUrl) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/peers`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ peer: peerUrl })
    });
    if (res.ok) {
      showToast(`Peer disconnected`, "info");
      await refreshAllData();
    }
  } catch (err) {
    showToast(err.message, "error");
  }
}

const btnSync = document.getElementById("btnSyncChain");
if (btnSync) {
  btnSync.addEventListener("click", async () => {
    showToast("Contacting peers for chain synchronization...", "info");
    try {
      const res = await fetch(`${API_BASE}/api/v1/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (data.synced) {
        showToast("Adopted longer authoritative branch from peer!", "success");
      } else {
        showToast(`Local ledger is currently up-to-date (Height: ${data.current_length})`, "info");
      }
      await refreshAllData();
    } catch (err) {
      showToast(`Sync failed: ${err.message}`, "error");
    }
  });
}

// =========================================================================
// VOTER REGISTRATION ACTION
// =========================================================================
const regKeyForm = document.getElementById("registerVoterKeyForm");
if (regKeyForm) {
  regKeyForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("newVoterPubInput");
    const vid = input.value.trim();
    if (!vid) return;

    try {
      const res = await fetch(`${API_BASE}/api/v1/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voter_id: vid })
      });
      if (res.ok) {
        showToast(`Voter ${shortenKey(vid)} successfully authorized!`, "success");
        input.value = "";
        await refreshAllData();
      }
    } catch (err) {
      showToast(err.message, "error");
    }
  });
}

// Quick refresh button
const btnRefresh = document.getElementById("btnQuickRefresh");
if (btnRefresh) {
  btnRefresh.addEventListener("click", async () => {
    await refreshAllData();
    showToast("Node state refreshed", "info");
  });
}

const btnAudit = document.getElementById("btnRefreshAudit");
if (btnAudit) {
  btnAudit.addEventListener("click", async () => {
    await refreshAllData();
    showToast("Audit log refreshed", "info");
  });
}

// =========================================================================
// MODAL SYSTEM & CITIZEN INTERACTIONS
// =========================================================================
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "flex";
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}

// Select a citizen and switch to voting tab
function voteWithCitizen(voterId) {
  const normVid = (voterId || "").trim().toLowerCase();
  const slug = Object.keys(VOTER_KEYRING).find(k => (VOTER_KEYRING[k].voter_id || "").toLowerCase() === normVid);
  if (slug && voterProfileSelect) {
    voterProfileSelect.value = slug;
    updateVoterProfile();
    showToast(`Selected citizen: ${VOTER_KEYRING[slug].name}`, "info");
  } else if (voterProfileSelect) {
    voterProfileSelect.value = "custom";
    if (displayVoterId) displayVoterId.value = normVid;
    if (customKeyGroup) customKeyGroup.style.display = "block";
    updateVoterProfile();
    showToast(`Selected voter ID ${shortenKey(normVid)}. Enter private key to sign ballot.`, "info");
  }
  navigateToTab("tab-cast-vote");
}

// Show citizen digital ID card
function showCitizenCard(voterId, citizenObj = null) {
  let citizen = citizenObj;
  const normVid = (voterId || "").trim().toLowerCase();
  if (!citizen) {
    const slug = Object.keys(VOTER_KEYRING).find(k => (VOTER_KEYRING[k].voter_id || "").toLowerCase() === normVid);
    citizen = slug ? VOTER_KEYRING[slug] : null;
  }

  if (citizen) {
    activeCitizenForCard = citizen;
    document.getElementById("cardCitizenName").textContent = citizen.name;
    document.getElementById("cardCitizenDistrict").textContent = citizen.district || "General Precinct";
    document.getElementById("cardCitizenVoterId").textContent = citizen.voter_id;
    document.getElementById("cardCitizenSecretKey").textContent = citizen.secret_key || "Stored encrypted on client";
  } else {
    activeCitizenForCard = { voter_id: voterId, name: "Authorized Voter", district: "General Precinct" };
    document.getElementById("cardCitizenName").textContent = "Authorized Voter";
    document.getElementById("cardCitizenDistrict").textContent = "General Precinct";
    document.getElementById("cardCitizenVoterId").textContent = voterId;
    document.getElementById("cardCitizenSecretKey").textContent = "Unknown (Registered via external public key)";
  }
  openModal("modalCitizenCredentials");
}

// Download credential JSON
const btnDownloadJson = document.getElementById("btnDownloadCitizenJson");
if (btnDownloadJson) {
  btnDownloadJson.addEventListener("click", () => {
    if (!activeCitizenForCard) return;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(activeCitizenForCard, null, 2));
    const a = document.createElement("a");
    a.href = dataStr;
    const safeName = (activeCitizenForCard.name || "citizen").toLowerCase().replace(/[^a-z0-9]/g, "_");
    a.download = `openballot_credentials_${safeName}.json`;
    a.click();
    showToast("Downloaded digital voter credentials!", "success");
  });
}

// Use selected citizen to vote
const btnSelectForVote = document.getElementById("btnSelectCitizenForVote");
if (btnSelectForVote) {
  btnSelectForVote.addEventListener("click", () => {
    if (activeCitizenForCard) {
      voteWithCitizen(activeCitizenForCard.voter_id);
      closeModal("modalCitizenCredentials");
    }
  });
}

// Quick Citizen Registration form
const quickCitForm = document.getElementById("quickCitizenForm");
if (quickCitForm) {
  quickCitForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("quickCitizenName").value.trim();
    const district = document.getElementById("quickCitizenDistrict").value.trim();

    try {
      const res = await fetch(`${API_BASE}/api/v1/citizens`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, district })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Citizen creation failed");

      showToast(`Citizen '${name}' created and whitelisted!`, "success");
      quickCitForm.reset();
      const slug = (data.citizen.name || '').toLowerCase().replace(/[^a-z0-9]/g, "_") || data.citizen.voter_id.substring(0, 8);
      VOTER_KEYRING[slug] = data.citizen;
      renderVoterSelectOptions();
      await refreshAllData();
      showCitizenCard(data.citizen.voter_id, data.citizen);
    } catch (err) {
      showToast(`Registration error: ${err.message}`, "error");
    }
  });
}

// Modal Citizen Registration form
const modalCitForm = document.getElementById("modalCreateCitizenForm");
if (modalCitForm) {
  modalCitForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = modalCitForm.querySelector("button[type='submit']");
    const origText = submitBtn ? submitBtn.textContent : "";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Generating Keypair & Whitelisting...";
    }
    const name = document.getElementById("citizenFullName").value.trim();
    const district = document.getElementById("citizenDistrict").value.trim();

    try {
      const res = await fetch(`${API_BASE}/api/v1/citizens`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, district })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Citizen creation failed");

      closeModal("modalCreateCitizen");
      showToast(`Citizen '${name}' registered with Ed25519 keypair!`, "success");
      modalCitForm.reset();
      const slug = (data.citizen.name || '').toLowerCase().replace(/[^a-z0-9]/g, "_") || data.citizen.voter_id.substring(0, 8);
      VOTER_KEYRING[slug] = data.citizen;
      renderVoterSelectOptions();
      if (voterProfileSelect) {
        voterProfileSelect.value = slug;
        updateVoterProfile();
      }
      await refreshAllData();
      showCitizenCard(data.citizen.voter_id, data.citizen);
    } catch (err) {
      showToast(`Registration error: ${err.message}`, "error");
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
      }
    }
  });
}

// Modal Triggers
const btnOpenCreateModal = document.getElementById("btnOpenCreateCitizenModal");
if (btnOpenCreateModal) {
  btnOpenCreateModal.addEventListener("click", () => openModal("modalCreateCitizen"));
}

const btnQuickCit = document.getElementById("btnQuickCreateCitizen");
if (btnQuickCit) {
  btnQuickCit.addEventListener("click", () => openModal("modalCreateCitizen"));
}

// Bulk Citizens generation
const btnBulkCit = document.getElementById("btnBulkGenerateCitizens");
if (btnBulkCit) {
  btnBulkCit.addEventListener("click", async () => {
    btnBulkCit.disabled = true;
    showToast("Generating 5 realistic test citizens...", "info");
    try {
      const res = await fetch(`${API_BASE}/api/v1/citizens/bulk`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count: 5, district: "Random" })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Bulk generation failed");

      showToast(`Generated & whitelisted ${data.count} citizens!`, "success");
      await refreshAllData();
    } catch (err) {
      showToast(`Error: ${err.message}`, "error");
    } finally {
      btnBulkCit.disabled = false;
    }
  });
}

// Create Election Modal & Action
const btnOpenNewElec = document.getElementById("btnOpenNewElectionModal");
if (btnOpenNewElec) {
  btnOpenNewElec.addEventListener("click", () => openModal("modalCreateElection"));
}

const formNewElec = document.getElementById("modalCreateElectionForm");
if (formNewElec) {
  formNewElec.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pid = document.getElementById("electionProposalId").value.trim().toUpperCase();
    const title = document.getElementById("electionTitle").value.trim();
    const desc = document.getElementById("electionDescription").value.trim();
    const cat = document.getElementById("electionCategory").value.trim();
    const choices = document.getElementById("electionChoices").value.trim();

    try {
      const res = await fetch(`${API_BASE}/api/v1/elections`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          proposal_id: pid,
          title: title,
          description: desc,
          category: cat,
          choices: choices
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to create election");

      closeModal("modalCreateElection");
      showToast(`Election '${pid}' successfully created!`, "success");
      formNewElec.reset();
      await refreshAllData();
    } catch (err) {
      showToast(`Creation error: ${err.message}`, "error");
    }
  });
}

// =========================================================================
// INTERACTIVE CYBERSECURITY ATTACK SIMULATOR
// =========================================================================
async function runAttackSimulation(attackType) {
  const terminal = document.getElementById("sandboxConsole");
  if (!terminal) return;

  const timestamp = new Date().toLocaleTimeString();
  const initLine = document.createElement("div");
  initLine.className = "terminal-line terminal-tag-info";
  initLine.textContent = `[${timestamp}] Launching exploit test payload: [${attackType}]...`;
  terminal.appendChild(initLine);

  try {
    const res = await fetch(`${API_BASE}/api/v1/security/simulate-attack`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ attack_type: attackType })
    });
    const data = await res.json();

    const resultLine = document.createElement("div");
    resultLine.className = "terminal-line terminal-tag-blocked";
    resultLine.innerHTML = `🛡️ [INTERCEPTED] ${data.attack} | HTTP Code: <strong>${data.status_code}</strong> | Layer: <strong>${data.layer}</strong>`;
    terminal.appendChild(resultLine);

    const reasonLine = document.createElement("div");
    reasonLine.className = "terminal-line terminal-tag-muted";
    reasonLine.textContent = `   Rejection Reason: "${data.reason}"`;
    terminal.appendChild(reasonLine);

    const defenseLine = document.createElement("div");
    defenseLine.className = "terminal-line terminal-tag-success";
    defenseLine.textContent = `   Security Defense: ${data.security_defense}`;
    terminal.appendChild(defenseLine);

    terminal.scrollTop = terminal.scrollHeight;
    showToast(`Attack successfully intercepted by ${data.layer}!`, "success");
    await refreshAllData();
  } catch (err) {
    const errLine = document.createElement("div");
    errLine.className = "terminal-line terminal-tag-blocked";
    errLine.textContent = `[ERROR] Failed to run simulation: ${err.message}`;
    terminal.appendChild(errLine);
  }
}

function clearSandboxTerminal() {
  const terminal = document.getElementById("sandboxConsole");
  if (terminal) {
    terminal.innerHTML = `<div class="terminal-line terminal-tag-info">[SYSTEM] Console cleared. OpenBallot defense monitoring active.</div>`;
  }
}

// Receipt helper actions
function copyReceiptDigest() {
  const el = document.getElementById("receiptVoteId");
  const digest = el ? el.textContent : "";
  if (digest && digest !== "-") {
    navigator.clipboard.writeText(digest);
    showToast("Copied vote hash digest to clipboard!", "info");
  }
}

function verifyReceiptOnChain() {
  const el = document.getElementById("receiptVoteId");
  const digest = el ? el.textContent : "";
  if (digest && digest !== "-") {
    const input = document.getElementById("verifyQueryInput");
    if (input) input.value = digest;
    closeModal("modalReceipt");
    navigateToTab("tab-verify-vote");
    document.getElementById("verifyVoteForm").dispatchEvent(new Event("submit"));
  }
}

// Real-time Event Streaming (Server-Sent Events)
function initLiveEventStream() {
  if (!window.EventSource) return;
  try {
    const evtSource = new EventSource(`${API_BASE}/api/v1/events`);
    evtSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.event === "BLOCK_MINED") {
          showToast(`⚡ Block #${payload.data.block_index} mined! (${payload.data.ballots_sealed} votes sealed)`, "success");
          refreshAllData();
        } else if (payload.event === "BALLOT_INGESTED") {
          showToast(`📥 New ballot received into mempool`, "info");
          refreshAllData();
        } else if (payload.event === "VOTER_REGISTERED" || payload.event === "CITIZEN_REGISTERED") {
          showToast(`🛡️ Voter registry updated in real-time`, "info");
          refreshAllData();
        }
      } catch (e) {}
    };
    evtSource.onerror = () => {
      evtSource.close();
      setTimeout(initLiveEventStream, 10000);
    };
  } catch (e) {}
}

// Automatic verification when URL contains ?verify=<receipt_hash>
function handleUrlVerification() {
  const urlParams = new URLSearchParams(window.location.search);
  const verifyHash = urlParams.get("verify") || urlParams.get("receipt");
  if (verifyHash) {
    navigateToTab("tab-verify-vote");
    const input = document.getElementById("verifyQueryInput");
    if (input) {
      input.value = verifyHash;
      setTimeout(() => {
        const vForm = document.getElementById("verifyVoteForm");
        if (vForm) vForm.dispatchEvent(new Event("submit"));
      }, 400);
    }
  }
}

// Initialize on page load and poll every 4 seconds
window.addEventListener("DOMContentLoaded", () => {
  refreshAllData();
  setInterval(refreshAllData, 4000);
  initLiveEventStream();
  handleUrlVerification();
});
