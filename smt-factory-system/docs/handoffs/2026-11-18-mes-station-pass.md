# HANDOFF — MES 原生过站引擎 + OQC AQL（2026-11-18）

## 目标
把 `D:\rj\repos\MES-ruijing`（Flask + SQLite）的过站 / AQL 能力原生移植进
`smt-factory-system`（PostgreSQL），后端引擎 + 前端控制台。

## 二、OQC AQL 出货抽检（同日完成）

| 文件 | 作用 |
|---|---|
| `services/api/src/aql-plans.js` | Z1.4 单次抽样表，**由 `core/aql.py` 程序化生成**（不是手抄）：SAMPLE_SIZE / 15 段批量区间 / 正常·加严·放宽三张 Ac-Re 表 |
| `services/api/src/aql.js` | 纯函数引擎：`codeFor`（批量→样本代字，支持检验水平 I/II/III 偏移）、`plan`（缺列时按 Z1.4 跳相邻代字）、`plansFor`（CR Ac 固定 0 + MA/MI 取较大样本）、`verdict`（三档判定，返回中文理由） |
| `services/api/src/routes/oqc-aql.js` | `/api/qms/oqc-aql`：方案预览、建批套方案、逐件记录（同 SN 重扫=更正，不重复计数）、判定、处置（返工/特采/报废） |
| `database/migrations/271_oqc_aql_plan_columns.sql` | 给已有 `qms_oqc_batches` 加 AQL 列（aql_ma/aql_mi/sample_code/ac_major/ac_minor…/disposition），纯增量 |
| `apps/web/src/qms/OqcAqlConsole.tsx` | 一屏：算方案 → 建批 → 扫件判定 → CR/MA/MI 计数 → 结论 → 处置 |
| `tests/aql.test.ts` | 16 条：代字映射 / 水平偏移 / 缺列跳代字 / 三档严格度 / CR 一票否决 / 三张表完整性（16 代字 × Re 关系） |

复用已有表，**没有新建 OQC 表**：`qms_oqc_batches` / `qms_oqc_items` 本来就是空的脚手架，
AQL 直接落在这两张表上（`ac_reject`/`re_pass` 仍写值，兼容老读者）。

### AQL 实测（真实 API，工号 QC_VN_01）

| 场景 | 结果 |
|---|---|
| lot 500 / AQL MA1.0 MI2.5 / 水平 II | n=50，代字 H，Ac CR0 / MA1 / MI3 |
| 48 PASS + 1 MA + 3 MI | `PASSED`（等于 Ac，收） |
| 2 MA | `FAILED`（2 > Ac 1） |
| 1 CR | `FAILED`（致命 Ac=0 一票否决） |
| 同 SN 重扫 PASS | 更正，不重复计数（items 仍 2 条，MA 1） |
| lot 1200 / 加严 | n=80，代字 J |
| 处置 | REWORK / WAIVER / SCRAP + 原因写入 `disposition_*` |

## 一、MES 过站引擎

## 已完成（文件已落盘，未提交）

| 文件 | 作用 |
|---|---|
| `database/migrations/269_mes_station_pass_engine.sql` | 新增 3 表：`mes_station_pass_policies`（每站防呆策略）、`mes_skip_releases`（跳站放行单）、`mes_station_pass_events`（过站事件，含 `idempotency_key` 幂等） |
| `services/api/src/station-pass.js` | 纯函数规则引擎 `evaluateStationPass()`，13 条规则：STATION_INVALID / NG_DEFECT_REQUIRED / MANUAL_PASS_DENIED / WORK_ORDER_NOT_RELEASED / PRODUCT_NOT_REGISTERED / PRODUCT_TERMINAL / NG_ROUTE_ACTIVE / MISSING_REQUIRED_STATION / STATION_NOT_EXPECTED / DUPLICATE_STATION_PASS / RETEST_LIMIT_EXCEEDED / DWELL_NOT_SATISFIED / UPSTREAM_NG_OPEN |
| `services/api/src/routes/station-pass.js` | `createStationPassRouter({ authenticateJWT, requirePermission })` 工厂：过站、状态、历史、策略 CRUD、放行单申请/批准/驳回。拦截也返回 200（携带完整规则链），4xx 只留给传输/参数错误 |
| `apps/web/src/mes/StationPassConsole.tsx` | 过站校验台（选工位 + 扫 SN + OK/NG + 规则链结论 + 历史 + 放行单审批），走 `apiClient` |
| `services/api/server.js` | 加 `import { createStationPassRouter }` + `api.use("/mes/station-pass", ...)` 挂载 |
| `apps/web/src/mes/index.ts` | `stationPass` 进 `MesTabKey` / `mesTabKeys` / `mesTabTranslationKeys` / `mesGroups.productExecution` / `productCore`，并 barrel 导出 |
| `apps/web/src/App.tsx` | `case "stationPass": return <StationPassConsole locale={locale} />` |
| `apps/web/src/i18n.ts` | `mes.subnav.stationPass` + 50 条 `mes.stationPass.*`（zh / vi / en 三语齐全） |
| `database/migrations/270_mes_station_pass_app_grants.sql` | 把 3 张新表 owner 交给应用角色（`smt_factory`），否则 API 写入报 `permission denied` |
| `scripts/migrate.mjs` | 自动加载 `.env` 的 `PG*`，避免迁移以 `postgres` 身份跑、建出 API 没权限的表 |

