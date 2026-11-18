# AI tooling resource registry

## Purpose

This registry records external AI and agent resources that may support the Ruijing factory MES, station-agent, PDA, documentation, and design workflows. The registry is intentionally separate from production runtime dependencies: adding a resource here does **not** install it on a station or grant it access to MES data.

## Safety boundary

- Production station agents remain vendor-neutral and continue to use the approved station-agent standard.
- No resource may make NG, repair, retest, release, scrap, routing, or authorization decisions.
- No production credentials, SN data, images, test files, or MES events may be uploaded until security, licensing, data residency, and audit requirements are approved.
- Runtime integration requires a separate ADR, dependency review, test evidence, rollback plan, and explicit owner.

## Candidate resources

| Resource | Category | Intended use | Status | Safe next step |
|---|---|---|---|---|
| [HeySki](https://heyski.io/) | Voice coding / developer tool | Optional voice input for developers creating or debugging tools | Evaluate only | Trial on a developer workstation; never install on a production station or PDA by default |
| [HeyNoah](https://www.heynoah.io/) | Management productivity assistant | Meeting, email, SMS, calendar, and follow-up coordination for managers | Evaluate only | Validate privacy, account ownership, and export controls with management |
| [AppLlama](https://appllama.io/) | UI reference library | Reference mobile/PDA interaction patterns and visual layouts | Reference only | Use screenshots/ideas as design input; do not copy proprietary assets into production |
| [CopilotKit Channels SDK](https://github.com/CopilotKit/channels-sdk) | Agent messaging integration | Candidate channel for repair-complete and pickup notifications to approved team channels | Architecture candidate | Design an authenticated notification adapter with retries, idempotency, audit, and MES ownership before coding |
| [GenOffice](https://github.com/genspark-ai/genoffice) | Office/document generation | Draft reports, SOPs, work-order summaries, and review documents | Evaluate only | Use with synthetic or approved data; human-review every generated document |
| [FLUX.3](https://bfl.ai/models/flux-3) | Image generation | Training illustrations, UI mood boards, and non-authoritative visual assets | Evaluate only | Keep generated visuals clearly non-production and verify licensing before distribution |
| Pantograph Robot | Robotics / agent project | Possible future automation research | Unverified | Verify the canonical project, license, security posture, and relevance before adoption |
| AgentSky | Agent platform | Possible future agent orchestration research | Unverified | Verify the canonical project, license, data handling, and maintenance before adoption |

### Database and correctness research

| Resource | Category | Intended use | Status | Safe next step |
|---|---|---|---|---|
| [Turso](https://github.com/tursodatabase/turso) | Rust SQLite-compatible database | Evaluate for local station Outbox, audit-history prototypes, or embedded test fixtures | Research candidate | Benchmark durability, concurrent writes, backup/restore, and Windows support against SQLite; do not replace MES yet |
| [libSQL](https://github.com/tursodatabase/libsql) | SQLite fork / database engine | Evaluate for replicated or extended SQLite scenarios | Research candidate | Review protocol, licensing, operational maturity, and migration/rollback path before any pilot |
| [pgrust](https://github.com/mjmalis/pgrust) | AI-transpiled Rust PostgreSQL project | Study only for database implementation research | Experimental / unverified | Do not use for production data; inspect project health, test coverage, compatibility, and license first |
| [ScyllaDB](https://github.com/scylladb/scylladb) | Distributed NoSQL database | Possible high-volume telemetry or event-ingestion research | Architecture candidate | Only consider if measured event volume requires it; keep MES transactional truth in the approved relational system |
| [Quint](https://github.com/quint-co/quint) | Executable formal-specification language | Model and verify NG routing, repair-loop, Outbox, and authorization invariants | Evaluation candidate | Start with a small non-production model; use it to test rules, not to bypass MES authorization |

## Installation policy

At this stage, **none of these resources is installed as a production station dependency**. Developer-only trials may be installed in an isolated environment after owner approval. A future integration must record:

1. owner and business purpose;
2. exact version, license, and source URL;
3. data classification and network destinations;
4. authentication and least-privilege scope;
5. offline behavior and MES-down behavior;
6. test, monitoring, rollback, and removal procedure.

## Recommended order

1. Use AppLlama and GenOffice as reference/documentation tools first.
2. Prototype the CopilotKit channel behind a local notification interface using synthetic events.
3. Evaluate HeySki only on developer machines.
4. Evaluate HeyNoah, FLUX.3, Pantograph Robot, and AgentSky only after privacy, licensing, and ownership review.
5. Use Quint for correctness modeling before considering any database migration; compare Turso/libSQL/ScyllaDB only with production-like benchmarks and a rollback plan.

## Project recommendation

### Adopt now in development

- **Quint:** model NG routing, repair-loop transitions, retest limits, MES-down rules, and authorization invariants.
- **AppLlama:** use only as UI/interaction research for PDA and MES screens.
- **GenOffice:** draft SOPs and review reports from approved or synthetic data.

### Prototype behind a feature flag

- **Turso/libSQL:** test append-only Outbox, local repair history, and MES-recovery replay outside production.
- **CopilotKit Channels SDK:** test repair-complete and pickup notifications through an authenticated adapter with idempotency and audit logging.

### Defer

- **ScyllaDB:** only reconsider if measured telemetry volume exceeds the current relational/MES design.
- **pgrust:** experimental; do not use for production.
- **HeySki, HeyNoah, FLUX.3, Pantograph Robot, AgentSky:** keep to isolated evaluation until privacy, licensing, ownership, and operational controls are approved.

### Acceptance gate

No candidate moves into a station agent or MES production path until it has an owner, pinned version, license review, security review, synthetic-data test, offline/MES-down behavior, monitoring, rollback, and removal procedure.

## Decision record

The resources were added as a governed registry rather than copied into station agents because the factory requires deterministic, auditable MES-owned routing and repair behavior. This keeps experimentation reversible and prevents an external AI service from becoming an uncontrolled production dependency.
