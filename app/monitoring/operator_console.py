from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from app.models.approval import ApprovalSubmission
from app.release_control.temporal_service import signal_temporal_approval
from app.services.operator_console_service import build_operator_console_data
from app.services.operator_console_service import record_human_approval

router = APIRouter()


@router.get("/operator-console", response_class=HTMLResponse)
async def operator_console():
    return HTMLResponse(_page_html())


@router.get("/operator-console-data")
async def operator_console_data(use_llm: bool = True, query: str | None = None):
    try:
        return await build_operator_console_data(use_llm=use_llm, operator_query=query)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/operator-approval")
async def operator_approval(submission: ApprovalSubmission):
    if not submission.reviewer.strip():
        raise HTTPException(status_code=400, detail="Reviewer name is required.")
    if not submission.reviewed_business_impact or not submission.reviewed_business_guardrails:
        raise HTTPException(
            status_code=400,
            detail="Review business impact and business guardrails before submitting approval.",
        )
    saved = record_human_approval(submission)
    temporal = await signal_temporal_approval(saved)
    return {
        "saved": saved,
        "temporal": temporal,
    }


def _page_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Operator Console</title>
  <style>
    :root {
      --ink: #132238;
      --muted: #5d6a7d;
      --bg: #f6f3eb;
      --panel: rgba(255,255,255,0.88);
      --line: rgba(19,34,56,0.12);
      --blue: #1c5cff;
      --green: #1f8a4c;
      --orange: #e97912;
      --purple: #5c3ac7;
      --red: #c24747;
      --shadow: 0 24px 60px rgba(19, 34, 56, 0.12);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Trebuchet MS", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(28,92,255,0.10), transparent 30%),
        radial-gradient(circle at top right, rgba(92,58,199,0.09), transparent 28%),
        linear-gradient(180deg, #fffaf1 0%, #f4f0e6 100%);
    }

    .shell {
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }

    .hero {
      padding: 28px;
      border: 1px solid rgba(28,92,255,0.18);
      border-radius: 28px;
      background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(243,247,255,0.86));
      box-shadow: var(--shadow);
      display: grid;
      gap: 20px;
    }

    .hero-top {
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: start;
      flex-wrap: wrap;
    }

    .hero h1 {
      margin: 0;
      font-size: clamp(2rem, 5vw, 3.7rem);
      line-height: 0.98;
      letter-spacing: -0.04em;
      max-width: 8ch;
    }

    .hero p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 1rem;
      max-width: 64ch;
    }

    .hero-controls {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }

    .query-toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }

    .query-toolbar input {
      flex: 1 1 340px;
      border-radius: 16px;
      border: 1px solid rgba(19,34,56,0.12);
      padding: 12px 14px;
      font: inherit;
      background: rgba(255,255,255,0.92);
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(19,34,56,0.05);
      color: var(--ink);
      font-size: 0.95rem;
      border: 1px solid rgba(19,34,56,0.08);
    }

    button, .link-button {
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font: inherit;
      cursor: pointer;
      text-decoration: none;
      transition: transform 140ms ease, box-shadow 140ms ease, opacity 140ms ease;
    }

    button:hover, .link-button:hover { transform: translateY(-1px); }

    .primary {
      background: linear-gradient(135deg, var(--blue), #0f46d6);
      color: white;
      box-shadow: 0 10px 28px rgba(28,92,255,0.28);
    }

    .secondary {
      background: white;
      color: var(--ink);
      border: 1px solid rgba(19,34,56,0.1);
    }

    .meta-row {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }

    .meta-card {
      background: rgba(255,255,255,0.74);
      border: 1px solid rgba(19,34,56,0.08);
      border-radius: 18px;
      padding: 14px 16px;
    }

    .meta-card .label {
      font-size: 0.78rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }

    .meta-card .value {
      font-size: 1.1rem;
      font-weight: 700;
    }

    .stages {
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 12px;
      margin-top: 22px;
    }

    .stage-card {
      padding: 16px 14px;
      background: rgba(255,255,255,0.76);
      border: 1px solid rgba(19,34,56,0.08);
      border-radius: 20px;
      min-height: 116px;
      position: relative;
      overflow: hidden;
    }

    .stage-card::after {
      content: "";
      position: absolute;
      inset: auto 0 0 0;
      height: 5px;
      background: rgba(19,34,56,0.08);
    }

    .stage-card.active::after { background: var(--blue); }
    .stage-card.ready::after,
    .stage-card.approved::after,
    .stage-card.candidate::after,
    .stage-card.baseline-ready::after { background: var(--green); }
    .stage-card.pending::after,
    .stage-card.planned::after { background: var(--orange); }
    .stage-card.rejected::after,
    .stage-card.changes-requested::after { background: var(--red); }

    .stage-number {
      font-size: 0.78rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 10px;
    }

    .stage-title {
      font-size: 1rem;
      font-weight: 800;
      margin-bottom: 12px;
    }

    .stage-status {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(19,34,56,0.06);
      color: var(--ink);
      font-size: 0.82rem;
      font-weight: 700;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.25fr 0.95fr;
      gap: 20px;
      margin-top: 24px;
    }

    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 26px;
      box-shadow: var(--shadow);
      padding: 22px;
      backdrop-filter: blur(8px);
    }

    .panel h2 {
      margin: 0 0 10px;
      font-size: 1.4rem;
      letter-spacing: -0.03em;
    }

    .panel p.lead {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.5;
    }

    .stack { display: grid; gap: 16px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }

    .chip {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(19,34,56,0.06);
      color: var(--ink);
      font-size: 0.88rem;
      font-weight: 600;
    }

    .impact-board {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .impact-tile, .metric-tile, .timeline-stage, .ledger-row, .evidence-box {
      border-radius: 20px;
      background: rgba(255,255,255,0.82);
      border: 1px solid rgba(19,34,56,0.08);
      padding: 16px;
    }

    .impact-tile h3,
    .metric-tile h3,
    .timeline-stage h3 {
      margin: 0 0 8px;
      font-size: 0.98rem;
    }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .metric-value {
      font-size: 1.55rem;
      font-weight: 800;
      letter-spacing: -0.04em;
      margin-top: 8px;
    }

    .muted { color: var(--muted); }

    .timeline {
      display: grid;
      gap: 12px;
    }

    .timeline-stage {
      border-left: 5px solid rgba(28,92,255,0.18);
    }

    .list {
      display: grid;
      gap: 8px;
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
    }

    .approval-box {
      display: grid;
      gap: 14px;
      padding: 18px;
      border-radius: 22px;
      background: linear-gradient(135deg, rgba(28,92,255,0.08), rgba(31,138,76,0.08));
      border: 1px solid rgba(28,92,255,0.12);
    }

    .approval-status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-weight: 700;
      background: rgba(255,255,255,0.88);
    }

    .approval-form {
      display: grid;
      gap: 12px;
    }

    .approval-form input,
    .approval-form textarea {
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(19,34,56,0.12);
      padding: 12px 14px;
      font: inherit;
      background: rgba(255,255,255,0.92);
    }

    .check-row {
      display: grid;
      gap: 10px;
    }

    .check {
      display: flex;
      gap: 10px;
      align-items: start;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.74);
      border: 1px solid rgba(19,34,56,0.08);
      color: var(--ink);
    }

    .approval-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    .shadow-toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 16px;
    }

    .shadow-toolbar input {
      flex: 1 1 240px;
      border-radius: 16px;
      border: 1px solid rgba(19,34,56,0.12);
      padding: 12px 14px;
      font: inherit;
      background: rgba(255,255,255,0.92);
    }

    .control-input {
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(19,34,56,0.12);
      padding: 12px 14px;
      font: inherit;
      background: rgba(255,255,255,0.92);
      margin-top: 12px;
    }

    .comparison-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }

    .mini-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 12px;
    }

    .two-col {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 20px;
      margin-top: 20px;
    }

    .evidence-box pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 0.84rem;
      color: #233047;
    }

    .ledger {
      display: grid;
      gap: 10px;
      max-height: 380px;
      overflow: auto;
      padding-right: 4px;
    }

    .empty {
      padding: 24px;
      border-radius: 20px;
      background: rgba(19,34,56,0.04);
      color: var(--muted);
      border: 1px dashed rgba(19,34,56,0.14);
    }

    .footer-links {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 18px;
    }

    @media (max-width: 1200px) {
      .stages { grid-template-columns: repeat(4, minmax(0, 1fr)); }
      .grid, .two-col, .impact-board, .metric-grid { grid-template-columns: 1fr; }
      .meta-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }

    @media (max-width: 760px) {
      .shell { padding: 16px 14px 36px; }
      .hero { padding: 18px; border-radius: 24px; }
      .stages { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .meta-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="chip">Operator View</div>
          <h1>Incident To Release Console</h1>
          <p>See the full path from signal detection to learning updates. Human approval only unlocks after the business impact and guardrails are reviewed.</p>
        </div>
        <div class="hero-controls">
          <label class="toggle">
            <input type="checkbox" id="use-llm" checked />
            <span>Use Ollama Enrichment</span>
          </label>
          <button class="secondary" id="refresh-button">Refresh</button>
        </div>
      </div>
      <div class="query-toolbar">
        <input id="operator-query" placeholder="Operator query context for incident packet, shadow replay, and release planning" />
        <button class="secondary" id="apply-query">Apply Query</button>
      </div>
      <div class="muted">Use a real customer or incident query to refresh the console around a single search case.</div>
      <div class="meta-row" id="meta-row"></div>
      <div class="stages" id="stage-row"></div>
    </section>

    <div class="two-col">
      <section class="panel">
        <h2>Supervisor Snapshot</h2>
        <p class="lead">A quick supervisory summary of what is failing, where the signals came from, and whether live release routing is currently blocked.</p>
        <div class="chips" id="supervisor-summary"></div>
        <div class="mini-grid" id="supervisor-overview"></div>
      </section>

      <section class="panel">
        <h2>Query Error Inspector</h2>
        <p class="lead">Inspect one search query directly against baseline and candidate behavior, then compare that with related signals and raw ops events.</p>
        <div class="chips" id="query-inspector-summary"></div>
        <div class="stack" id="query-inspector-results" style="margin-top: 14px;"></div>
        <div class="stack" id="query-related-signals" style="margin-top: 14px;"></div>
      </section>
    </div>

    <div class="grid">
      <section class="panel">
        <h2>Business Impact First</h2>
        <p class="lead">This section explains why the incident matters to customers and the business before any approval happens. Review this first, then approve only if the guardrails still make sense.</p>
        <div class="impact-board" id="impact-board"></div>
      </section>

      <section class="panel">
        <h2>Approval Gate</h2>
        <p class="lead">If human approval is required, record it here after reviewing business impact and business guardrails.</p>
        <div class="approval-box">
          <div id="approval-summary"></div>
          <form class="approval-form" id="approval-form">
            <input id="reviewer" name="reviewer" placeholder="Your name" />
            <textarea id="rationale" name="rationale" rows="4" placeholder="Approval note or requested changes"></textarea>
            <div class="check-row">
              <label class="check"><input type="checkbox" id="reviewed-impact" /> <span>I reviewed the business impact and customer effect.</span></label>
              <label class="check"><input type="checkbox" id="reviewed-guardrails" /> <span>I reviewed the business guardrails and rollout gates.</span></label>
            </div>
            <div class="approval-actions">
              <button type="button" class="primary" data-decision="approved">Approve Release</button>
              <button type="button" class="secondary" data-decision="changes-requested">Request Changes</button>
              <button type="button" class="secondary" data-decision="rejected">Reject</button>
            </div>
          </form>
          <div class="muted" id="approval-feedback"></div>
        </div>
      </section>
    </div>

    <div class="two-col">
      <section class="panel">
        <h2>Release Plan</h2>
        <p class="lead">The rollout flow follows shadow to canary to promotion, with explicit rollback triggers on each step.</p>
        <div class="impact-tile" style="margin-bottom: 16px;">
          <h3>Temporal Orchestration</h3>
          <div class="muted" style="margin-bottom: 12px;">Approval and release phase changes are backed by a durable Temporal workflow.</div>
          <div class="chips" id="temporal-summary"></div>
          <div class="footer-links" id="temporal-links"></div>
          <input class="control-input" id="temporal-note" placeholder="Optional note for refresh, phase change, or rollback" />
          <div class="approval-actions" style="margin-top: 12px;">
            <button class="secondary" id="temporal-refresh">Refresh Workflow</button>
            <button class="secondary" id="shadow-index-sync">Sync Candidate Index</button>
            <button class="secondary" data-temporal-phase="canary-5">Canary 5%</button>
            <button class="secondary" data-temporal-phase="canary-25">Canary 25%</button>
            <button class="secondary" data-temporal-phase="promote-100">Promote 100%</button>
            <button class="secondary" data-temporal-phase="completed">Mark Complete</button>
            <button class="secondary" id="temporal-rollback">Rollback</button>
          </div>
          <div class="muted" id="temporal-status-note" style="margin-top: 10px;"></div>
          <div class="ledger" id="temporal-history" style="margin-top: 14px;"></div>
        </div>
        <div class="timeline" id="release-timeline"></div>
      </section>

      <section class="panel">
        <h2>Observe And Compare</h2>
        <p class="lead">These baselines and watchlists are what the operator should compare against before promotion.</p>
        <div class="impact-tile" style="margin-bottom: 16px;">
          <h3>Shadow Replay</h3>
          <div class="muted" style="margin-bottom: 12px;">Mirror the baseline queries into a candidate index before any canary rollout.</div>
          <div class="shadow-toolbar">
            <input id="shadow-query" placeholder="Optional custom query for side-by-side replay" />
            <button class="secondary" id="shadow-run-query">Run Query</button>
            <button class="secondary" id="shadow-run-eval">Run Incident Eval Set</button>
          </div>
          <div class="chips" id="shadow-summary"></div>
          <div class="muted" id="shadow-feedback" style="margin-top: 10px;"></div>
          <div class="stack" id="shadow-comparisons" style="margin-top: 14px;"></div>
        </div>
        <div class="metric-grid" id="metric-grid"></div>
        <div class="stack" style="margin-top: 16px;">
          <div class="impact-tile">
            <h3>Promotion Gates</h3>
            <div class="list" id="promotion-gates"></div>
          </div>
          <div class="impact-tile">
            <h3>Live Watchlist</h3>
            <div class="list" id="watchlist"></div>
          </div>
        </div>
      </section>
    </div>

    <div class="two-col">
      <section class="panel">
        <h2>Learn And Update</h2>
        <p class="lead">The feedback engine closes the loop by updating thresholds, watchlists, runbooks, and approval policy hints.</p>
        <div class="impact-tile" style="margin-bottom: 16px;">
          <h3>Automation State</h3>
          <div class="chips" id="feedback-automation-summary"></div>
          <div class="approval-actions" style="margin-top: 14px;">
            <button class="secondary" id="toggle-automation">Disable automation</button>
            <button class="secondary" id="toggle-auto-promote">Disable auto promote</button>
            <button class="secondary" id="toggle-auto-rollback">Disable auto rollback</button>
            <button class="secondary" id="reset-automation-override">Reset to global defaults</button>
          </div>
          <div class="muted" id="feedback-control-note" style="margin-top: 10px;"></div>
          <div class="list" id="feedback-threshold-updates" style="margin-top: 12px;"></div>
          <div class="list" id="feedback-policy-updates" style="margin-top: 12px;"></div>
        </div>
        <div class="stack" id="learning-list"></div>
      </section>

      <section class="panel">
        <h2>Audit Ledger</h2>
        <p class="lead">Release evidence is durable and survives app restarts. This is the operator history trail.</p>
        <div class="chips" id="ledger-backend"></div>
        <div class="ledger" id="ledger-list" style="margin-top: 14px;"></div>
        <div class="impact-tile" style="margin-top: 16px;">
          <h3>Recent Feedback Outcomes</h3>
          <div class="stack" id="feedback-outcome-list"></div>
        </div>
      </section>
    </div>

    <div class="two-col">
      <section class="panel">
        <h2>Recent Incident Feed</h2>
        <p class="lead">Supervisors can scan the last few detected signals here without expanding raw JSON payloads.</p>
        <div class="stack" id="incident-feed"></div>
      </section>

      <section class="panel">
        <h2>Signal Evidence</h2>
        <p class="lead">The latest signals, diagnostics, and RLM decomposition are here for quick operator context without leaving the page.</p>
        <div class="stack">
          <div class="impact-tile">
            <h3>RLM Decomposition</h3>
            <div class="muted" style="margin-bottom: 12px;">A parent incident orchestrator breaks the problem into capability, data gap, metric impact, and owner-path subtasks, then folds the evidence back into one synthesis.</div>
            <div class="chips" id="rlm-summary"></div>
            <div class="stack" id="rlm-subtasks" style="margin-top: 14px;"></div>
          </div>
          <div class="evidence-box"><pre id="signals-json"></pre></div>
          <div class="evidence-box"><pre id="diagnostics-json"></pre></div>
        </div>
      </section>

      <section class="panel">
        <h2>Exports</h2>
        <p class="lead">Use the generated reports when you want to paste the incident or rollout plan into docs, tickets, or slides.</p>
        <div class="footer-links" id="report-links"></div>
      </section>
    </div>
  </div>

  <script>
    const state = {
      data: null,
      shadowData: null,
      useLlm: true,
      operatorQuery: new URLSearchParams(window.location.search).get("query") || "",
    };

    const metaRow = document.getElementById("meta-row");
    const stageRow = document.getElementById("stage-row");
    const impactBoard = document.getElementById("impact-board");
    const approvalSummary = document.getElementById("approval-summary");
    const approvalFeedback = document.getElementById("approval-feedback");
    const releaseTimeline = document.getElementById("release-timeline");
    const metricGrid = document.getElementById("metric-grid");
    const promotionGates = document.getElementById("promotion-gates");
    const watchlist = document.getElementById("watchlist");
    const shadowSummary = document.getElementById("shadow-summary");
    const shadowFeedback = document.getElementById("shadow-feedback");
    const shadowComparisons = document.getElementById("shadow-comparisons");
    const shadowQueryInput = document.getElementById("shadow-query");
    const temporalSummary = document.getElementById("temporal-summary");
    const temporalLinks = document.getElementById("temporal-links");
    const temporalStatusNote = document.getElementById("temporal-status-note");
    const temporalHistory = document.getElementById("temporal-history");
    const learningList = document.getElementById("learning-list");
    const feedbackAutomationSummary = document.getElementById("feedback-automation-summary");
    const feedbackControlNote = document.getElementById("feedback-control-note");
    const feedbackThresholdUpdates = document.getElementById("feedback-threshold-updates");
    const feedbackPolicyUpdates = document.getElementById("feedback-policy-updates");
    const ledgerBackend = document.getElementById("ledger-backend");
    const ledgerList = document.getElementById("ledger-list");
    const feedbackOutcomeList = document.getElementById("feedback-outcome-list");
    const rlmSummary = document.getElementById("rlm-summary");
    const rlmSubtasks = document.getElementById("rlm-subtasks");
    const signalsJson = document.getElementById("signals-json");
    const diagnosticsJson = document.getElementById("diagnostics-json");
    const reportLinks = document.getElementById("report-links");
    const operatorQueryInput = document.getElementById("operator-query");
    const supervisorSummary = document.getElementById("supervisor-summary");
    const supervisorOverview = document.getElementById("supervisor-overview");
    const queryInspectorSummary = document.getElementById("query-inspector-summary");
    const queryInspectorResults = document.getElementById("query-inspector-results");
    const queryRelatedSignals = document.getElementById("query-related-signals");
    const incidentFeed = document.getElementById("incident-feed");

    operatorQueryInput.value = state.operatorQuery;
    shadowQueryInput.value = state.operatorQuery;

    document.getElementById("use-llm").addEventListener("change", (event) => {
      state.useLlm = event.target.checked;
      loadData();
    });

    document.getElementById("apply-query").addEventListener("click", () => {
      applyOperatorQuery();
    });

    operatorQueryInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        applyOperatorQuery();
      }
    });

    document.getElementById("refresh-button").addEventListener("click", () => loadData());
    document.getElementById("toggle-automation").addEventListener("click", async () => {
      if (!state.data) return;
      const effective = currentEffectiveAutomation();
      await postFeedbackControl({
        incident_id: state.data.incident_packet.incident_id,
        enabled: !(effective.enabled ?? true),
        note: "Operator toggled automation enablement for this incident.",
      });
    });

    document.getElementById("toggle-auto-promote").addEventListener("click", async () => {
      if (!state.data) return;
      const effective = currentEffectiveAutomation();
      await postFeedbackControl({
        incident_id: state.data.incident_packet.incident_id,
        auto_promote_enabled: !(effective.auto_promote_enabled ?? true),
        note: "Operator toggled auto-promote for this incident.",
      });
    });

    document.getElementById("toggle-auto-rollback").addEventListener("click", async () => {
      if (!state.data) return;
      const effective = currentEffectiveAutomation();
      await postFeedbackControl({
        incident_id: state.data.incident_packet.incident_id,
        auto_rollback_enabled: !(effective.auto_rollback_enabled ?? true),
        note: "Operator toggled auto-rollback for this incident.",
      });
    });

    document.getElementById("reset-automation-override").addEventListener("click", async () => {
      if (!state.data) return;
      await postFeedbackControl({
        incident_id: state.data.incident_packet.incident_id,
        clear_override: true,
        note: "Operator reset incident automation controls to global defaults.",
      });
    });

    document.getElementById("shadow-run-query").addEventListener("click", async () => {
      const query = shadowQueryInput.value.trim();
      if (!query) {
        shadowFeedback.textContent = "Enter a query first, or run the incident eval set.";
        return;
      }
      await runShadowTest(query);
    });

    document.getElementById("shadow-run-eval").addEventListener("click", async () => {
      await runShadowTest();
    });

    document.getElementById("temporal-refresh").addEventListener("click", async () => {
      if (!state.data) return;
      await postTemporalAction("/temporal-release-refresh", {
        incident_id: state.data.incident_packet.incident_id,
        note: document.getElementById("temporal-note").value,
      });
    });

    document.getElementById("shadow-index-sync").addEventListener("click", async () => {
      temporalStatusNote.textContent = "Syncing candidate index...";
      try {
        const response = await fetch("/shadow-index-sync?force=true", { method: "POST" });
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Candidate index sync failed.");
        }
        temporalStatusNote.textContent = body.error || "Candidate index synced.";
        await sleep(700);
        await loadData();
      } catch (error) {
        temporalStatusNote.textContent = error.message;
      }
    });

    document.querySelectorAll("[data-temporal-phase]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!state.data) return;
        await postTemporalAction("/temporal-release-phase", {
          incident_id: state.data.incident_packet.incident_id,
          phase: button.dataset.temporalPhase,
          note: document.getElementById("temporal-note").value,
        });
      });
    });

    document.getElementById("temporal-rollback").addEventListener("click", async () => {
      if (!state.data) return;
      await postTemporalAction("/temporal-release-rollback", {
        incident_id: state.data.incident_packet.incident_id,
        reason: document.getElementById("temporal-note").value || "Rollback requested from operator console.",
      });
    });

    document.querySelectorAll("[data-decision]").forEach((button) => {
      button.addEventListener("click", async () => {
        if (!state.data) return;

        const incidentId = state.data.incident_packet.incident_id;
        const payload = {
          incident_id: incidentId,
          reviewer: document.getElementById("reviewer").value,
          decision: button.dataset.decision,
          rationale: document.getElementById("rationale").value,
          reviewed_business_impact: document.getElementById("reviewed-impact").checked,
          reviewed_business_guardrails: document.getElementById("reviewed-guardrails").checked,
        };

        approvalFeedback.textContent = "Saving decision...";

        try {
          const response = await fetch("/operator-approval", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          const body = await response.json();
          if (!response.ok) {
            throw new Error(body.detail || "Approval could not be saved.");
          }
          approvalFeedback.textContent = `Saved: ${body.saved.decision} by ${body.saved.reviewer}`;
          await sleep(600);
          await loadData();
        } catch (error) {
          approvalFeedback.textContent = error.message;
        }
      });
    });

    async function loadData() {
      approvalFeedback.textContent = "";
      shadowFeedback.textContent = "";
      metaRow.innerHTML = "<div class='meta-card'><div class='label'>Status</div><div class='value'>Loading...</div></div>";

      try {
        const params = new URLSearchParams({ use_llm: String(state.useLlm) });
        if (state.operatorQuery) {
          params.set("query", state.operatorQuery);
        }
        const response = await fetch(`/operator-console-data?${params.toString()}`);
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Could not load operator console.");
        }
        const previousQuery = state.operatorQuery;
        state.data = body;
        state.shadowData = body.shadow_test;
        state.operatorQuery = body.operator_query || "";
        operatorQueryInput.value = state.operatorQuery;
        if (!shadowQueryInput.value.trim() || shadowQueryInput.value.trim() === previousQuery) {
          shadowQueryInput.value = body.effective_query || state.operatorQuery || "";
        }
        syncUrlQuery();
        render();
      } catch (error) {
        metaRow.innerHTML = `<div class="meta-card"><div class="label">Error</div><div class="value">${escapeHtml(error.message)}</div></div>`;
      }
    }

    function render() {
      renderMeta();
      renderStages();
      renderSupervisor();
      renderImpact();
      renderApproval();
      renderTemporal();
      renderRelease();
      renderShadow();
      renderObservation();
      renderLearning();
      renderLedger();
      renderIncidentFeed();
      renderRlm();
      renderEvidence();
      renderReports();
    }

    function renderMeta() {
      const packet = state.data.incident_packet;
      const release = state.data.controlled_release_packet;
      const approval = state.data.approval;
      metaRow.innerHTML = [
        metaCard("Incident", packet.incident_id),
        metaCard("Query", state.data.effective_query || "unknown-query"),
        metaCard("Capability", packet.diagnosis.affected_capability),
        metaCard("Severity / Risk", `${packet.diagnosis.severity} / ${release.source_incident.risk_level}`),
        metaCard("Approval", approval.required ? "Human required" : "Auto eligible"),
      ].join("");
    }

    function renderStages() {
      stageRow.innerHTML = state.data.stage_statuses.map((item) => {
        const [number, ...rest] = item.stage.split(" ");
        return `
          <div class="stage-card ${escapeAttr(item.status)}">
            <div class="stage-number">${escapeHtml(number)}</div>
            <div class="stage-title">${escapeHtml(rest.join(" "))}</div>
            <div class="stage-status">${escapeHtml(item.status)}</div>
          </div>
        `;
      }).join("");
    }

    function renderImpact() {
      const impact = state.data.business_impact;
      impactBoard.innerHTML = `
        <div class="impact-tile">
          <h3>Business Impact Summary</h3>
          <p class="muted">${escapeHtml(impact.summary)}</p>
          <div class="chips">
            <div class="chip">Severity: ${escapeHtml(impact.severity)}</div>
            <div class="chip">Risk: ${escapeHtml(impact.risk_level)}</div>
          </div>
        </div>
        <div class="impact-tile">
          <h3>Customer Effect</h3>
          ${asList(impact.customer_effects)}
        </div>
        <div class="impact-tile">
          <h3>Business Effect</h3>
          ${asList(impact.business_effects)}
        </div>
        <div class="impact-tile">
          <h3>Business Guardrails</h3>
          ${asList(impact.guardrails)}
        </div>
      `;
    }

    function renderSupervisor() {
      const supervisor = state.data.supervisor || {};
      const summary = supervisor.signal_summary || {};
      const inspector = supervisor.query_inspector || {};
      supervisorSummary.innerHTML = [
        `<div class="chip">Signals: ${escapeHtml(summary.total_signals ?? 0)}</div>`,
        `<div class="chip">Events: ${escapeHtml(summary.total_events ?? 0)}</div>`,
        `<div class="chip">Capability: ${escapeHtml(summary.active_capability || "unknown")}</div>`,
        `<div class="chip">Phase: ${escapeHtml(summary.release_phase || "baseline")}</div>`,
        `<div class="chip">Live candidate traffic: ${escapeHtml(summary.live_candidate_percent ?? 0)}%</div>`,
        `<div class="chip">Candidate ready: ${summary.candidate_ready ? "yes" : "no"}</div>`,
      ].join("");

      const severityCounts = mapToSummary(summary.severity_counts);
      const capabilityCounts = mapToSummary(summary.capability_counts);
      const signalOrigins = mapToSummary(summary.signal_origin_counts);
      const eventOrigins = mapToSummary(summary.event_origin_counts);
      supervisorOverview.innerHTML = `
        <div class="impact-tile">
          <h3>Severity Split</h3>
          <div class="muted">${escapeHtml(severityCounts)}</div>
        </div>
        <div class="impact-tile">
          <h3>Capability Split</h3>
          <div class="muted">${escapeHtml(capabilityCounts)}</div>
        </div>
        <div class="impact-tile">
          <h3>Signal Origins</h3>
          <div class="muted">${escapeHtml(signalOrigins)}</div>
        </div>
        <div class="impact-tile">
          <h3>Event Origins</h3>
          <div class="muted">${escapeHtml(eventOrigins)}</div>
          <div class="muted" style="margin-top: 8px;">${escapeHtml(summary.blocked_reason || "No live routing block is active.")}</div>
        </div>
      `;

      if (!inspector.available) {
        queryInspectorSummary.innerHTML = `<div class="chip">Inspector unavailable</div>`;
        queryInspectorResults.innerHTML = `<div class="empty">${escapeHtml(inspector.message || "Provide a real query to inspect search behavior.")}</div>`;
        queryRelatedSignals.innerHTML = renderRelatedSignalPanels(inspector.related_signals || [], inspector.related_events || []);
        return;
      }

      queryInspectorSummary.innerHTML = [
        `<div class="chip">Query: ${escapeHtml(inspector.query)}</div>`,
        `<div class="chip">Status: ${escapeHtml(inspector.triage_status || "unknown")}</div>`,
        `<div class="chip">Workflow: ${escapeHtml(inspector.routing.workflow_status || "unknown")}</div>`,
        `<div class="chip">Phase: ${escapeHtml(inspector.routing.release_phase || "baseline")}</div>`,
        `<div class="chip">Canary traffic: ${escapeHtml(inspector.routing.live_candidate_percent ?? 0)}%</div>`,
      ].join("");

      queryInspectorResults.innerHTML = `
        <div class="impact-tile">
          <h3>Triage Note</h3>
          <div class="muted">${escapeHtml(inspector.triage_note || "No triage note available.")}</div>
        </div>
        <div class="comparison-grid">
          ${renderQueryResultCard("Baseline", inspector.baseline)}
          ${renderQueryResultCard("Candidate", inspector.candidate)}
        </div>
        ${renderShadowInspector(inspector.shadow_comparison)}
      `;

      queryRelatedSignals.innerHTML = renderRelatedSignalPanels(inspector.related_signals || [], inspector.related_events || []);
    }

    function renderApproval() {
      const approval = state.data.approval;
      const latest = approval.latest;
      const statusText = latest ? `${latest.decision} by ${latest.reviewer}` : (approval.required ? "Awaiting operator approval" : "Auto approval available");

      approvalSummary.innerHTML = `
        <div class="approval-status">${escapeHtml(statusText)}</div>
        <div class="muted" style="margin-top: 10px;">${escapeHtml(approval.gate_message)}</div>
        <div class="chips" style="margin-top: 12px;">
          <div class="chip">Approval backend: ${escapeHtml(approval.backend)}</div>
          <div class="chip">Audit backend: ${escapeHtml(state.data.audit_ledger.backend)}</div>
          <div class="chip">Temporal: ${escapeHtml(state.data.temporal.workflow_status || state.data.temporal.status || "unavailable")}</div>
        </div>
      `;
    }

    function renderTemporal() {
      const temporal = state.data.temporal || {};
      temporalSummary.innerHTML = [
        `<div class="chip">Workflow: ${escapeHtml(temporal.workflow_status || temporal.status || "unavailable")}</div>`,
        `<div class="chip">Phase: ${escapeHtml(temporal.release_phase || "shadow")}</div>`,
        `<div class="chip">Live candidate traffic: ${escapeHtml((state.data.traffic_router && state.data.traffic_router.live_candidate_percent) ?? 0)}%</div>`,
        `<div class="chip">Shadow mirror: ${state.data.traffic_router && state.data.traffic_router.shadow_mirror_enabled ? "on" : "off"}</div>`,
        `<div class="chip">Namespace: ${escapeHtml(temporal.namespace || "default")}</div>`,
        `<div class="chip">Task queue: ${escapeHtml(temporal.task_queue || "unknown")}</div>`,
      ].join("");
      temporalLinks.innerHTML = temporal.ui_url
        ? `<a class="link-button secondary" href="${escapeAttr(temporal.ui_url)}" target="_blank" rel="noreferrer">Open Temporal UI</a>`
        : `<span class="muted">Temporal UI link is not available for this environment.</span>`;
      temporalStatusNote.textContent = (state.data.traffic_router && state.data.traffic_router.blocked_reason) || temporal.recommended_next_step || temporal.error || "";

      const history = temporal.history || [];
      if (!history.length) {
        temporalHistory.innerHTML = `<div class="empty">Temporal workflow history is not available yet.</div>`;
        return;
      }
      temporalHistory.innerHTML = history.slice().reverse().map((entry) => `
        <div class="ledger-row">
          <strong>${escapeHtml(entry.event)}</strong>
          <div class="muted" style="margin-top: 6px;">${escapeHtml(entry.at)}</div>
          <div style="margin-top: 8px;">${escapeHtml(entry.detail)}</div>
        </div>
      `).join("");
    }

    function renderRelease() {
      const release = state.data.controlled_release_packet.release;
      releaseTimeline.innerHTML = release.traffic_router.map((stage) => `
        <div class="timeline-stage">
          <h3>${escapeHtml(stage.name)} · ${escapeHtml(stage.traffic_percent)}</h3>
          <div class="muted" style="margin-bottom: 8px;">${escapeHtml(stage.objective)}</div>
          <div><strong>Promotion check:</strong> ${escapeHtml(stage.promotion_check)}</div>
          <div style="margin-top: 8px;"><strong>Rollback trigger:</strong> ${escapeHtml(stage.rollback_trigger)}</div>
        </div>
      `).join("");
    }

    function renderShadow() {
      const shadow = state.shadowData;
      if (!shadow) {
        shadowSummary.innerHTML = "";
        shadowComparisons.innerHTML = `<div class="empty">Shadow replay data is not available yet.</div>`;
        return;
      }

      shadowSummary.innerHTML = [
        `<div class="chip">Baseline: ${escapeHtml(shadow.baseline_index)}</div>`,
        `<div class="chip">Candidate: ${escapeHtml(shadow.shadow_index)}</div>`,
        `<div class="chip">Status: ${escapeHtml(shadow.summary.shadow_status)}</div>`,
        `<div class="chip">Ready for canary: ${shadow.summary.ready_for_canary ? "yes" : "no"}</div>`,
        `<div class="chip">Improved queries: ${escapeHtml(shadow.summary.improved_queries)}</div>`,
        `<div class="chip">Regressed queries: ${escapeHtml(shadow.summary.regressed_queries)}</div>`,
      ].join("");
      shadowFeedback.textContent = shadow.recommended_next_step || "";

      const comparisons = shadow.comparisons || [];
      if (!comparisons.length) {
        shadowComparisons.innerHTML = `<div class="empty">No shadow comparisons have been collected yet.</div>`;
        return;
      }

      shadowComparisons.innerHTML = comparisons.map((item) => `
        <div class="impact-tile">
          <h3>${escapeHtml(item.query)}</h3>
          <div class="chips">
            <div class="chip">Outcome: ${escapeHtml(item.delta.outcome)}</div>
            <div class="chip">Result delta: ${escapeHtml(item.delta.results_count)}</div>
            <div class="chip">Latency delta: ${escapeHtml(formatMetric(item.delta.latency_ms))} ms</div>
          </div>
          <div class="comparison-grid">
            <div class="metric-tile">
              <h3>Baseline</h3>
              <div class="muted">${escapeHtml(item.baseline.index)} · ${escapeHtml(item.baseline.status)}</div>
              <div class="metric-value">${escapeHtml(item.baseline.results_count)}</div>
              <div class="muted" style="margin-top: 6px;">${escapeHtml(formatMetric(item.baseline.latency_ms))} ms</div>
              <div class="muted" style="margin-top: 8px;">Top hits: ${escapeHtml(formatHitList(item.baseline.top_hits))}</div>
              ${item.baseline.error ? `<div class="muted" style="margin-top: 8px;">Error: ${escapeHtml(item.baseline.error)}</div>` : ""}
            </div>
            <div class="metric-tile">
              <h3>Candidate</h3>
              <div class="muted">${escapeHtml(item.shadow.index)} · ${escapeHtml(item.shadow.status)}</div>
              <div class="metric-value">${escapeHtml(item.shadow.results_count)}</div>
              <div class="muted" style="margin-top: 6px;">${escapeHtml(formatMetric(item.shadow.latency_ms))} ms</div>
              <div class="muted" style="margin-top: 8px;">Top hits: ${escapeHtml(formatHitList(item.shadow.top_hits))}</div>
              ${item.shadow.error ? `<div class="muted" style="margin-top: 8px;">Error: ${escapeHtml(item.shadow.error)}</div>` : ""}
            </div>
          </div>
        </div>
      `).join("");
    }

    function renderObservation() {
      const observation = state.data.controlled_release_packet.observation;
      metricGrid.innerHTML = observation.baseline_metrics.map((metric) => `
        <div class="metric-tile">
          <h3>${escapeHtml(metric.name)}</h3>
          <div class="muted">${escapeHtml(metric.note)}</div>
          <div class="metric-value">${formatMetric(metric.value)} <span style="font-size:0.92rem; font-weight:600;">${escapeHtml(metric.unit)}</span></div>
          <div class="muted" style="margin-top: 6px;">${escapeHtml(metric.source)} · ${escapeHtml(metric.status)}</div>
        </div>
      `).join("");
      promotionGates.innerHTML = asListItems(observation.promotion_gates);
      watchlist.innerHTML = asListItems(observation.live_watchlist);
    }

    function renderLearning() {
      const learning = state.data.controlled_release_packet.learning;
      const feedback = state.data.feedback || {};
      const automation = feedback.automation || {};
      const effectiveAutomation = currentEffectiveAutomation();
      const incidentOverride = feedback.incident_override || automation.incident_override || null;
      const thresholdUpdates = automation.threshold_updates || (((feedback.state || {}).automation || {}).threshold_updates || []);
      const policyUpdates = automation.policy_updates || (((feedback.state || {}).automation || {}).policy_updates || []);
      learningList.innerHTML = learning.learning_actions.map((action) => `
        <div class="impact-tile">
          <h3>${escapeHtml(action.category)} · ${escapeHtml(action.priority)}</h3>
          <div>${escapeHtml(action.action)}</div>
          <div class="muted" style="margin-top: 8px;">${escapeHtml(action.rationale)}</div>
        </div>
      `).join("");
      feedbackAutomationSummary.innerHTML = [
        `<div class="chip">Enabled: ${escapeHtml(String(effectiveAutomation.enabled ?? true))}</div>`,
        `<div class="chip">Auto promote: ${escapeHtml(String(effectiveAutomation.auto_promote_enabled ?? true))}</div>`,
        `<div class="chip">Auto rollback: ${escapeHtml(String(effectiveAutomation.auto_rollback_enabled ?? true))}</div>`,
        `<div class="chip">Scope: ${escapeHtml(effectiveAutomation.scope || "global-default")}</div>`,
        `<div class="chip">Last guardrail: ${escapeHtml(automation.guardrail_status || effectiveAutomation.last_guardrail_status || "unknown")}</div>`,
        `<div class="chip">Last action: ${escapeHtml((automation.auto_action && automation.auto_action.type) || effectiveAutomation.last_action || "none")}</div>`,
      ].join("");
      document.getElementById("toggle-automation").textContent = (effectiveAutomation.enabled ?? true) ? "Disable automation" : "Enable automation";
      document.getElementById("toggle-auto-promote").textContent = (effectiveAutomation.auto_promote_enabled ?? true) ? "Disable auto promote" : "Enable auto promote";
      document.getElementById("toggle-auto-rollback").textContent = (effectiveAutomation.auto_rollback_enabled ?? true) ? "Disable auto rollback" : "Enable auto rollback";
      document.getElementById("reset-automation-override").disabled = !incidentOverride;
      if (!feedbackControlNote.textContent) {
        feedbackControlNote.textContent = incidentOverride
          ? `Incident override active${incidentOverride.updated_at ? ` · updated ${incidentOverride.updated_at}` : ""}.`
          : "Using global automation defaults for this incident.";
      }
      feedbackThresholdUpdates.innerHTML = thresholdUpdates.length
        ? asListItems(thresholdUpdates.slice().reverse().slice(0, 6).map((item) => `${item.name}: ${item.value} (${item.reason})`))
        : `<div class="empty">No automatic threshold changes recorded yet.</div>`;
      feedbackPolicyUpdates.innerHTML = policyUpdates.length
        ? asListItems(policyUpdates.slice().reverse().slice(0, 6).map((item) => `${item.capability}: manual approval ${item.required ? "enabled" : "disabled"}`))
        : `<div class="empty">No automatic approval-policy changes recorded yet.</div>`;
    }

    function renderLedger() {
      ledgerBackend.innerHTML = `
        <div class="chip">Ledger backend: ${escapeHtml(state.data.audit_ledger.backend)}</div>
        <div class="chip">Approval backend: ${escapeHtml(state.data.approval.backend)}</div>
      `;
      const records = state.data.audit_ledger.records || [];
      if (!records.length) {
        ledgerList.innerHTML = `<div class="empty">No release evidence has been recorded yet.</div>`;
        return;
      }
      ledgerList.innerHTML = records.slice().reverse().map((record) => `
        <div class="ledger-row">
          <strong>${escapeHtml(record.source_signal)}</strong>
          <div class="muted" style="margin-top: 6px;">${escapeHtml(record.created_at)}</div>
          <div style="margin-top: 8px;">Approver: ${escapeHtml(record.approver)} · Eval: ${escapeHtml(record.eval_report)}</div>
          <div class="chips" style="margin-top: 10px;">
            ${(record.rollout_timeline || []).map((stage) => `<div class="chip">${escapeHtml(stage)}</div>`).join("")}
          </div>
        </div>
      `).join("");
      const outcomes = (state.data.feedback && state.data.feedback.recent_outcomes) ? state.data.feedback.recent_outcomes : [];
      feedbackOutcomeList.innerHTML = outcomes.length
        ? outcomes.map((record) => `
          <div class="impact-tile">
            <h3>${escapeHtml(record.outcome_status || "unknown")} · ${escapeHtml(record.signal_type || "unknown")}</h3>
            <div>${escapeHtml(record.incident_id || "unknown-incident")}</div>
            <div class="muted" style="margin-top: 8px;">Capability: ${escapeHtml(record.capability || "unknown")} · Query: ${escapeHtml(record.query || "unknown-query")}</div>
          </div>
        `).join("")
        : `<div class="empty">No feedback outcomes have been recorded yet.</div>`;
    }

    function renderIncidentFeed() {
      const feed = state.data.supervisor && state.data.supervisor.incident_feed ? state.data.supervisor.incident_feed : [];
      if (!feed.length) {
        incidentFeed.innerHTML = `<div class="empty">No recent signals are available for supervisory review yet.</div>`;
        return;
      }
      incidentFeed.innerHTML = feed.map((item) => `
        <div class="ledger-row">
          <strong>${escapeHtml(item.signal_type || "unknown-signal")}</strong>
          <div class="muted" style="margin-top: 6px;">${escapeHtml(item.created_at || "unknown-time")} · ${escapeHtml(item.capability || "unknown")} · ${escapeHtml(item.origin || "unknown")}</div>
          <div style="margin-top: 8px;">Query: ${escapeHtml(item.query || "n/a")} · Severity: ${escapeHtml(item.severity || "info")}</div>
          <div class="muted" style="margin-top: 8px;">${escapeHtml(item.summary || "No summary attached.")}</div>
        </div>
      `).join("");
    }

    function renderRlm() {
      const analysis = state.data.rlm_analysis;
      if (!analysis) {
        rlmSummary.innerHTML = "";
        rlmSubtasks.innerHTML = `<div class="empty">RLM analysis is not available yet.</div>`;
        return;
      }

      const synthesis = analysis.synthesis || {};
      rlmSummary.innerHTML = [
        `<div class="chip">Mode: ${escapeHtml(analysis.mode || "codeact")}</div>`,
        `<div class="chip">Capability: ${escapeHtml(synthesis.affected_capability || "unknown")}</div>`,
        `<div class="chip">Family: ${escapeHtml(synthesis.capability_family || "unknown")}</div>`,
        `<div class="chip">Data gap: ${escapeHtml(synthesis.data_gap || "unknown")}</div>`,
        `<div class="chip">Rollout: ${escapeHtml(synthesis.rollout_readiness || "unknown")}</div>`,
        `<div class="chip">Confidence: ${escapeHtml(synthesis.confidence || "unknown")}</div>`,
      ].join("");

      const subtasks = analysis.subtasks || [];
      rlmSubtasks.innerHTML = subtasks.map((task) => `
        <div class="impact-tile">
          <h3>${escapeHtml(task.title)}</h3>
          <div class="muted" style="margin-bottom: 10px;">${escapeHtml(task.summary)}</div>
          <div class="chips">
            <div class="chip">Status: ${escapeHtml(task.status)}</div>
            <div class="chip">Confidence: ${escapeHtml(task.confidence)}</div>
            <div class="chip">Focus: ${escapeHtml(task.evidence_window.focus)}</div>
          </div>
          <div class="muted" style="margin-top: 10px;"><strong>Actions:</strong> ${escapeHtml((task.recommended_actions || []).join(" | "))}</div>
        </div>
      `).join("");
    }

    function renderEvidence() {
      signalsJson.textContent = JSON.stringify(state.data.signals, null, 2);
      diagnosticsJson.textContent = JSON.stringify(state.data.diagnostics, null, 2);
    }

    function renderReports() {
      const links = state.data.report_links;
      reportLinks.innerHTML = `
        <a class="link-button secondary" href="${escapeAttr(links.incident_report)}" target="_blank" rel="noreferrer">Incident Report</a>
        <a class="link-button secondary" href="${escapeAttr(links.controlled_release_report)}" target="_blank" rel="noreferrer">Controlled Release Report</a>
        <a class="link-button secondary" href="${escapeAttr(links.rlm_analysis)}" target="_blank" rel="noreferrer">RLM Analysis JSON</a>
        <a class="link-button secondary" href="/shadow-test" target="_blank" rel="noreferrer">Shadow Test JSON</a>
        ${links.temporal_ui ? `<a class="link-button secondary" href="${escapeAttr(links.temporal_ui)}" target="_blank" rel="noreferrer">Temporal UI</a>` : ""}
      `;
    }

    async function postTemporalAction(url, payload) {
      temporalStatusNote.textContent = "Sending Temporal workflow signal...";
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Temporal action failed.");
        }
        temporalStatusNote.textContent = body.error || "Temporal workflow updated.";
        await sleep(600);
        await loadData();
      } catch (error) {
        temporalStatusNote.textContent = error.message;
      }
    }

    async function postFeedbackControl(payload) {
      feedbackControlNote.textContent = "Saving incident automation controls...";
      try {
        const response = await fetch("/feedback-incident-controls", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Automation controls could not be updated.");
        }
        const successMessage = body.incident_override
          ? "Incident automation override saved."
          : "Incident automation override cleared. Global defaults are active again.";
        await loadData();
        feedbackControlNote.textContent = successMessage;
      } catch (error) {
        feedbackControlNote.textContent = error.message;
      }
    }

    async function runShadowTest(query = "") {
      shadowFeedback.textContent = "Running shadow replay...";
      shadowComparisons.innerHTML = "";

      try {
        const suffix = query ? `?query=${encodeURIComponent(query)}` : "";
        const response = await fetch(`/shadow-test${suffix}`);
        const body = await response.json();
        if (!response.ok) {
          throw new Error(body.detail || "Could not run shadow replay.");
        }
        state.shadowData = body;
        renderShadow();
      } catch (error) {
        shadowFeedback.textContent = error.message;
      }
    }

    function metaCard(label, value) {
      return `
        <div class="meta-card">
          <div class="label">${escapeHtml(label)}</div>
          <div class="value">${escapeHtml(value)}</div>
        </div>
      `;
    }

    function currentEffectiveAutomation() {
      const feedback = state.data && state.data.feedback ? state.data.feedback : {};
      return feedback.effective_automation
        || (feedback.automation && feedback.automation.effective_automation_policy)
        || ((feedback.state || {}).automation || {});
    }

    function asList(items) {
      return `<ul class="list">${asListItems(items)}</ul>`;
    }

    function asListItems(items) {
      return (items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
    }

    function formatMetric(value) {
      if (value === null || value === undefined) return "n/a";
      const number = Number(value);
      if (Number.isNaN(number)) return String(value);
      if (Math.abs(number) >= 100) return number.toFixed(0);
      if (Math.abs(number) >= 10) return number.toFixed(1);
      if (Math.abs(number) >= 1) return number.toFixed(2);
      return number.toFixed(4);
    }

    function formatHitList(items) {
      if (!items || !items.length) return "none";
      return items.join(", ");
    }

    function mapToSummary(value) {
      const entries = Object.entries(value || {});
      if (!entries.length) return "none";
      return entries.map(([key, count]) => `${key}: ${count}`).join(" · ");
    }

    function renderQueryResultCard(title, result) {
      if (!result) {
        return `
          <div class="metric-tile">
            <h3>${escapeHtml(title)}</h3>
            <div class="muted">No result available.</div>
          </div>
        `;
      }
      return `
        <div class="metric-tile">
          <h3>${escapeHtml(title)}</h3>
          <div class="muted">${escapeHtml(result.index_name || "unknown-index")} · HTTP ${escapeHtml(result.status_code ?? "n/a")}</div>
          <div class="metric-value">${escapeHtml(result.results_count ?? 0)}</div>
          <div class="muted" style="margin-top: 6px;">${escapeHtml(formatMetric(result.latency_ms))} ms</div>
          <div class="muted" style="margin-top: 8px;">Top hits: ${escapeHtml(formatHitList(result.top_hits))}</div>
          ${result.error ? `<div class="muted" style="margin-top: 8px;">Error: ${escapeHtml(result.error)}</div>` : ""}
        </div>
      `;
    }

    function renderShadowInspector(comparison) {
      if (!comparison) return "";
      return `
        <div class="impact-tile">
          <h3>Shadow Comparison</h3>
          <div class="chips">
            <div class="chip">Outcome: ${escapeHtml(comparison.delta && comparison.delta.outcome || "unknown")}</div>
            <div class="chip">Result delta: ${escapeHtml(comparison.delta && comparison.delta.results_count || "n/a")}</div>
            <div class="chip">Latency delta: ${escapeHtml(formatMetric(comparison.delta && comparison.delta.latency_ms))} ms</div>
          </div>
        </div>
      `;
    }

    function renderRelatedSignalPanels(signals, events) {
      const signalMarkup = signals.length
        ? signals.map((item) => `
            <div class="ledger-row">
              <strong>${escapeHtml(item.signal_type || "unknown-signal")}</strong>
              <div class="muted" style="margin-top: 6px;">${escapeHtml(item.created_at || "unknown-time")} · ${escapeHtml(item.origin || "unknown")} · ${escapeHtml(item.severity || "info")}</div>
              <div style="margin-top: 8px;">Capability: ${escapeHtml(item.capability || "unknown")} · Query: ${escapeHtml(item.query || "n/a")}</div>
              <div class="muted" style="margin-top: 8px;">${escapeHtml(item.summary || "No summary attached.")}</div>
            </div>
          `).join("")
        : `<div class="empty">No related signals were found for the current inspector scope.</div>`;

      const eventMarkup = events.length
        ? events.map((item) => `
            <div class="ledger-row">
              <strong>${escapeHtml(item.source_type || "unknown-event")}</strong>
              <div class="muted" style="margin-top: 6px;">${escapeHtml(item.created_at || "unknown-time")} · ${escapeHtml(item.origin || "unknown")}</div>
              <div style="margin-top: 8px;">${escapeHtml(item.event_type || "unknown")} · ${escapeHtml(item.capability || "unknown")} · Query: ${escapeHtml(item.query || "n/a")}</div>
            </div>
          `).join("")
        : `<div class="empty">No related raw ops events were found for the current inspector scope.</div>`;

      return `
        <div class="impact-tile">
          <h3>Related Signals</h3>
          <div class="stack" style="margin-top: 12px;">${signalMarkup}</div>
        </div>
        <div class="impact-tile">
          <h3>Related Raw Events</h3>
          <div class="stack" style="margin-top: 12px;">${eventMarkup}</div>
        </div>
      `;
    }

    function sleep(ms) {
      return new Promise((resolve) => setTimeout(resolve, ms));
    }

    function applyOperatorQuery() {
      state.operatorQuery = operatorQueryInput.value.trim();
      shadowQueryInput.value = state.operatorQuery;
      syncUrlQuery();
      loadData();
    }

    function syncUrlQuery() {
      const url = new URL(window.location.href);
      if (state.operatorQuery) {
        url.searchParams.set("query", state.operatorQuery);
      } else {
        url.searchParams.delete("query");
      }
      window.history.replaceState({}, "", url);
    }

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function escapeAttr(value) {
      return escapeHtml(value);
    }

    loadData();
  </script>
</body>
</html>
"""
