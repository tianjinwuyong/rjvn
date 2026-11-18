# Agent Guidance — 回修站质量工位 (Repair Station)

## Workspace

```
005-回修站质量工位/          ← YOU ARE HERE (repair station specific)
├── 回修站质量工位.py        ← Main desktop app (Tkinter)
├── mes_client.py           ← MES API client
├── data/                   ← Local SQLite DB + logs
├── 维修架构.md             ← System architecture
└── r.md                    ← Process flow docs
```

**Parent directory** (`越南工厂瑞晶/`) contains the full `smt-factory-system/` MES codebase.

## Repair Station App

**Entry point:** `回修站质量工位.py` — standalone Tkinter desktop app.

### Running
```bash
python 回修站质量工位.py
```
Requires: `pynput` for barcode scanner hook (`pip install pynput`).

### Key Constants (hardcoded in file)
| Constant | Value | Meaning |
|---|---|---|
| `TCP_PORT` | `1005` | TCP server for scanner input |
| `MES_BASE_URL` | `http://localhost:6309` | MES API base |
| `MAX_REPAIR_COUNT` | `3` | Scrap threshold |
| `DB_PATH` | `data/rework.db` | Local SQLite |

### Repair Workflow (5 locked steps)
1. ① 拆壳检查 (Disassembly)
2. ② PCB故障定位 (PCB fault location)
3. ③ 元件更换焊接 (Component replacement)
4. ④ 清洗烘干 (Cleaning)
5. ⑤ 重装紧固 (Reassembly)
→ ⑥ 修复后测试 (Post-repair tests)

### Post-Repair Tests
- 基本电性测试 (Electrical)
- 老化联测 (Aging)
- 耐压安全测试 (Hipot)

### Defect Code Dictionary
| Source | Codes |
|---|---|
| ATE | OC-001, SC-001, HV-001, IR-001, VR-001, FN-001, CM-001 |
| 高压测试 | HIPOT-01~04 |
| 老化测试 | AG-001~005 |
| 通用 | GN-001~006 |

## MES API Integration

### NG Registry Check
```
GET /api/aging/ng_registry/check?sn={SN}
GET /api/mes/ng-registry/check?sn={SN}&stationCode={code}&lineCode={code}
```
Returns: NG records from `ng_defect_records` table.

### Repair Upload (NG产生时报废上报考修记录)
```
POST /api/rework/upload
Body: {sn, sourceStation, sourceLine, routeTo, defectCode, defectReason, materialCode, repairCount, operator}
```
- Writes to `rework.rework_records` with `result='open'`
- Prevents duplicate: returns 409 if SN already has `result='repaired'`

### NG Clearance (修复成功后清除NG标记)
```
POST /api/rework/clear-ng
Body: {sn, repairResult, operator}
```
- Sets `result='repaired'` (repairResult='pass') or `result='scrapped'`
- Deletes SN from `mes.ng_pool`
- Updates `ng_defect_records.repair_status`

### 回修站实时监控看板
```
GET /api/mes/rework/dashboard
```
- Returns: todayStats (total/repaired/scrapped/inProgress), openRecords, recentRecords, stations
- Frontend: `apps/web/src/mes/ReworkDashboard.tsx` — MES → 回修站 tab

## Database

### Local SQLite Schema (`data/rework.db`)
- `rework_log` — repair records (SN, source, route, defect, material)
- `repair_process` — step tracking (per-step confirm)
- `repair_test` — post-repair test results
- `rework_count` — SN repair count (for ≥3 scrap logic)

### MES PostgreSQL
- `ng_defect_records` — all NG events (partitioned by year)
- `mes.ng_pool` — remote NG pool
- `mes.sn_pool` — remote SN pool

## MES API Server
- **Port:** 6309
- **File:** `smt-factory-system/services/api/server.js`
- **Auth:** JWT, hardcoded test passwords (`Factory@123`)
- Test accounts: `VN_OP_001`, `VN_WH_001`, `PMC_CN_01`, `QC_VN_01`

## Common Tasks

### Add new defect code
Edit `DEFECT_CODES` dict in `回修站质量工位.py` and add to `get_defect_codes_for_source()`.

### Change MES endpoint URL
Edit `MES_BASE_URL` constant at top of `回修站质量工位.py`.

### Add new repair step
1. Add tuple to `REPAIR_STEPS` list
2. Update step indexes (`STEP_REPAIR`, `STEP_TEST`, `STEP_RESULT`)
3. Add step confirmation logic in `_confirm_step()` / `_show_step_content()`

### Change scrap threshold
Change `MAX_REPAIR_COUNT` constant (default: 3).

## Troubleshooting

- **Scanner not working:** Check `pynput` installed, check TCP port 1005 not blocked
- **MES not reachable:** Verify `MES_BASE_URL` is correct, MES server running on port 6309
- **NG not clearing:** Check `/api/rework/clear-ng` endpoint exists in MES server.js
- **SQLite locked:** Only one instance of app should run at a time

## Key File References

| File | Purpose |
|---|---|
| `回修站质量工位.py` | Main app (1300+ lines) |
| `mes_client.py` | MES API client helper |
| `smt-factory-system/services/api/server.js` | MES backend (NG registry, rework endpoints) |
| `smt-factory-system/database/migrations/016_mes_ng_sn_pool.sql` | `mes.ng_pool` schema |
| `smt-factory-system/database/migrations/017_simplified_ng_sn_audit.sql` | `ng_defect_records` schema |
