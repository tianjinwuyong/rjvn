# Virtual Factory Agent Team — Design Blueprint

**Scope**: How to build an agent team ("virtual employees") that operates the Ruijing Vietnam
SMT factory on top of the existing `smt-factory-system` MES.
**Status**: Proposal. Grounded in the current workspace inventory (docs/, smt-factory-system/,
瑞晶越南工位-正式命名/, ruijing_crew/, agentic-os/, agent-memory-stack/).
**Update**: 2026-11 — orchestration layer now follows the Super-agent pattern from DeepSeek's
open-source `dsh-superagent` prototype (MIT). See §4.

---

## 1. TL;DR — the recommended approach

> **MES-anchored, event-driven, supervisor-orchestrated virtual employees.**
> Keep MES as the single source of truth (you already enforce this in the Andon governance).
> Agents are a **cognitive + action layer** on top: they read live MES state, reason, and act
> **only through a permission-scoped tool layer** that returns audited MES commands.
> Generalize the working IQC "virtual employee" pattern to every role.
> Orchestrate with the **Router → Worker** pattern: a supervisor session evaluates triggers and
> dispatches **Tickets** (authorized, immutable **Mandates**) to isolated worker sessions.

Three rules that decide everything else:

1. **Deterministic core, generative edges.** SLAs, timers, routing, NG state machines, permission
   checks and the Eval *gate* stay deterministic (MES/PostgreSQL/code). LLMs do triage, diagnosis,
   planning, summarization, and natural-language communication — never the critical loop itself.
2. **Every agent action is a command with feedback.** Reuse the existing `commandId` →
   `RECEIVED / ACCEPTED / EXECUTED / REJECTED / BLOCKED` protocol from `mes-andon-escalation.md`,
   and the Super-agent's immutable **Trigger + Mandate + Policy version**. Agents can be audited,
   replayed, and revoked. This is what makes an agent team *safe to run a factory*.
3. **Autonomy is earned by KPI, in stages.** Copilot (assist) → supervised autonomy (execute
   low-risk, human approves high-risk) → closed-loop (routine loops only). This maps 1:1 onto the
   Super-agent accept modes `off` / `observe` / `auto` — start in `observe`. Advance a role only
   when its KPIs improve for N consecutive weeks.

---

## 2. What you already have (inventory)

| Asset | Where | Role in the agent team |
|---|---|---|
| MES core (WMS/PMC/MES/HR/Finance/Equipment/Quality/AI/Sales/Service) | `smt-factory-system/` | Source of truth; the tool layer's backend |
| Andon escalation L0–L4, immutable events, command feedback, outbox | `docs/mes-andon-escalation.md` | The agent team's trigger and escalation spine |
| Station specs + named stations (AOI, ICT, FCT, Depanel, Aging, HiVolt, Supersonic, Assembly, Packing, OuterBox, Pallet, QRBinding, PDA) | `*.spec`, `瑞晶越南工位-正式命名/` | Station-copilot scope definitions |
| Station agents / heartbeats / TTS voice / scanner terminals / display board | station-agent app, heartbeat agents, `tts-*.html` | Station-copilot runtime + trilingual floor comms |
| IQC virtual employee (Ollama qwen + guidance + screenshots) | `Modelfile.qwen38-iqc`, iqc-virtual-employee pages | The **pattern to clone** for every role |
| Repair queue / NG management / repair-case lifecycle | `docs/manual-line-repair-*.md`, MES NG pages | Repair-agent domain |
| mem0 + Qdrant memory server; cognee / memory-mcp / paperclip knowledge stack | `smt-factory-system/services/memory/`, `agent-memory-stack/` | Long-term memory + SOP RAG |
| CrewAI dev crew | `ruijing_crew/` | Keep for **software development** crews only |
| Agentic OS dashboard | `agentic-os/` | Dev/ops control plane — **not** the factory runtime |
| Plant-manager PDA cockpit, seniority + `approval.final.release` gating | `tasks/plan.md` | Human approval surface for agent actions |
| Super-agent reference prototype | [deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype) | Reference architecture for the orchestration layer (§4) |

---

