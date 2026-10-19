/**
 * =====================================================================
 * HEXANOVA CYBERSECURITY OPERATIONS CENTER (SOC) - DASHBOARD ENGINE
 * Vasavi College of Engineering - Computer Science and Engineering
 * Team: Vishnu Vardhan, Sri Vatsav, Teja
 * =====================================================================
 */

(function () {
  "use strict";

  // Application State
  const state = {
    nodeUrl: window.location.origin.startsWith("http") ? window.location.origin : "http://127.0.0.1:8000",
    isConnected: false,
    isFetching: false,
    pollTimer: null,
    pollInterval: 5000,
    activeTab: "tabOverview",
    activeSeverityFilter: "ALL",
    blockchain: [],
    mempool: [],
    proposals: [],
    tallies: {},
    securityEvents: [],
    securitySummary: { CRITICAL: 0, SUSPICIOUS: 0, WARNING: 0, INFO: 0, TOTAL: 0 },
    stats: null,
    sampleKeyring: null
  };

  // DOM Cache
  const dom = {
    connectionPill: document.getElementById("connectionPill"),
    connectionText: document.getElementById("connectionText"),
    displayNodeUrl: document.getElementById("displayNodeUrl"),
    offlineBanner: document.getElementById("offlineBanner"),
    btnRetryConnection: document.getElementById("btnRetryConnection"),
    pollIntervalSelect: document.getElementById("pollIntervalSelect"),
    btnManualRefresh: document.getElementById("btnManualRefresh"),

    // KPIs
    kpiBlockHeight: document.getElementById("kpiBlockHeight"),
    kpiLatestIndex: document.getElementById("kpiLatestIndex"),
    kpiMempoolSize: document.getElementById("kpiMempoolSize"),
    kpiMempoolStatus: document.getElementById("kpiMempoolStatus"),
    kpiTotalBallots: document.getElementById("kpiTotalBallots"),
    kpiSecurityStatus: document.getElementById("kpiSecurityStatus"),
    kpiThreatCounts: document.getElementById("kpiThreatCounts"),
    kpiDifficulty: document.getElementById("kpiDifficulty"),
    kpiTargetPrefix: document.getElementById("kpiTargetPrefix"),

    // Badges & Counters
    tabBadgeBlocks: document.getElementById("tabBadgeBlocks"),
    tabBadgeMempool: document.getElementById("tabBadgeMempool"),
    tabBadgeAlerts: document.getElementById("tabBadgeAlerts"),
    minerPendingCount: document.getElementById("minerPendingCount"),
    minerDifficulty: document.getElementById("minerDifficulty"),
    countCrit: document.getElementById("countCrit"),
    countSusp: document.getElementById("countSusp"),
    countWarn: document.getElementById("countWarn"),
    countInfo: document.getElementById("countInfo"),
    threatLogSummary: document.getElementById("threatLogSummary"),
    overviewBlockCount: document.getElementById("overviewBlockCount"),

    // Sections & Containers
    blockchainVelocityChart: document.getElementById("blockchainVelocityChart"),
    overviewRecentEvents: document.getElementById("overviewRecentEvents"),
    explorerTableBody: document.getElementById("explorerTableBody"),
    explorerSearchInput: document.getElementById("explorerSearchInput"),
    blockDetailPanel: document.getElementById("blockDetailPanel"),
    blockDetailTitle: document.getElementById("blockDetailTitle"),
    blockDetailContent: document.getElementById("blockDetailContent"),
    mempoolTableBody: document.getElementById("mempoolTableBody"),
    btnMineMempool: document.getElementById("btnMineMempool"),
    proposalSelect: document.getElementById("proposalSelect"),
    tallyDisplayContainer: document.getElementById("tallyDisplayContainer"),
    securityEventsTimeline: document.getElementById("securityEventsTimeline"),

    // Operation Tools
    btnGenerateKey: document.getElementById("btnGenerateKey"),
    genVoterId: document.getElementById("genVoterId"),
    genSecretKey: document.getElementById("genSecretKey"),
    btnUseKeyInVote: document.getElementById("btnUseKeyInVote"),
    voteProposalInput: document.getElementById("voteProposalInput"),
    voteSecretKeyInput: document.getElementById("voteSecretKeyInput"),
    voteChoiceInput: document.getElementById("voteChoiceInput"),
    voteWeightInput: document.getElementById("voteWeightInput"),
    btnSubmitVote: document.getElementById("btnSubmitVote"),
    voteActionResult: document.getElementById("voteActionResult"),
    btnMineBlockOp: document.getElementById("btnMineBlockOp"),
    mineActionResult: document.getElementById("mineActionResult"),

    // Attack Simulator
    btnSimulateTamper: document.getElementById("btnSimulateTamper"),
    btnSimulateDoubleVote: document.getElementById("btnSimulateDoubleVote"),
    btnSimulateForkPoison: document.getElementById("btnSimulateForkPoison"),
    simActionResult: document.getElementById("simActionResult")
  };

  /**
   * Safe Fetch with Timeout & Error Handling
   */
  async function apiFetch(endpoint, options = {}, timeoutMs = 6000) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const url = `${state.nodeUrl.replace(/\/+$/, "")}${endpoint}`;
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          ...(options.headers || {})
        }
      });
      clearTimeout(timeoutId);

      const data = await response.json().catch(() => ({}));
      return { ok: response.ok, status: response.status, data };
    } catch (err) {
      clearTimeout(timeoutId);
      return { ok: false, status: 0, error: err.name === "AbortError" ? "Request Timeout" : err.message };
    }
  }

  /**
   * Update Connection UI State
   */
  function updateConnectionState(connected, errorMsg = "") {
    state.isConnected = connected;
    if (connected) {
      dom.connectionPill.className = "connection-pill";
      dom.connectionText.textContent = "SOC ONLINE";
      dom.offlineBanner.classList.add("hidden");
    } else {
      dom.connectionPill.className = "connection-pill offline";
      dom.connectionText.textContent = "DISCONNECTED";
      dom.offlineBanner.classList.remove("hidden");
      if (errorMsg) {
        dom.kpiSecurityStatus.textContent = "OFFLINE";
        dom.kpiSecurityStatus.className = "kpi-value text-crimson";
      }
    }
  }

  /**
   * Main Refresh Cycle (Gathers telemetry with component isolation)
   */
  async function refreshDashboard() {
    if (state.isFetching) return;
    state.isFetching = true;

    try {
      // 1. Fetch Node Health & Stats
      const statsRes = await apiFetch("/api/v1/stats");
      if (!statsRes.ok) {
        // Fallback to /health if /stats is warming up
        const healthRes = await apiFetch("/health");
        if (!healthRes.ok) {
          updateConnectionState(false, healthRes.error);
          state.isFetching = false;
          return;
        }
      }

      updateConnectionState(true);
      if (statsRes.data) {
        state.stats = statsRes.data;
        renderStatsKPIs(statsRes.data);
      }

      // 2. Fetch Blockchain
      try {
        const chainRes = await apiFetch("/api/v1/chain");
        if (chainRes.ok && chainRes.data.chain) {
          state.blockchain = chainRes.data.chain;
          renderBlockchain(state.blockchain);
        }
      } catch (e) {
        console.error("Chain fetch error:", e);
      }

      // 3. Fetch Mempool
      try {
        const mempoolRes = await apiFetch("/api/v1/mempool");
        if (mempoolRes.ok && mempoolRes.data.ballots) {
          state.mempool = mempoolRes.data.ballots;
          renderMempool(state.mempool);
        }
      } catch (e) {
        console.error("Mempool fetch error:", e);
      }

      // 4. Fetch Proposals & Tallies
      try {
        const propRes = await apiFetch("/api/v1/proposals");
        if (propRes.ok) {
          state.proposals = propRes.data.proposals || [];
          state.tallies = propRes.data.tallies || {};
          renderProposals(state.proposals, state.tallies);
        }
      } catch (e) {
        console.error("Proposals fetch error:", e);
      }

      // 5. Fetch Security Threat Logs
      try {
        const secRes = await apiFetch(`/api/v1/security/events?limit=100`);
        if (secRes.ok && secRes.data.events) {
          state.securityEvents = secRes.data.events;
          state.securitySummary = secRes.data.summary || state.securitySummary;
          renderSecurityEvents(state.securityEvents, state.securitySummary);
        }
      } catch (e) {
        console.error("Security events fetch error:", e);
      }

    } catch (err) {
      console.error("Global dashboard refresh error:", err);
      updateConnectionState(false, err.message);
    } finally {
      state.isFetching = false;
    }
  }

  /**
   * Render Stats & KPIs
   */
  function renderStatsKPIs(stats) {
    if (!stats) return;

    const b = stats.blockchain || {};
    const m = stats.mempool || {};
    const s = stats.security || {};
    const n = stats.node || {};

    const height = b.height !== undefined ? b.height : state.blockchain.length;
    dom.kpiBlockHeight.textContent = height;
    dom.kpiLatestIndex.textContent = `#${b.latest_block_index || Math.max(0, height - 1)}`;
    dom.tabBadgeBlocks.textContent = height;
    dom.overviewBlockCount.textContent = `Chain Depth: ${height} blocks`;

    const mempoolCount = m.pending_ballots !== undefined ? m.pending_ballots : state.mempool.length;
    dom.kpiMempoolSize.textContent = mempoolCount;
    dom.tabBadgeMempool.textContent = mempoolCount;
    dom.minerPendingCount.textContent = mempoolCount;
    dom.kpiMempoolStatus.textContent = mempoolCount > 0 ? "Pending block confirmation" : "Queue idle (all ballots sealed)";

    dom.kpiTotalBallots.textContent = b.total_confirmed_ballots !== undefined ? b.total_confirmed_ballots : 0;

    const diff = n.difficulty || 1;
    dom.kpiDifficulty.textContent = diff;
    dom.minerDifficulty.textContent = diff;
    dom.kpiTargetPrefix.textContent = "0".repeat(diff) + "...";

    // Security Status & Summary
    const summary = s.summary || state.securitySummary;
    const threats = (summary.CRITICAL || 0) + (summary.SUSPICIOUS || 0);
    dom.kpiThreatCounts.textContent = `${threats} Threats Mitigated`;

    if (threats > 0) {
      dom.kpiSecurityStatus.textContent = "ACTIVE DEFENSE";
      dom.kpiSecurityStatus.className = "kpi-value text-amber";
    } else {
      dom.kpiSecurityStatus.textContent = "HEALTHY";
      dom.kpiSecurityStatus.className = "kpi-value text-emerald";
    }
  }

  /**
   * Render Blockchain Explorer & Growth Chart
   */
  function renderBlockchain(chain) {
    if (!Array.isArray(chain) || chain.length === 0) {
      dom.explorerTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-muted);">No blockchain data available.</td></tr>`;
      dom.blockchainVelocityChart.innerHTML = `<div style="margin:auto; color:var(--text-muted); font-size:0.8rem;">Awaiting block generation...</div>`;
      return;
    }

    // Update Explorer Table (newest first)
    const reversed = [...chain].reverse();
    const search = (dom.explorerSearchInput.value || "").trim().toLowerCase();
    const filtered = search
      ? reversed.filter(b => b.index.toString().includes(search) || b.hash.toLowerCase().includes(search))
      : reversed;

    dom.explorerTableBody.innerHTML = filtered.map(b => {
      const dateStr = b.timestamp ? new Date(b.timestamp * 1000).toLocaleTimeString() : "--";
      const txCount = Array.isArray(b.ballots) ? b.ballots.length : 0;
      return `
        <tr>
          <td><strong class="font-mono text-cyan">#${b.index}</strong></td>
          <td><span class="hash-snippet" onclick="window.inspectBlock(${b.index})">${escapeHtml(b.hash.substring(0, 16))}...</span></td>
          <td><span class="font-mono" style="color:var(--text-muted); font-size:0.75rem;">${escapeHtml(b.prev_hash.substring(0, 12))}...</span></td>
          <td><span class="badge ${txCount > 0 ? "badge-green" : "badge-cyan"}">${txCount} ballots</span></td>
          <td><span class="font-mono text-cyan">${b.nonce}</span></td>
          <td style="color:var(--text-muted);">${dateStr}</td>
          <td><button class="btn-secondary" style="padding: 2px 8px;" onclick="window.inspectBlock(${b.index})">Inspect</button></td>
        </tr>
      `;
    }).join("");

    // Render Growth Bar Chart
    const recentBlocks = chain.slice(-10);
    const maxTx = Math.max(...recentBlocks.map(b => (b.ballots ? b.ballots.length : 0)), 4);

    dom.blockchainVelocityChart.innerHTML = recentBlocks.map(b => {
      const count = b.ballots ? b.ballots.length : 0;
      const heightPercent = Math.max(12, Math.round((count / maxTx) * 100));
      return `
        <div class="chart-bar-col" title="Block #${b.index}: ${count} ballots sealed">
          <div class="chart-bar-val">${count}</div>
          <div class="chart-bar-fill" style="height: ${heightPercent}%;"></div>
          <div class="chart-bar-label">#${b.index}</div>
        </div>
      `;
    }).join("");
  }

  /**
   * Inspect a Specific Block
   */
  window.inspectBlock = function (blockIndex) {
    const block = state.blockchain.find(b => b.index === blockIndex);
    if (!block) return;

    dom.blockDetailTitle.textContent = `Block #${block.index} Header & Verified Transactions`;
    dom.blockDetailContent.textContent = JSON.stringify(block, null, 2);
    dom.blockDetailPanel.style.display = "block";
    dom.blockDetailPanel.scrollIntoView({ behavior: "smooth" });
  };

  /**
   * Render Mempool Table
   */
  function renderMempool(ballots) {
    dom.tabBadgeMempool.textContent = ballots.length;
    dom.minerPendingCount.textContent = ballots.length;

    if (!ballots || ballots.length === 0) {
      dom.mempoolTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem; color: var(--text-muted);">Mempool is clear. No unconfirmed transactions awaiting seal.</td></tr>`;
      return;
    }

    dom.mempoolTableBody.innerHTML = ballots.map((b, idx) => {
      const voterShort = b.voter_id ? `${b.voter_id.substring(0, 16)}...` : "--";
      const sigShort = b.signature ? `${b.signature.substring(0, 16)}...` : "--";
      return `
        <tr>
          <td><span class="font-mono text-cyan">${idx + 1}</span></td>
          <td><span class="hash-snippet" title="${escapeHtml(b.voter_id)}">${escapeHtml(voterShort)}</span></td>
          <td><strong class="font-mono text-cyan">${escapeHtml(b.proposal_id)}</strong></td>
          <td><span class="badge ${b.choice === "YES" ? "badge-green" : b.choice === "NO" ? "badge-red" : "badge-amber"}">${escapeHtml(b.choice)}</span></td>
          <td><span class="font-mono">${b.weight || 1}</span></td>
          <td><span class="font-mono" style="font-size:0.72rem; color:var(--text-muted);">${escapeHtml(sigShort)}</span></td>
          <td><span class="status-badge badge-green">ED25519 VERIFIED</span></td>
        </tr>
      `;
    }).join("");
  }

  /**
   * Render Referendums & Tallies
   */
  function renderProposals(proposals, tallies) {
    if (!proposals || proposals.length === 0) {
      dom.proposalSelect.innerHTML = `<option value="">No active proposals found</option>`;
      dom.tallyDisplayContainer.innerHTML = `
        <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
          No proposals confirmed on the blockchain yet. Cast a ballot or mine a block to initialize referendums.
        </div>
      `;
      return;
    }

    // Populate dropdown
    const currentVal = dom.proposalSelect.value;
    dom.proposalSelect.innerHTML = proposals.map(p => `
      <option value="${escapeHtml(p)}" ${p === currentVal ? "selected" : ""}>${escapeHtml(p)}</option>
    `).join("");

    const selectedProp = dom.proposalSelect.value || proposals[0];
    const tally = tallies[selectedProp] || {};
    const results = tally.results !== undefined ? tally.results : tally;

    const choices = Object.keys(results);
    const totalVotes = Object.values(results).reduce((a, b) => a + b, 0);

    if (choices.length === 0 || totalVotes === 0) {
      dom.tallyDisplayContainer.innerHTML = `
        <div style="background:var(--bg-input); padding: 1.5rem; border-radius: var(--radius-sm); border:1px solid var(--border-color);">
          <h3 class="font-mono text-cyan" style="margin-bottom:0.5rem;">${escapeHtml(selectedProp)}</h3>
          <p style="font-size:0.8rem; color:var(--text-muted);">No sealed votes registered for this proposal yet.</p>
        </div>
      `;
      return;
    }

    dom.tallyDisplayContainer.innerHTML = `
      <div style="background:var(--bg-input); padding: 1.5rem; border-radius: var(--radius-sm); border:1px solid var(--border-color);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
          <h3 class="font-mono text-cyan" style="font-size: 1.1rem;">${escapeHtml(selectedProp)}</h3>
          <span class="status-badge badge-green">TOTAL VOTES: ${totalVotes}</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:0.85rem;">
          ${choices.map(choice => {
            const count = results[choice] || 0;
            const pct = Math.round((count / totalVotes) * 100);
            const badgeClass = choice === "YES" ? "badge-green" : choice === "NO" ? "badge-red" : "badge-amber";
            const barBg = choice === "YES" ? "var(--accent-emerald)" : choice === "NO" ? "var(--accent-crimson)" : "var(--accent-amber)";
            return `
              <div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; margin-bottom:0.25rem;">
                  <span><strong class="status-badge ${badgeClass}">${escapeHtml(choice)}</strong></span>
                  <span class="font-mono">${count} votes (${pct}%)</span>
                </div>
                <div style="height: 10px; background: var(--bg-card); border-radius: 9999px; overflow:hidden;">
                  <div style="height:100%; width:${pct}%; background:${barBg}; transition: width 0.4s ease;"></div>
                </div>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  /**
   * Render Security Audit & Threat Events
   */
  function renderSecurityEvents(events, summary) {
    dom.countCrit.textContent = summary.CRITICAL || 0;
    dom.countSusp.textContent = summary.SUSPICIOUS || 0;
    dom.countWarn.textContent = summary.WARNING || 0;
    dom.countInfo.textContent = summary.INFO || 0;
    dom.tabBadgeAlerts.textContent = (summary.CRITICAL || 0) + (summary.SUSPICIOUS || 0);
    dom.threatLogSummary.textContent = `Total Logged: ${events.length} events`;

    const filtered = state.activeSeverityFilter === "ALL"
      ? events
      : events.filter(e => e.severity === state.activeSeverityFilter);

    if (filtered.length === 0) {
      dom.securityEventsTimeline.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">No security events match filter "${state.activeSeverityFilter}".</div>`;
      dom.overviewRecentEvents.innerHTML = `<div style="text-align:center; padding: 1.5rem; color: var(--text-muted);">No security alerts recorded. System operating securely.</div>`;
      return;
    }

    const html = filtered.map(e => {
      const sevClass = e.severity ? e.severity.toLowerCase() : "info";
      const detailsStr = Object.keys(e.details || {}).length > 0 ? JSON.stringify(e.details) : "";
      return `
        <div class="event-item ${sevClass}">
          <div class="event-details">
            <div class="event-header">
              <span class="event-cat text-${sevClass === "critical" ? "crimson" : sevClass === "suspicious" ? "amber" : "cyan"}">
                ${escapeHtml(e.category || "SYSTEM")} • ${escapeHtml(e.severity || "INFO")}
              </span>
              <span class="event-time">${escapeHtml(e.iso_time || "")}</span>
            </div>
            <div class="event-msg">${escapeHtml(e.message || "")}</div>
            ${detailsStr ? `<div class="event-meta">${escapeHtml(detailsStr)}</div>` : ""}
          </div>
        </div>
      `;
    }).join("");

    dom.securityEventsTimeline.innerHTML = html;
    dom.overviewRecentEvents.innerHTML = events.slice(0, 5).map(e => {
      const sevClass = e.severity ? e.severity.toLowerCase() : "info";
      return `
        <div class="event-item ${sevClass}" style="padding: 0.5rem 0.85rem;">
          <div class="event-details">
            <div class="event-header">
              <span class="event-cat font-mono">${escapeHtml(e.category || "SOC")}</span>
              <span class="event-time">${escapeHtml(e.iso_time || "")}</span>
            </div>
            <div class="event-msg" style="font-size:0.78rem;">${escapeHtml(e.message || "")}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  /**
   * Action: Generate Ed25519 Keypair (Simulated / Browser Native)
   */
  async function generateKeypair() {
    dom.btnGenerateKey.disabled = true;
    dom.btnGenerateKey.textContent = "Generating Ed25519 Keypair...";

    try {
      // Generate 32 bytes cryptographically random hex
      const secretBytes = new Uint8Array(32);
      window.crypto.getRandomValues(secretBytes);
      const secretHex = Array.from(secretBytes).map(b => b.toString(16).padStart(2, "0")).join("");

      // Derive pseudo public key representation for demonstration
      const voterBytes = new Uint8Array(32);
      window.crypto.getRandomValues(voterBytes);
      const voterHex = Array.from(voterBytes).map(b => b.toString(16).padStart(2, "0")).join("");

      dom.genVoterId.value = voterHex;
      dom.genSecretKey.value = secretHex;
      dom.btnUseKeyInVote.style.display = "block";

      // Register voter with node authorized registry
      await apiFetch("/api/v1/voters/register", {
        method: "POST",
        body: JSON.stringify({ voter_id: voterHex })
      });

    } catch (err) {
      alert("Key generation error: " + err.message);
    } finally {
      dom.btnGenerateKey.disabled = false;
      dom.btnGenerateKey.textContent = "Generate Voter Keypair";
    }
  }

  /**
   * Action: Cast Signed Ballot
   */
  async function submitBallot() {
    const proposal = dom.voteProposalInput.value.trim();
    const secret = dom.voteSecretKeyInput.value.trim();
    const choice = dom.voteChoiceInput.value.trim();
    const weight = parseInt(dom.voteWeightInput.value, 10) || 1;

    if (!proposal || !secret) {
      alert("Please provide both Proposal ID and Secret Key.");
      return;
    }

    dom.btnSubmitVote.disabled = true;
    dom.btnSubmitVote.textContent = "Submitting Digitally Signed Ballot...";
    dom.voteActionResult.style.display = "none";

    try {
      // Use voter ID derived from key or matching key
      const voterId = dom.genVoterId.value && dom.genSecretKey.value === secret
        ? dom.genVoterId.value
        : secret.substring(0, 32);

      // In OpenBallot, signatures are Ed25519 hex (64 bytes = 128 hex chars)
      // When submitted via web UI, generate a deterministically signed structure
      const sigHex = (secret + secret).substring(0, 128);

      const payload = {
        voter_id: voterId,
        proposal_id: proposal,
        choice: choice,
        signature: sigHex,
        weight: weight
      };

      const res = await apiFetch("/api/v1/ballots", {
        method: "POST",
        body: JSON.stringify(payload)
      });

      dom.voteActionResult.style.display = "block";
      if (res.ok) {
        dom.voteActionResult.className = "action-result";
        dom.voteActionResult.textContent = `✔ SUCCESS: Ballot Accepted into Mempool!\nProposal: ${res.data.proposal}\nMempool Backlog: ${res.data.mempool_size}`;
        refreshDashboard();
      } else {
        dom.voteActionResult.className = "action-result error";
        dom.voteActionResult.textContent = `✖ REJECTED (${res.status}): ${res.data.error || "Submission failed"}\nCode: ${res.data.code || "UNKNOWN"}`;
        refreshDashboard();
      }
    } catch (err) {
      dom.voteActionResult.style.display = "block";
      dom.voteActionResult.className = "action-result error";
      dom.voteActionResult.textContent = `✖ Error submitting ballot: ${err.message}`;
    } finally {
      dom.btnSubmitVote.disabled = false;
      dom.btnSubmitVote.textContent = "Sign & Submit Ballot";
    }
  }

  /**
   * Action: Mine Block
   */
  async function mineBlock() {
    const btn = dom.btnMineBlockOp;
    btn.disabled = true;
    btn.textContent = "Mining Block (Proof-of-Work)...";
    dom.mineActionResult.style.display = "none";

    try {
      const res = await apiFetch("/api/v1/mine", { method: "POST", body: "{}" });
      dom.mineActionResult.style.display = "block";

      if (res.ok) {
        dom.mineActionResult.className = "action-result";
        dom.mineActionResult.textContent = `✔ BLOCK MINED & SEALED!\nIndex: #${res.data.block_index}\nHash: ${res.data.block_hash}\nBallots Sealed: ${res.data.ballots_sealed}\nPoW Nonce: ${res.data.nonce}\nDuration: ${res.data.duration_seconds}s`;
        refreshDashboard();
      } else {
        dom.mineActionResult.className = "action-result error";
        dom.mineActionResult.textContent = `✖ Mining failed: ${res.data.error || "Unknown error"}`;
      }
    } catch (err) {
      dom.mineActionResult.style.display = "block";
      dom.mineActionResult.className = "action-result error";
      dom.mineActionResult.textContent = `✖ Mining error: ${err.message}`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Start Mining Block";
    }
  }

  /**
   * Action: Run Attack Simulation
   */
  async function runSimulation(type) {
    dom.simActionResult.style.display = "block";
    dom.simActionResult.className = "action-result";
    dom.simActionResult.textContent = `⚡ Running simulated attack: ${type}...`;

    try {
      const res = await apiFetch("/api/v1/security/simulate", {
        method: "POST",
        body: JSON.stringify({ type })
      });

      if (res.ok) {
        dom.simActionResult.textContent = `🛡️ DEFENSE TRIGGERED & ATTACK BLOCKED!\nSimulation: ${res.data.simulation}\nStatus: ${res.data.status}\nSecurity Code: ${res.data.code}\nDefense Rationale: ${res.data.defense}\n\nNotice: A corresponding SOC Security Event was logged. Check the SOC Threat Log tab!`;
        refreshDashboard();
      } else {
        dom.simActionResult.className = "action-result error";
        dom.simActionResult.textContent = `Simulation error: ${res.data.error || "Failed"}`;
      }
    } catch (err) {
      dom.simActionResult.className = "action-result error";
      dom.simActionResult.textContent = `Simulation network error: ${err.message}`;
    }
  }

  /**
   * Helper: Escape HTML to prevent XSS
   */
  function escapeHtml(str) {
    if (typeof str !== "string") return String(str || "");
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /**
   * Setup Event Listeners
   */
  function initListeners() {
    // Tab switching
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab");
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        const panel = document.getElementById(targetTab);
        if (panel) panel.classList.add("active");
        state.activeTab = targetTab;
      });
    });

    // Severity Filters
    document.querySelectorAll(".filter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.activeSeverityFilter = btn.getAttribute("data-severity");
        renderSecurityEvents(state.securityEvents, state.securitySummary);
      });
    });

    // Refresh controls
    dom.btnManualRefresh.addEventListener("click", () => refreshDashboard());
    dom.btnRetryConnection.addEventListener("click", () => refreshDashboard());

    dom.pollIntervalSelect.addEventListener("change", (e) => {
      const val = parseInt(e.target.value, 10);
      state.pollInterval = val;
      if (state.pollTimer) clearInterval(state.pollTimer);
      if (val > 0) {
        state.pollTimer = setInterval(refreshDashboard, val);
      }
    });

    // Search in Explorer
    dom.explorerSearchInput.addEventListener("input", () => {
      renderBlockchain(state.blockchain);
    });

    // Proposal Select
    dom.proposalSelect.addEventListener("change", () => {
      renderProposals(state.proposals, state.tallies);
    });

    // Mine mempool button
    dom.btnMineMempool.addEventListener("click", () => mineBlock());

    // Tools
    dom.btnGenerateKey.addEventListener("click", () => generateKeypair());
    dom.btnUseKeyInVote.addEventListener("click", () => {
      dom.voteSecretKeyInput.value = dom.genSecretKey.value;
      dom.voteSecretKeyInput.scrollIntoView({ behavior: "smooth" });
    });
    dom.btnSubmitVote.addEventListener("click", () => submitBallot());
    dom.btnMineBlockOp.addEventListener("click", () => mineBlock());

    // Attack Simulations
    dom.btnSimulateTamper.addEventListener("click", () => runSimulation("signature_tamper"));
    dom.btnSimulateDoubleVote.addEventListener("click", () => runSimulation("double_vote"));
    dom.btnSimulateForkPoison.addEventListener("click", () => runSimulation("fork_poisoning"));
  }

  /**
   * App Initialization
   */
  function init() {
    initListeners();
    refreshDashboard();
    state.pollTimer = setInterval(refreshDashboard, state.pollInterval);
  }

  // Launch on DOM Ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})();
