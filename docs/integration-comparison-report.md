# Integration Comparison Report: 5 Factory Systems

**Date:** 2026-11-12  
**Scope:** Comparative analysis of 5 systems for Vietnam SMT factory  
**Output:** Definitive merge/kill/port recommendations

---

## 1. System Profiles — What Each System IS

| System | Path | Type | Tables (schema) | Tables (live DB) | Scope |
|--------|------|------|-----------------|------------------|-------|
| **A. smt-factory-system-worker** | `C:\Users\tianj\Desktop\越南工厂瑞晶\smt-factory-system-worker` | TypeScript/Node.js monorepo (React web, NestJS-like services, pg migrations) | 82 (public schema) | 82 (smt_factory DB) | **Primary target** — Unified SMT factory platform: ERP/PMC/WMS/MES/Quality/Traceability/Reports/Finance/Admin. 238 migrations, M0-M10 done, 215 tests pass. Mission: "one integrated management system... not a collection of separate ERP, WMS, MES, Quality tools." |
| **B. WMS-20261019** | `D:\rj\repos\extract\WMS-20261019` | NestJS + React + Drizzle ORM | 178 | N/A (schema.ts only) | **WMS+MES+OA+AGV+Equipment+HR+Flow** — Originally 129 tables, 5 subagents appended MES+OA+Provider+AGV+Equipment. Has `server/database/schema.ts` with full Drizzle definitions. DB name defaults to 'wms' (DSN split-brain). |
| **C. OA** | `D:\rj\repos\extract\OA` | Fastify + Next.js | ~76 (from dump) | N/A (oa_system.dump) | **OA/HR/Attendance/Payroll** — Separate PG instance (port 5433). Dump shows 76 tables: org, attendance, leave, payroll, salary, onboarding, permissions. |
| **D. ruijing-mes** | `C:\Users\tianj\test-ruijing` | Python/FastAPI + SQLite | 66 | N/A (schema.sql) | **Legacy MES + WMS integration** — SQLite single-file. 11 domains: sys, md, bom, cfg, itf, ord, pln, prd, proc. Has `api/itf_wms.py` = WMS integration layer. Device drivers in `设备对接工具/`. |
| **E. rjvn-factory-erp** | `C:\Users\tianj\rjvn-factory-erp` | Fresh monorepo scaffold (NestJS + Drizzle) | 88 | N/A (packages/db/src/schema.ts) | **Scaffold copy of B** — 88 tables, strict subset of B. Copies B's schema but drops: agv (10), calibration (2), cfg (11), cm, condition, doc (4), equipment (3), flow (4), hr (4), md (11), mes (3), oee, pm, prd (20), proc (3), sales (3), spare (2), supplier (13), sys (7), warehouse (2). Keeps: inventory, iqc, material, mrb, operation, over, picking, production, purchase, receipt, rework, role, stock, work_order. |

---

## 2. Table/Schema Overlap Matrix

### 2.1 Core Overlap: System B ↔ System D (ruijing-mes)
**D is a 100% subset of B** — all 66 tables in D exist in B with identical names.

| Domain | Tables in Both (66) |
|--------|---------------------|
| **bom** | `bom_header`, `bom_item` |
| **cfg** | `cfg_aoi_comp_map`, `cfg_aoi_defect`, `cfg_bind_rule`, `cfg_bind_station`, `cfg_code_dict`, `cfg_pack_rule`, `cfg_pcb_code`, `cfg_pokayoke`, `cfg_print_tpl`, `cfg_sn_rule`, `cfg_threshold` |
| **itf** | `itf_api_config`, `itf_api_log` |
| **md** | `md_calendar`, `md_customer`, `md_defect`, `md_equipment`, `md_line`, `md_material`, `md_product`, `md_rootcause`, `md_shift`, `md_station`, `md_track` |
| **ord** | `ord_issue`, `ord_issue_item`, `ord_mo`, `ord_mo_seq`, `ord_po`, `ord_replenish` |
| **pln** | `pln_capacity`, `pln_schedule` |
| **prd** | `prd_aoi_board`, `prd_aoi_comp`, `prd_aoi_result`, `prd_box`, `prd_decode`, `prd_defect_rec`, `prd_machine_data`, `prd_mo_route`, `prd_pallet`, `prd_pass`, `prd_pass_check`, `prd_pass_release`, `prd_print_job`, `prd_repair`, `prd_route_change`, `prd_scrap`, `prd_skip_log`, `prd_sn`, `prd_sn_rel`, `prd_test` |
| **proc** | `proc_route`, `proc_station_rule`, `proc_step` |
| **sys** | `sys_api_key`, `sys_audit_log`, `sys_param`, `sys_perm`, `sys_role`, `sys_role_perm`, `sys_user`, `sys_user_line`, `sys_user_role` |