## 3. Target architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  HUMAN SURFACE: plant-manager PDA · display board · TTS (zh/en/vi)│
│  approvals (approval.final.release) · escalation L3/L4 owners     │
├──────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION — Super-agent Engine (Router → Worker):            │
│  Intake → Eval (deterministic gate + LLM assessment) → Ticket     │
│  → Assignment → Report · Effects queue · Policy versions          │
│  supervisor = one long-running Router session per shift            │
├──────────────────────────────────────────────────────────────────┤
│  ROLE AGENTS (virtual employees, one scope each = Executors/workers)│
│  line-leader · PMC/planner · warehouse · IQC/quality · repair/NG  │
│  maintenance/equipment · HR/attendance · safety · station copilots│
├──────────────────────────────────────────────────────────────────┤
│  TOOL LAYER: MCP servers wrapping MES APIs                        │
│  permission-scoped per agent · commandId feedback · idempotent    │
│  · full audit (actor = agent_id + policy version)                 │
├──────────────────────────────────────────────────────────────────┤
│  EVENT BUS: andon events · NG · heartbeats · WMS · timers         │
│  (reuse realtime service + worker + outbox, offline-safe)         │
├──────────────────────────────────────────────────────────────────┤
│  MES + PostgreSQL (source of truth, immutable history)            │
└──────────────────────────────────────────────────────────────────┘
```

### Why not the alternatives

- **Flat swarm of autonomous agents** — undeterministic, un-auditable, unsafe for production.
  Factory operations are a permission + escalation hierarchy; model it that way.
- **One mega-agent with all tools** — context bloat, permission blur, single point of failure.
- **Agentic OS / CrewAI as the runtime** — they orchestrate *development work*; they do not
  hold MES command feedback, offline outbox, SLA timers, or policy versions. Dev side only.
- **LLM-only automation** — LLMs drift and hallucinate; never let them own timers, routing,
  disposition, or final release. (Your andon doc already says exactly this — keep it.)

---

## 4. Super-agent runtime — DeepSeek `dsh-superagent` mapping

DeepSeek open-sourced `dsh-superagent` (MIT) on 2026-11-01/02. It is a research prototype —
explicitly **not production-ready**, runs with full OS-user access, and is packaged as a DSH
profile (requires Node 22.19+, tmux, git, Python 3.8+, GitHub CLI). We adopt its **model**, not
its GitHub-coding deployment as-is.

### 4.1 Concept mapping

| Super-agent concept | Factory meaning | Existing counterpart in your system |
|---|---|---|
| **Source** | A stream of events: andon triggers, NG events, station heartbeats, WMS receiving events, PDA activity, (optional) Feishu/chat requests | `/api/pda/events` SSE, `andon_events`, outbox, realtime service |
| **Trigger** | One immutable event (one andon trigger, one repair request, one WO request) | `andonEventId`, NG event, `commandId` |
| **Thread** | The case chain a trigger belongs to: one repair case, one batch, one shift | `repair-case-lifecycle`, `workOrderId`, batch QR, shift |
| **Correlation** | Related threads that add context but never route | links between repair case / NG / WO |
| **Channel** | Write side: MES command, PDA push, TTS, Feishu, panel | PDA push, TTS, Kanban, `andon_notifications` |
| **Policy / Policy version** | Who may originate what, where: roles, allowlists, L0–L4 policy, admission rules | MES permissions, `approval.final.release`, andon policy version |
| **Eval (gate + assessment)** | Gate = deterministic authorization (who/strength); assessment = LLM triage (accept / stop / ignore / unavailable) | MES permission check + andon SLA policy + LLM triage |
| **Mandate** | What an accept grants: policy version, scope, strength, matched rules — immutable | command feedback + approval records |
| **Ticket** | The authorized unit of work: an andon response, a repair ticket, a WO draft, an IQC disposition draft | repair work order, andon event, WO |
| **Assignment** | The binding to one executor instance (one agent session, one directory) | station agent / virtual employee session |
| **Subscription** | Later messages on the same case reach the original executor without re-asking | repair-case follow-up events, PDA/chat follow-ups |
| **Report** | progress / waiting / ready / blocked / failed / dropped | andon state machine + command feedback |
| **Attention** | A structured question waiting for a person | approval queue / team-leader PDA claim |
| **Executor** | One isolated session + directory per Ticket (worker preset) | role agent (IQC virtual employee pattern) |
| **Panel** | Shows only what needs a person; healthy work takes no space | WMS Kanban, PDA cockpit |

### 4.2 Mechanisms to adopt (and their factory payoff)

1. **Two-path authorization.** Explicit requests (allowlist + addressed) vs inferred candidates
   (admission table + rules); a message is *context, never authority* — it cannot expand
   permissions. → precisely your `approval.final.release` model, generalized.
2. **Immutable Trigger + Mandate + Policy version.** Every accepted action records the policy
   version and matched rules; a policy change notifies affected open tickets and blocks stale
   resumes. → extends your andon immutability to the agent's own decisions.
3. **One thread = one Eval at a time, batching queued triggers.** → no duplicate work orders per
   andon burst; a burst of station heartbeats becomes one Eval.
4. **Subscription fan-out.** A person's follow-up on a case reaches the original executor without
   a new mention; the executor decides it inside its Ticket's scope or hands it back. → repair
   case continuations, shift-handover notes, management comments.
5. **Structured Report + Attention.** Workers report progress/waiting/ready/blocked/failed/dropped
   and ask **one concrete question at a time**. → fits your PDA approval queue; no long reports.
6. **Durable Effects queue with retries.** External side effects are enqueued in the same
   transaction and executed after commit, idempotent, retried with backoff. → same principle as
   your offline `andon_outbox`.
7. **Health entries per part.** Each component reports its own health; panel shows only what needs
   a person. → one more signal for the WMS sync-health page.

### 4.3 What must change for the factory

- **Source → MES events.** Replace GitHub/Feishu Sources with MES event adapters (station
  heartbeats, andon, NG, WMS, PDA). Feishu can stay as an optional management-chat Source.
- **Executor → MCP tool layer.** The worker no longer edits code; it calls permission-scoped MES
  tools (`andon.ack`, `wo.draft`, `repair.assign`…) whose results carry `commandId` feedback.
- **Panel → embed in WMS/PDA**, not a standalone client.
- **Runtime constraints.** The prototype needs tmux (Unix-only) and a DSH profile; on this
  Windows machine tmux is absent and WSL is blocked. Two paths:
  - **A (recommended for production):** re-implement the minimal Engine on the existing Node
    worker — tables `trigger / thread / decision / ticket / assignment / effect` in PostgreSQL,
    Sources as event adapters, Executors as your role agents. MIT code can be ported, but the
    domain model is ~5 concepts; porting is straightforward.
  - **B (research baseline):** run the official prototype on Linux/WSL2 with a custom MES
    Source plugin, to compare behavior and validate policies before the port.
- **Security posture.** The prototype runs with full OS-user access by design. For the factory:
  dedicated service account, `agent_*` MES accounts, read-only by default, observe first,
  tool-layer validation, no direct DB writes.

### 4.4 Adoption principle from its philosophy doc

> *Take as little human attention as possible, and give as much value as possible. Act only when
> asked or when a written rule allows it. Speak only when a person must act or can use a result.*

This is the right interaction contract for a factory floor, where attention is the scarcest
resource. Bake it into every role prompt: report to the PDA only on escalation L≥2 or when a
decision is needed; stay silent while healthy.

---

## 5. Agent roster (first cut)

Each agent = scope, triggers, tools, permissions, KPIs. One role per agent; no shared tool bags.
The **Shift Supervisor** is the Router (main session); every role agent is an Executor (worker).

| Agent | Triggers | Tools (MES API scope) | Autonomy ceiling | KPIs |
|---|---|---|---|---|
| **Shift Supervisor** (router, 1 per shift) | all escalated events, shift start/end, daily plan | read-all; assign owners; escalate; request approvals; route Tickets | cannot release/close; final release stays human (or senior-only policy) | andon L1→L2 time, OEE, OTIF |
| **Line Leader** (per line) | L1 andon, pickup SLA, handover mismatch | claim/assign within line, PDA pushes, TTS | execute low-risk line actions | andon response time, queue age |
| **PMC / Planner** | PO open, WO creation request, capacity/material check | create WO drafts, capacity read, material readiness check | WO **release** requires approval | on-time WO start, line changeover loss |
| **Warehouse / WMS** | receiving event, pick shortage, IQC pending | receiving label ops, stock read, shortage alert, kit prep | receipt posting; disposition of holds = QC | inventory accuracy, shortage count |
| **IQC / Quality** (clone the existing virtual employee) | IQC pending, supplier lot in, NG disposition support | inspection guidance, evidence capture, disposition **draft** | disposition is quality-authority owned | IQC cycle time, escape rate |
| **Repair / NG** | NG bucket, repair SLA, retest queue | repair queue triage, assignment, evidence notes, escalation | cannot close cases / alter route | repair cycle time, SLA breach rate |
| **Maintenance / Equipment** | heartbeat loss, device fault, OEE drop | diagnostics read, work-order draft, spare-part request | maintenance release = human | MTTR, MTTF, downtime % |
| **HR / Attendance** | shift start, missing operator, training due | attendance read, coverage alert, training reminders | no payroll mutations | coverage rate, training compliance |
| **Safety** | safety events, near-miss reports | alert, evidence lock, L4 escalation | safety events bypass grace (already in MES) | report-to-escalation time |
| **Station Copilot** (per station) | station events, NG at station, operator help | station read, guidance, voice/TTS, ack | cannot skip/rewind route steps | first-pass yield assist, help resolution |

---

## 6. Operating model — three autonomy stages (≡ accept modes)

| Stage | Super-agent mode | What agents do | Human does | Gate to advance |
|---|---|---|---|---|
| **1. Copilot** (now → next 2–4 weeks) | `observe` — record what would have been done, do nothing | watch + triage + recommend; every action requires human ack; drafts of messages/plans/diagnostics | executes or approves | zero unauthorized actions in 2 weeks; andon response improves |
| **2. Supervised autonomy** | `auto` for low-risk rules | execute low-risk actions in scope (notifications, assignments, data entry, diagnostics, drafts); hold at approval gates | approves release/disposition/maintenance; reviews daily agent log | KPI improvement 4 consecutive weeks; <0.1% REJECTED commands |
| **3. Closed-loop** | `auto` for routine rules | routine loops only (andon L0/L1, IQC guidance, repair queue triage, stock alerts) fully automated | exceptions + L3/L4 only | 8 weeks stable; audit clean; incident drill passed |

Per-role, not global: a station copilot may reach stage 2 while finance agents stay stage 1.
Policy changes are versioned; a weaker policy does not silently stop open Tickets but notifies
affected ones and requires revalidation before resume (mirrors the prototype's Mandate rules).

---

## 7. Memory design

- **SOP/standards corpus (RAG)**: station specs, repair-case lifecycles, `*GRILLING.md` audits,
  work instructions → indexed in the existing mem0/Qdrant or cognee stack. This is the "training
  manual" every agent reads before acting.
- **Episodic memory per role**: what this agent did, what worked, per agent_id (mem0 already
  keyed by agent_id).
- **Shared shift memory**: shift handover notes (state, open andons, risks) written by the
  outgoing Shift Supervisor, read by the incoming one — the factory's "daily journal".
- **Decision memory (new)**: the Engine's `trigger / decision / ticket / assignment` tables are
  the agent team's own audit memory. Replays, KPI review and incident drills read from here.
- **Case memory**: repair cases + outcomes feed back into the RAG corpus (repair-case-lifecycle
  already exists) so the team gets smarter each week.

---

## 8. Phased roadmap

| Phase | Work | Reuses |
|---|---|---|
| **P0 — Digital backbone (mostly done)** | MES modules, andon, stations, PDA, memory server running | everything in §2 |
| **P1 — Engine + Copilot team (now)** | Implement the Super-agent Engine (`trigger/thread/decision/ticket/assignment/effect` tables) on the existing Node worker; MES event Source adapters; MCP tool layer with commandId feedback; clone IQC pattern into Line Leader, Repair, Warehouse, Maintenance; Router session with daily loop (plan → monitor → escalate → handover) in `observe` mode | realtime service, worker, outbox, MES |
| **P2 — Supervised autonomy** | approval-gate tooling on PDA (seniority already built); agent action log UI ("who did what, with which command, under which policy version"); `auto` for safe rules | `tasks/plan.md` cockpit, `approval.final.release` |
| **P3 — Cross-function orchestration** | Router coordinates PMC/warehouse/quality/maintenance on exceptions; daily planning loop; KPI dashboard per agent | reports module, andon metrics |
| **P4 — Closed-loop + simulation** | closed loops for routine ops; validate risky actions in the 3D line preview / simulator before executing | 3d line preview, simulator |

**Suggested immediate next steps** (each is a bounded task):

1. **Trigger schema + Source adapters**: define `trigger` (id = andonEventId/commandId, source,
   thread, actor, at) and build MES → Trigger adapters (andon SSE, station heartbeat, WMS events);
   dedupe by immutable event id (idempotent receive).
2. **Policy v1**: allowlists per role/line, admission rules (who may ask the agent to do what,
   from which channel), accept mode default `observe`, policy version hashing.
3. **Engine skeleton** on the existing worker: `trigger → thread → eval → ticket → assignment →
   report` state machine + durable `effect` queue (reuse outbox pattern).
4. **MCP tool schema** for 3–5 read tools + 3 write tools (e.g., `andon.ack`, `wo.draft`,
   `repair.assign`) with the commandId feedback contract.
5. **Repair/NG agent** as the second virtual employee (after IQC) — highest SLA pain, fully
   documented in `docs/manual-line-repair-*`, piloted in `observe` mode.
6. **Agent audit log** = Engine tables + actor/policy version; before granting any autonomous
   execution.

---

## 9. Pitfalls to avoid

- ❌ Agents writing MES directly — always through the tool layer (your andon doc already forbids this).
- ❌ LLM-owned timers/SLAs or the authorization gate — MES owns timers; the gate is deterministic.
- ❌ Global autonomy — per-role, per-stage, revoked on any REJECTED/BLOCKED spike.
- ❌ English-only agent comms — floor comms must be vi-VN/zh-CN/en-US (TTS + PDA already trilingual).
- ❌ Unlogged actions — no agent action without actor, policy version, and command result.
- ❌ One agent per station doing everything — station copilots stay narrow; cross-station work goes up to line leader / supervisor.
- ❌ Buying a "factory agent platform" — you already have 80% of the backbone; a platform would fight your MES instead of wrapping it.
- ❌ Running the raw prototype in production — it is research code with full OS-user access; use it as reference, or port the model with a dedicated account.

---

## 10. Open decisions (need factory management input)

1. **Which roles get autonomy first?** Recommendation: Repair/NG + Line Leader (clear SLA pain,
   low safety risk). IQC disposition and WO release stay human-approved longest.
2. **Runtime path**: port the minimal Engine into the existing Node worker (recommended, no new
   runtime), or first validate on a Linux/WSL2 host running the official prototype.
3. **Model routing**: local Ollama (qwen) for latency/cost on station copilots; stronger cloud
   models (deepseek-class) for the router/planning. Define cost per action.
4. **Language policy**: agents converse in vi-VN on the floor, zh-CN for management reports,
   en-US in the API layer.
5. **Account model**: does a "virtual employee" get a real MES user account (with role-based
   permissions, e.g., `VN_AI_*`), or a separate service-account scope? Recommendation: service
   accounts with `agent_` prefix, auditable separately from humans.

---

## 11. References

- [deepseek-ai/dsh-superagent-prototype](https://github.com/deepseek-ai/dsh-superagent-prototype) — MIT, research prototype; docs numbered 000–008.
- [000 Philosophy](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/000-philosophy.md) — attention-minimal interaction contract.
- [001 Domain model](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/001-domain.md) — Source/Trigger/Thread/Eval/Mandate/Ticket/Subscription.
- [002 Authorization](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/002-authorization.md) — gate, admission table, accept modes, revalidation.
- [007 Architecture](https://github.com/deepseek-ai/dsh-superagent-prototype/blob/main/docs/007-architecture.md) — Engine parts, Store, Effects, Sources, Sessions, panel.
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness) — the host runtime (developer preview).