复用已有表，未新建：`mes_product_units` / `mes_product_identifiers` /
`mes_product_attendance` / `mes_product_station_visits` /
`mes_product_dependent_sequences` / `mes_operating_event_ledger` /
`stations` / `station_sequences` / `work_orders` / `ng_defect_records`。

## 已验证

- `node --check` 两个后端文件：通过。
- 迁移 269 + 270 已 apply 到线上 `smt_factory`（新表 owner = `smt_factory`）。
- 迁移 SQL 干跑：临时 schema 内 3 表 5 索引建成后 `ROLLBACK`。
- 上表所有引用列已核对 `information_schema`，全部存在。
- `npm run typecheck`：无输出。
- `npm run test`：380 passed / 3 failed（`backend-validation.test.ts`、`wms-3d-security-contract.test.ts`，改动前就红）。
- `npm run build`：通过（14.41s）。

### 端到端实测（真实 API :8080，L002 线，工单 26061020007）

| 场景 | 结果 |
|---|---|
| 无工单首扫 | `HOLD / WORK_ORDER_NOT_RELEASED` |
| 首站建档（带工单） | `ALLOW / FIRST_REGISTRATION_REQUIRED` |
| 同站重复扫 | `REJECT / STATION_NOT_EXPECTED`（应到下一站，先命中"扫错站"） |
| 按序下一站 | `ALLOW / STATION_PASSED` |
| 跳过中间站 | `REJECT / STATION_NOT_EXPECTED` |
| NG 无不良码 | `REJECT / NG_DEFECT_REQUIRED` |
| NG 带不良码 | `REPAIR_ROUTE / NG_RECORDED` + 生成 REPAIR 序列 |
| 跳站放行单：未申请 | `REJECT / STATION_NOT_EXPECTED`（提示需放行单） |
| 已申请未批准 | `REJECT`，提示"放行单待审批" |
| 批准后再扫 | `ALLOW`，放行单 `CONSUMED` 并记进事件 |
| 同 idempotencyKey 重放 | `replay=true`，不重复写入 |
| L001（路线与工位主数据对不上） | `REJECT / ROUTE_NOT_CONFIGURED`，提示工艺核对 `station_sequences` |
| L003（完全没配路线） | 保持自由流，首站建档 `ALLOW` |

落库核对：`mes_station_pass_events` / `mes_product_units` / `mes_product_identifiers` /
`mes_product_attendance` / `mes_product_station_visits` / `mes_product_dependent_sequences` /
`mes_operating_event_ledger` / `mes_skip_releases` 均有对应行。

测试数据 SN 前缀 `TESTPASS0001..0006`，**已清理**（六张表相关行全部删除，核对为 0）。

## 路线解析（重要）

`station_sequences.station_code` 有两种写法，`loadRoute` 两种都认：

1. **真实工位码**（L002/L004）：直接匹配 `stations.code`。
2. **工位类型码**（L001：`smt_aoi` 等）：按同线 + 同 `station_types.code` 反查唯一在用工位。

解析结果里带 `resolved` 标记；只要有一条解析不出来，`route.configured=false`，
过站直接返回 `REJECT / ROUTE_NOT_CONFIGURED`（fail-closed），不会把产品误判完工、
也不会再提示"去一个不存在的工位建档"。

## 未完成 / 已知问题

1. **L001 路线数据本身仍是坏的**：7 条里有 6 条是 SMT 前段类型码（`smt_pda_loading`/`smt_spi`/…），
   而 L001 上没有这些类型的工位，所以 7 条只解析出 `smt_aoi → AOI-01`。
   现在行为是：L001 上过站一律 `ROUTE_NOT_CONFIGURED` + 明确提示，**不再误导**。
   要真正放行，需要工艺按 L001 实际 78 个工位重配 `station_sequences`（这属于工艺决定，代码不该猜顺序）。
2. **`process_route_steps.station_id` 全为 NULL**，产品级路线（`process_routes`）暂时没法用来判定，
   只能退回线别级 `station_sequences`。
3. **`scripts/migrate.mjs` 原本不读 `.env`**，默认以 `postgres/postgres` 连库，它建的表 owner 是 postgres，
   API（`smt_factory`）没有权限。已改为自动加载 `.env` 里的 `PG*`；线上现存 80 张 postgres 拥有的表是历史遗留，
   真要统一得写一个批量 `ALTER TABLE ... OWNER TO smt_factory` 的迁移。
4. **`wmsApi.getIqcWaitingQueue`** 仍指向 `/wms/receiving/qr-bindings`（语义错），只对齐了类型。
5. `apps/web/src/reports/` 被 `.gitignore` 的 `**/reports/` 吞掉，之前 ReportDomain 修复不会进版本库。
6. AQL / OQC 已移植（见上「二、OQC AQL 出货抽检」）。**仍未移植**的是 MES-ruijing 的 `api/mesapi.pyc`（设备网关，
   源码已丢失）与 `core/oqc_aql.py` 里的托盘/PO 台数拆分（`_po_lot_qty`、`_belongs`）——后者依赖其 SQLite 的
   装箱结构，需要先确认本系统的箱码模型再搬。

## 验证命令
```powershell
node --check services/api/src/routes/station-pass.js
node --check services/api/src/station-pass.js
npm run typecheck        # 期望：无输出
npm run test             # 期望：380 passed / 3 known fail
```

## 不要做
- 不要重启 :8080 / :5178。
- 不要 `git add -A`（根目录 400+ 垃圾文件）。
- 不要碰 `MISSION.md` / `FACTORY.md` / `FACTORY_RULES.md` / `harness/` / `.factory/locks` / `.factory/holdout`。