**→ D adds ZERO tables not in B. D is a legacy SQLite port of B's MES+MD+cfg subset.**

### 2.2 System B ↔ System E (rjvn-factory-erp)
**E is a 100% subset of B** — all 88 tables in E exist in B.

| Domain | Tables in E (88) | Tables in B but NOT in E (90) |
|--------|------------------|-------------------------------|
| **agv** | 10/10 | — |
| **bom** | 2/3 (`bom`, `bom_item`) | `bom_header` |
| **defective** | 1/1 | — |
| **equipment** | 1/4 (`equipment_asset`) | `equipment_lifecycle_event`, `equipment_meter`, `equipment_type` |
| **flow** | 1/5 (`flow_instance`) | `flow_approval`, `flow_definition`, `flow_instance_step`, `flow_step` |
| **hr** | 4/8 | `hr_attendance`, `hr_contract`, `hr_leave`, `hr_salary` |
| **inventory** | 2/2 | — |
| **iqc** | 13/13 | — |
| **material** | 5/5 | — |
| **mes** | 4/7 | `mes_bom_item`, `mes_sys_param`, `mes_sys_role` |
| **mrb** | 5/5 | — |
| **operation** | 1/1 | — |
| **over** | 2/2 | — |
| **picking** | 3/3 | — |
| **production** | 3/3 | — |
| **purchase** | 1/1 | — |
| **receipt** | 1/1 | — |
| **rework** | 1/1 | — |
| **role** | 1/1 | — |
| **sales** | 3/3 | — |
| **stock** | 4/4 | — |
| **supplier** | 13/13 | — |
| **sys** | 4/11 | `sys_api_key`, `sys_audit_log`, `sys_perm`, `sys_role_perm`, `sys_user`, `sys_user_line`, `sys_user_role` |
| **warehouse** | 2/2 | — |
| **work** | 1/1 | — |
| **Missing domains in E** | — | `calibration` (2), `cfg` (11), `cm` (1), `condition` (1), `doc` (4), `md` (11), `oee` (1), `pln` (2), `pm` (2), `prd` (20), `proc` (3), `spare` (2) |

**→ E is an incomplete scaffold. B has 90 tables E lacks, including ALL of: prd (MES production), cfg (configuration), md (master data), proc (process), pln (planning), pm (preventive maintenance), calibration, doc, spare parts, AGV (kept), flow (partial), hr (partial), sys (partial).**

### 2.3 System A (smt_factory) vs Factory DB (public schema)
**IDENTICAL** — 82 tables, exact match. System A's DB *is* the `public` schema in the factory PG instance.

| Overlap | Count | Tables |
|---------|-------|--------|
| A ∩ factory.public | 82 | All 82 tables match exactly |
| A only | 0 | — |
| factory.public only | 0 | — |

**→ System A is deployed and running. The smt_factory DB = factory.public schema.**

### 2.4 System A vs System B
**ZERO TABLE OVERLAP** — Different naming conventions entirely.

