# Integration Comparison — One-Page Summary

## TL;DR
**Factory DB `rjvn` schema (221 tables) IS the single source of truth.** System A (smt-factory-system) is the only production-ready codebase. Systems B, C, D, E are redundant schema copies or legacy ports — **kill all, port missing domains into A targeting rjvn.**

---

## System Status at a Glance

| System | Type | Tables | Status | Verdict |
|--------|------|--------|--------|---------|
| **A. smt-factory-system** | TS/Node monorepo | 82 (live) | M0-M10 done, 215 tests pass | **KEEP** — Primary app |
| **Factory DB `rjvn`** | PostgreSQL schema | 221 | Unified WMS+MES+OA+HR+Sales | **KEEP** — Canonical data |
| **Factory DB `public`** | PostgreSQL schema | 82 | Mirror of A's tables | **DROP** after retarget |
| **Factory DB `mesapp`** | PostgreSQL schema | 29 | Legacy MES | **MIGRATE→DROP** |
| **B. WMS-20261019** | NestJS+Drizzle | 178 (schema only) | Superset of D/E | **KILL** — Redundant |
| **C. OA** | Fastify+Next.js | ~76 (dump) | Separate PG instance (5433) | **MIGRATE→KILL** |
| **D. ruijing-mes** | Python/FastAPI+SQLite | 66 | 100% subset of B | **KILL** — Port drivers only |
| **E. rjvn-factory-erp** | Scaffold (NestJS) | 88 | Incomplete subset of B | **KILL** — No runtime value |

---

## Key Findings

### 🔴 Zero Overlap: System A ↔ System B
- **Different naming conventions entirely** — A uses `station_*`, `wms_*`, `mes_*`, `sn_*`, `factory_*`; B uses `md_*`, `cfg_*`, `prd_*`, `iqc_*`, `ord_*`, `work_order`
- **Same concepts, zero shared table names** — Work orders, material lots, IQC, stations, SN traceability, BOM, equipment all modeled differently

### 🟢 Factory `rjvn` Already Unified
- **221 tables** combining B's WMS/MES/IQC (73 direct matches) + A's traceability (`canonical_sn_trace_events`, `factory_sn_master`) + OA's HR/Flow (13 tables) + Sales/Purchase/Supplier
- **40 cross-domain views** (`v_mgmt_*`, `v_oa_*`) for reporting
- **6 roles exist**: `role_wms`, `role_oa`, `role_mes`, `role_smt`, `role_mgmt`, `role_report`

### 🔄 Duplication Count
- **~120+ exact table name duplicates** across B, E, factory.rjvn (triplicated WMS/IQC/MES core)
- **D is 100% clone of B's MES+MD subset** (66/66 tables match)
- **E is 100% clone of B** (88/88 tables match, missing 90)

---

## What A Lacks (Must Add from B/C)

| Domain | Tables | Source |
|--------|--------|--------|
| HR/Attendance/Payroll | 7-76 | Factory rjvn `hr_*`, OA dump |
| Sales/CRM | 7 | Factory rjvn `sales_*`, B `sales_*` |
| Purchase/Procurement | 14 | Factory rjvn `purchase_order`, `supplier_*`, B `supplier_*` (13) |
| Flow/Workflow | 6 | Factory rjvn `flow_*`, B `flow_*` |
| AGV/Fleet | 10 | B `agv_*`, E `agv_*` |
| Equipment PM/CM/Calibration | 7 | B `equipment_*`, `pm_*`, `calibration_*`, `condition_*`, `cm_*` |
| Spare Parts | 2 | B `spare_part`, `spare_part_bom` |
| Document Management | 4 | B `doc_*` |
| OEE/Analytics | 1+ | B `oee_log` |
| Finance/Accounting | Partial | B, Factory rjvn `supplier_debt`, payroll |

---

## Merge Plan (6 Weeks)

### Phase 1: Schema Alignment (Week 1-2)
- Add multilingual columns (`name_zh/name_en/name_vi`) to all rjvn master tables
- Create 90 missing domain tables in rjvn from B (agv, calibration, condition, cm, doc, equipment_lifecycle, flow_def/step, hr_attendance/contract/leave/salary, md_*, mes_bom_item/sys_param/sys_role, oee_log, pm, prd, proc, spare_part, supplier_portal/price/qual/risk, sys_api_key/audit_log/perm/role_perm/user_line)
- Migrate 29 `mesapp` tables → rjvn
- Drop `factory.public` schema

### Phase 2: Code Retarget (Week 3-4)
- Point A's DB connection to `factory` DB / `rjvn` schema
- Add repositories for new domains (HR, Sales, Purchase, Flow, AGV, Equipment PM, Finance)
- Port OA HR/Attendance/Payroll UI → A's `apps/web` Admin module
- Port device drivers from D's `设备对接工具/` → A's `integrations/`
- Run 215 tests against rjvn

### Phase 3: Cleanup (Week 5-6)
- Decommission `smt_factory` DB, OA standalone PG (5433)
- Archive B, D, E, C repos (read-only)
- Validate 6 roles + trilingual UI
- M11 Pilot gate

---

## Post-Merge Architecture

```
┌─────────────────────────────────────────────┐
│  System A: smt-factory-system (code)        │
│  apps/web, scanner, display, station-agent  │
│  services/api, worker, realtime, watchdog   │
└──────────────┬──────────────────────────────┘
               │ targets
               ▼
┌─────────────────────────────────────────────┐
│  Factory PostgreSQL (single instance)       │
│  ├── rjvn (280 tables) — CANONICAL          │
│  │   ├── WMS/Inventory/IQC/MRB              │
│  │   ├── MES/Production/Traceability/SN     │
│  │   ├── Station Execution (50+ tables)     │
│  │   ├── HR/Attendance/Payroll/Flow         │
│  │   ├── Sales/Purchase/Supplier            │
│  │   ├── AGV/Equipment/Spare/Doc/OEE        │
│  │   ├── Admin/Sys/Audit (6 roles)          │
│  │   └── v_mgmt_* / v_oa_* (40 views)       │
│  └── (public, mesapp DROPPED)               │
└─────────────────────────────────────────────┘
```

---

## Kill List (Delete These)

| Repo/DB | Action |
|---------|--------|
| `D:\rj\repos\extract\WMS-20261019` | Archive (read-only) |
| `D:\rj\repos\extract\OA` | Archive after HR/Payroll port |
| `C:\Users\tianj\test-ruijing` | Archive after driver port |
| `C:\Users\tianj\rjvn-factory-erp` | Delete (empty scaffold) |
| `smt_factory` database | Drop after retarget |
| `oa_system` database (port 5433) | Drop after migrate |
| `factory.public` schema | Drop |
| `factory.mesapp` schema | Drop after migrate |

---

*Generated from live DB queries + schema analysis. Full report: `integration-comparison-report.md`*