| System A (smt_factory) — 82 tables | System B (WMS-20261019) — 178 tables |
|------------------------------------|--------------------------------------|
| Prefixes: `auto_`, `box_`, `canonical_`, `factory_`, `material_`, `mes_`, `ng_`, `pda_`, `smt_`, `sn_`, `station_`, `supplier_`, `wms_` | Prefixes: `agv_`, `bom_`, `calibration_`, `cfg_`, `cm_`, `condition_`, `defective_`, `doc_`, `equipment_`, `flow_`, `hr_`, `inventory_`, `iqc_`, `itf_`, `material_`, `md_`, `mes_`, `mrb_`, `oee_`, `operation_`, `ord_`, `over_`, `picking_`, `pln_`, `pm_`, `prd_`, `proc_`, `production_`, `purchase_`, `receipt_`, `rework_`, `role_`, `sales_`, `spare_`, `stock_`, `supplier_`, `sys_`, `warehouse_`, `work_` |

**Shared concepts, different table names:**
| Concept | System A | System B |
|---------|----------|----------|
| Work Order | `station_active_workorders`, `station_sn_route_progress` | `work_order`, `cm_workorder`, `ord_mo`, `mes_work_order_material` |
| Material Lot | `wms_material_roll_labels`, `mes_material_roll_import_rows` | `inventory`, `material`, `material_requirement`, `iqc_lot` |
| IQC | `wms_receiving_label_ai_scans` | `iqc_inspection_draft`, `iqc_inspection_record`, `iqc_lot`, `iqc_template` |
| Station/Line | `station_*` (50+ tables) | `md_station`, `md_line`, `md_track`, `cfg_bind_station` |
| SN Traceability | `canonical_sn_trace_events`, `sn_journey_events`, `factory_sn_master` | `prd_sn`, `prd_sn_rel`, `prd_box`, `prd_pallet` |
| BOM | (in MES tables) | `bom`, `bom_header`, `bom_item`, `mes_bom_item` |
| Equipment | `mes_smt_machine_channel_mapping` | `equipment_asset`, `equipment_type`, `equipment_lifecycle_event`, `md_equipment` |
| Users/Roles | `pda_role_work_sessions` | `sys_user`, `sys_role`, `sys_user_role`, `sys_perm`, `sys_role_perm`, `sys_user_line` |

### 2.5 Factory DB (rjvn schema) — The Unified Layer
**221 tables** in `rjvn` schema — this is the **consolidated canonical layer** that already merges WMS+MES+OA+HR+Sales+Supplier+Flow+Equipment.

| Domain | Tables | Source |
|--------|--------|--------|
| **WMS/Inventory** | `inventory`, `inventory_transaction`, `material`, `material_expiry_extension`, `material_requirement`, `material_requirement_item`, `material_substitution`, `warehouse`, `warehouse_location`, `receipt_order`, `picking_order`, `picking_order_item`, `picking_reel`, `over_picking_order`, `over_picking_item`, `stock_take_order`, `stock_take_item`, `stock_take_log`, `stock_transfer`, `production_return`, `production_return_iqc`, `production_return_label`, `wms_material_label_master`, `wms_material_msd_bindings`, `wms_material_roll_labels`, `wms_receiving_label_ai_scans`, `wms_receiving_pallet_box_removals`, `supplier_pre_receipts`, `supplier_pre_receipt_exceptions` | B + extensions |
| **MES/Production** | `mes_work_order_material`, `mes_issue_writeback`, `mes_sync_log`, `mes_sync_state`, `mes_manager_instructions`, `mes_material_binding_details`, `mes_material_roll_import_batches`, `mes_material_roll_import_rows`, `mes_material_roll_label_events`, `mes_ng_pickup_alarm_resolutions`, `mes_ng_pickup_announcements`, `mes_smt_loading_completions`, `mes_smt_loading_pda_requests`, `mes_smt_loading_scan_verifications`, `mes_smt_machine_channel_mapping`, `work_order`, `smt_loading_daily_plans` | B + A concepts |
| **Quality/IQC/MRB** | `iqc_*` (13), `mrb_*` (5), `quality_inspection`, `quality_inspection_item`, `rework_order`, `defective_move_task`, `ng_revival_audit` | B |
| **Traceability/SN** | `canonical_sn_trace_events`, `factory_sn_master`, `sn_journey_events`, `station_sn_registry`, `station_sn_arrivals`, `station_sn_route_progress`, `station_sn_identity_alias`, `station_qr_workorder_bindings`, `station_qr_workorder_trace`, `auto_line_sn_history`, `box_journey_records`, `station_packaging_boxes`, `station_packaging_box_items`, `station_packaging_box_audit`, `station_pallets`, `station_pallet_cartons`, `station_pallet_audit`, `station_pass_return_requests`, `station_pass_shortages` | A + B merged |
| **Station/Line Execution** | `station_*` (40+ tables: `station_active_workorders`, `station_activity_logs`, `station_aging_*`, `station_arrival_exceptions`, `station_bucket_snapshots`, `station_confirmed_motherboard_layouts`, `station_data_conflicts`, `station_fct_motherboard_staging`, `station_handover_*`, `station_history_archives`, `station_interception_events`, `station_inventory_checks`, `station_maintenance_cases`, `station_mes_integrity_alerts`, `station_ng_dispatch_alarm`, `station_ng_release_*`, `station_product_residence`, `station_production_events`, `station_repair_material_usage`, `station_repair_work_orders`, `station_retest_*`, `station_route_requests`, `station_scrap_*`, `station_production_events`) | A (rich) + B (md_station) |
| **HR/Flow/OA** | `hr_*` (7), `flow_*` (6), `oa_callback_log`, `oa_event_outbox` | C (OA) + B (flow) |
| **Sales/Purchase/Supplier** | `sales_*` (7), `purchase_order`, `supplier`, `supplier_material`, `supplier_return_*`, `supplier_debt`, `supplier_debt_settlement` | B |
| **Equipment** | `equipment_asset`, `mes_smt_machine_channel_mapping` | B + A |
| **Admin/Sys** | `sys_account`, `sys_notice`, `sys_param`, `sys_permission`, `sys_role`, `sys_role_permission`, `sys_user`, `sys_user_role`, `role_user`, `audit_log`, `pub_dict_material_category`, `pub_dict_unit`, `pub_idempotent_event` | B + C |
| **Views (cross-domain)** | `v_mgmt_*` (22), `v_oa_*` (18) | **Unique to factory DB** — pre-joined management/OA views |

---

## 3. Duplication Analysis

### 3.1 Exact Duplicates (Same Table Names)

| Table | In Systems | Status |
|-------|------------|--------|
| `inventory` | B, E, factory.rjvn | **Triplicated** |
| `inventory_transaction` | B, E, factory.rjvn | **Triplicated** |
| `iqc_inspection_draft` | B, E, factory.rjvn | **Triplicated** |
| `iqc_inspection_item` | B, E, factory.rjvn | **Triplicated** |
| `iqc_inspection_record` | B, E, factory.rjvn | **Triplicated** |
| `iqc_inspection_strictness` | B, E, factory.rjvn | **Triplicated** |
| `iqc_lot` | B, E, factory.rjvn | **Triplicated** |
| `iqc_lot_receipt` | B, E, factory.rjvn | **Triplicated** |
| `iqc_lot_strictness_count` | B, E, factory.rjvn | **Triplicated** |
| `iqc_report` | B, E, factory.rjvn | **Triplicated** |
| `iqc_standard_item` | B, E, factory.rjvn | **Triplicated** |
| `iqc_strictness_transfer_log` | B, E, factory.rjvn | **Triplicated** |
| `iqc_template` | B, E, factory.rjvn | **Triplicated** |
| `iqc_template_item` | B, E, factory.rjvn | **Triplicated** |
| `iqc_template_material` | B, E, factory.rjvn | **Triplicated** |
| `material` | B, E, factory.rjvn | **Triplicated** |
| `material_expiry_extension` | B, E, factory.rjvn | **Triplicated** |
| `material_requirement` | B, E, factory.rjvn | **Triplicated** |
| `material_requirement_item` | B, E, factory.rjvn | **Triplicated** |
| `material_substitution` | B, E, factory.rjvn | **Triplicated** |
| `mes_issue_writeback` | B, E, factory.rjvn | **Triplicated** |
| `mes_sync_log` | B, E, factory.rjvn | **Triplicated** |
| `mes_sync_state` | B, E, factory.rjvn | **Triplicated** |
| `mes_work_order_material` | B, E, factory.rjvn | **Triplicated** |
| `mrb_cc` | B, E, factory.rjvn | **Triplicated** |
| `mrb_disposition` | B, E, factory.rjvn | **Triplicated** |
| `mrb_disposition_label` | B, E, factory.rjvn | **Triplicated** |
| `mrb_review` | B, E, factory.rjvn | **Triplicated** |
| `mrb_reviewer` | B, E, factory.rjvn | **Triplicated** |
| `over_picking_item` | B, E, factory.rjvn | **Triplicated** |
| `over_picking_order` | B, E, factory.rjvn | **Triplicated** |
| `picking_order` | B, E, factory.rjvn | **Triplicated** |
| `picking_order_item` | B, E, factory.rjvn | **Triplicated** |
| `picking_reel` | B, E, factory.rjvn | **Triplicated** |
| `production_return` | B, E, factory.rjvn | **Triplicated** |
| `production_return_iqc` | B, E, factory.rjvn | **Triplicated** |
| `production_return_label` | B, E, factory.rjvn | **Triplicated** |
| `purchase_order` | B, E, factory.rjvn | **Triplicated** |
| `receipt_order` | B, E, factory.rjvn | **Triplicated** |
| `rework_order` | B, E, factory.rjvn | **Triplicated** |
| `role_user` | B, E, factory.rjvn | **Triplicated** |
| `sales_customer` | B, E, factory.rjvn | **Triplicated** |
| `sales_order` | B, E, factory.rjvn | **Triplicated** |
| `sales_quotation` | B, E, factory.rjvn | **Triplicated** |
| `stock_take_item` | B, E, factory.rjvn | **Triplicated** |
| `stock_take_log` | B, E, factory.rjvn | **Triplicated** |
| `stock_take_order` | B, E, factory.rjvn | **Triplicated** |
| `stock_transfer` | B, E, factory.rjvn | **Triplicated** |
| `supplier` | B, E, factory.rjvn | **Triplicated** |
| `supplier_audit` | B, E, factory.rjvn | **Triplicated** |
| `supplier_certificate` | B, E, factory.rjvn | **Triplicated** |
| `supplier_contract` | B, E, factory.rjvn | **Triplicated** |
| `supplier_delivery` | B, E, factory.rjvn | **Triplicated** |
| `supplier_evaluation` | B, E, factory.rjvn | **Triplicated** |
| `supplier_material` | B, E, factory.rjvn | **Triplicated** |
| `supplier_portal_user` | B, E | **Duplicated** (not in factory.rjvn) |
| `supplier_price_list` | B, E | **Duplicated** (not in factory.rjvn) |
| `supplier_qualification` | B, E | **Duplicated** (not in factory.rjvn) |
| `supplier_return_item` | B, E, factory.rjvn | **Triplicated** |
| `supplier_return_order` | B, E, factory.rjvn | **Triplicated** |
| `supplier_risk` | B, E | **Duplicated** (not in factory.rjvn) |
| `warehouse` | B, E, factory.rjvn | **Triplicated** |
| `warehouse_location` | B, E, factory.rjvn | **Triplicated** |
| `work_order` | B, E, factory.rjvn | **Triplicated** |
| `operation_log` | B, E, factory.rjvn | **Triplicated** |
| `equipment_asset` | B, E, factory.rjvn | **Triplicated** |
| `flow_instance` | B, E, factory.rjvn | **Triplicated** |
| `hr_attendance_raw` | B, E, factory.rjvn | **Triplicated** |
| `hr_department` | B, E, factory.rjvn | **Triplicated** |
| `hr_employee` | B, E, factory.rjvn | **Triplicated** |
| `hr_payroll_batch` | B, E, factory.rjvn | **Triplicated** |
| `sys_account` | B, E, factory.rjvn | **Triplicated** |
| `sys_notice` | B, E, factory.rjvn | **Triplicated** |
| `sys_param` | B, E, factory.rjvn | **Triplicated** |
| `sys_role` | B, E, factory.rjvn | **Triplicated** |
| `agv_*` (10 tables) | B, E | **Duplicated** (not in factory.rjvn) |
| `cfg_*` (11 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `md_*` (11 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `ord_*` (6 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `pln_*` (2 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `prd_*` (20 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `proc_*` (3 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `sys_*` (9 tables) | B, D | **Duplicated** (D is SQLite copy) |
| `itf_*` (2 tables) | B, D | **Duplicated** (D is SQLite copy) |

**Total exact-name duplicates: ~120+ table definitions across systems**

### 3.2 Conceptual Duplicates (Different Names, Same Purpose)

| Concept | System A | System B | Factory rjvn | System D |
|---------|----------|----------|--------------|----------|
| Work Order | `station_active_workorders` | `work_order`, `cm_workorder`, `ord_mo` | `work_order` | `ord_mo` |
| Material Lot | `wms_material_roll_labels` | `inventory`, `iqc_lot` | `inventory`, `iqc_lot` | — |
| BOM | (embedded) | `bom`, `bom_header`, `bom_item`, `mes_bom_item` | `bom`, `bom_item` | `bom_header`, `bom_item` |
| Station | `station_*` (50+) | `md_station`, `cfg_bind_station` | (merged in station_*) | `md_station` |
| SN Traceability | `canonical_sn_trace_events`, `factory_sn_master` | `prd_sn`, `prd_sn_rel`, `prd_box`, `prd_pallet` | `canonical_sn_trace_events`, `factory_sn_master`, `sn_journey_events` | `prd_sn`, `prd_sn_rel` |
| Equipment | `mes_smt_machine_channel_mapping` | `equipment_asset`, `equipment_type`, `md_equipment` | `equipment_asset` | `md_equipment` |
| Users/Roles | `pda_role_work_sessions` | `sys_user`, `sys_role`, `sys_user_role`, `sys_perm`, `sys_role_perm`, `sys_user_line` | `sys_user`, `sys_role`, `sys_user_role`, `sys_permission`, `sys_role_permission` | `sys_user`, `sys_role`, `sys_user_role`, `sys_perm`, `sys_role_perm` |
| IQC | `wms_receiving_label_ai_scans` | `iqc_*` (13 tables) | `iqc_*` (13 tables) | — |

---

## 4. What's MISSING from Primary Target (System A)

System A (smt-factory-system) is **production-ready for MES/WMS/Quality/Traceability** but **lacks**:

| Missing Domain | Tables Needed | Available In |
|----------------|---------------|--------------|
| **HR/Attendance/Payroll** | 7-8 tables | Factory rjvn (`hr_*`), System B (`hr_*`), OA dump (76 tables) |
| **Sales/CRM** | 7 tables | Factory rjvn (`sales_*`), System B (`sales_*`) |
| **Purchase/Procurement** | 1-13 tables | Factory rjvn (`purchase_order`, `supplier_*`), System B (`purchase_order`, `supplier_*` 13 tables) |
| **Flow/Workflow Engine** | 6 tables | Factory rjvn (`flow_*`), System B (`flow_*` 5 tables) |
| **AGV/Fleet** | 10 tables | System B, System E (`agv_*`) |
| **Equipment Maintenance (PM/CM)** | 4-7 tables | System B (`equipment_*`, `pm_*`, `calibration_*`, `condition_*`, `cm_*`), Factory rjvn (`equipment_asset`) |
| **Spare Parts** | 2 tables | System B (`spare_part`, `spare_part_bom`) |
| **Document Management** | 4 tables | System B (`doc_*`) |
| **OEE/Production Analytics** | 1+ tables | System B (`oee_log`), Factory rjvn (via views) |
| **Finance/Accounting** | Multiple | System B (partial), Factory rjvn (supplier_debt, payroll) |
| **Multi-language Master Data** | — | System A AGENT.md requires `name_zh/name_en/name_vi` — not yet in schema |

**System A has superior:**
- Station execution model (50+ `station_*` tables with rich state machine)
- SN traceability chain (`canonical_sn_trace_events` → `factory_sn_master` → `sn_journey_events`)
- IQC receiving integration (`wms_receiving_label_ai_scans`, `wms_material_roll_labels`)
- Real-time PDA/agent integration (`pda_*`, `mes_smt_loading_*`, `station_*`)
- 3D monitoring data structures (`station_bucket_snapshots`, `station_product_residence`)

---

## 5. Single Source of Truth Recommendation

### Verdict: **Factory DB `rjvn` schema IS the single source of truth**

**Evidence:**
1. **Already unified** — 221 tables combining WMS+MES+OA+HR+Sales+Supplier+Flow+Equipment
2. **Cross-domain views** — 40 `v_mgmt_*` + `v_oa_*` views for management/OA reporting
3. **Roles exist** — `role_wms`, `role_oa`, `role_mes`, `role_smt`, `role_mgmt`, `role_report`
4. **Contains System A's traceability** — `canonical_sn_trace_events`, `factory_sn_master`, `sn_journey_events` (A's tables replicated in rjvn)
5. **Contains System B's WMS/MES/IQC** — All 73 overlapping tables
6. **Contains OA data** — `hr_*`, `flow_*`, `oa_callback_log`, `oa_event_outbox`
7. **System A's DB (smt_factory) = factory.public** — Already synced/mirrored

**System A (codebase) should TARGET the factory DB `rjvn` schema**, not maintain separate `smt_factory` DB.

---

## 6. Concrete Merge/Kill/Port Plan

### 🟢 KEEP & EXTEND (Primary Target)
| Asset | Action |
|-------|--------|
| **System A codebase** (`smt-factory-system-worker`) | **KEEP** — Primary application. Retarget to `factory` DB `rjvn` schema. Add missing domains (HR, Sales, Purchase, Flow, AGV, Equipment PM, Finance). |
| **Factory DB `rjvn` schema** | **KEEP** — Canonical data layer. Add multilingual columns (`name_zh`, `name_en`, `name_vi`) per AGENT.md. |
| **Factory DB `public` schema** | **DEPRECATE** — Drop after A retargets to `rjvn`. Currently 1:1 mirror of A's tables. |
| **Factory DB `mesapp` schema** | **MIGRATE & DROP** — 29 tables (legacy MES). Move `bom`, `bom_entries`, `product`, `work_orders`, `container_box`, `pallet`, `ng_pool`, `ng_registry`, `defect_product`, `rework_log`, `spare_parts_replacement` → `rjvn`. Drop schema. |

### 🔴 KILL (Redundant/Obsolete)
| System | Reason |
|--------|--------|
| **System B (WMS-20261019)** | Schema-only (Drizzle definitions). Entire table set exists in factory.rjvn (73 direct) + factory has richer station/SN model. Codebase is NestJS — not aligned with A's architecture. |
| **System D (ruijing-mes)** | 100% subset of B. SQLite legacy. Python/FastAPI — wrong stack. Device drivers in `设备对接工具/` → **PORT** to A's integrations. |
| **System E (rjvn-factory-erp)** | Incomplete scaffold (88/178 tables). Strict subset of B. Fresh monorepo with no runtime value. |
| **OA standalone (System C)** | Separate PG instance (5433). 76 tables → **MIGRATE** into factory.rjvn (hr, attendance, payroll, org, flow). Fastify/Next.js codebase → **PORT** UI components to A's apps/web. |

### 🟡 PORT (Extract Value, Discard Rest)
| Source | What to Port | Target in A |
|--------|--------------|-------------|
| **System B schema.ts** | Missing domain definitions: `agv_*`, `calibration_*`, `condition_*`, `cm_*`, `doc_*`, `equipment_lifecycle_event`, `equipment_meter`, `equipment_type`, `flow_approval`, `flow_definition`, `flow_instance_step`, `flow_step`, `hr_attendance`, `hr_contract`, `hr_leave`, `hr_salary`, `md_*` (11), `mes_bom_item`, `mes_sys_param`, `mes_sys_role`, `oee_log`, `pm_plan`, `pm_task`, `prd_*` (20), `proc_*` (3), `spare_part`, `spare_part_bom`, `supplier_portal_user`, `supplier_price_list`, `supplier_qualification`, `supplier_risk`, `sys_api_key`, `sys_audit_log`, `sys_perm`, `sys_role_perm`, `sys_user_line` | Add as Drizzle/TypeORM entities in A's `packages/db` or migration SQL |
| **System D (ruijing-mes)** | Device drivers in `设备对接工具/` (SMT, SPI, AOI, ICT, etc.) | A's `integrations/` folder |
| **System D** | `api/itf_wms.py` WMS integration patterns | A's WMS↔MES sync (already has `mes_sync_log`, `mes_sync_state`) |
| **OA dump (System C)** | Full HR/Attendance/Payroll schema (76 tables) | Factory rjvn schema (extend `hr_*`, add `attendance_*`, `salary_*`, `onboarding_*`) |
| **OA codebase** | Next.js admin screens for org/attendance/leave/payroll | A's `apps/web` Admin module |

### 🔧 MIGRATION SEQUENCE

```
Phase 1 (Week 1-2): Schema Alignment
├── Add multilingual columns to all rjvn master tables (name_zh/name_en/name_vi)
├── Create missing domain tables in rjvn from B: agv, calibration, condition, cm, doc, equipment_lifecycle, equipment_meter, equipment_type, flow_def, flow_step, hr_attendance, hr_contract, hr_leave, hr_salary, md_*, mes_bom_item, mes_sys_param, mes_sys_role, oee_log, pm, prd, proc, spare_part, supplier_portal_user, supplier_price_list, supplier_qualification, supplier_risk, sys_api_key, sys_audit_log, sys_perm, sys_role_perm, sys_user_line
├── Migrate mesapp → rjvn (29 tables)
└── Drop factory.public schema (after A retargeted)

Phase 2 (Week 3-4): Codebase Retarget
├── Update A's DB connection to `factory` DB, schema `rjvn`
├── Update all repositories/services to use rjvn tables
├── Add repositories for new domains (HR, Sales, Purchase, Flow, AGV, Equipment PM, Finance)
├── Port OA HR/Attendance/Payroll UI → A's apps/web Admin
├── Port Device drivers from D → A's integrations/
└── Run full test suite (215 tests) against rjvn

Phase 3 (Week 5-6): Cleanup & Validation
├── Decommission smt_factory DB
├── Decommission OA standalone PG (port 5433)
├── Archive B, D, E repos (read-only)
├── Verify all 6 roles work: role_wms, role_oa, role_mes, role_smt, role_mgmt, role_report
├── Validate trilingual UI (zh-CN, en-US, vi-VN)
└── M11 Pilot deployment gate
```

### 📊 Table Count After Merge

| Layer | Tables | Source |
|-------|--------|--------|
| **factory.rjvn (canonical)** | ~280 | Current 221 + B's 90 missing + OA 76 - overlaps |
| **A codebase entities** | ~280 | 1:1 mapping to rjvn |
| **A migrations** | 238+ | Existing + new domain migrations |
| **Dead schemas** | 0 | public, mesapp, wms (B), oa_system (C), ruijing-mes (D), rjvn-factory-erp (E) |

---

## 7. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss during public→rjvn retarget | Low | High | Run in transaction, verify row counts, keep backup |
| Missing FK constraints in rjvn | Medium | Medium | Run FK validation script (B has full Drizzle relations) |
| Trilingual migration breaks existing UI | Medium | High | Add columns as nullable, backfill, then enforce |
| OA payroll calculation logic in Fastify not portable | Medium | Medium | Port business logic to A's worker service, not UI |
| Device driver protocols (D) undocumented | High | Medium | Reverse-engineer from `设备对接工具/` code, test on hardware |
| M11 pilot deadline pressure | High | High | Phase 1-2 must complete before M11 gate |

---

## Appendix: Complete Table Lists

See `all_tables.json` for machine-readable lists of all 7 systems/layers.

---
*Report generated from live DB queries (factory, smt_factory), schema.ts parsing (B, E), schema.sql parsing (D), and dump analysis (C). No source files modified.*