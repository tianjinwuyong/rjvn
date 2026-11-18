# smt-factory-system 与 统一PDA管理 — 联合状态报告

> 勘察日期：2026-09-20 · 覆盖：`smt-factory-system/`（MES/WMS/PMC 主系统）与 `统一PDA管理/unifiedpda/`（Kotlin Android 统一 PDA）

## 一、结论摘要

两个项目都停在 **2026-09-10 前后** 的同一批工作上，之后没有新的提交或构建。周报
（`smt-factory-system/docs/work-summary-2026-09-01-10.md`）中列出的 4 项「待收尾」经逐一核验，
**全部仍未闭环**，且其中收发料删除链路存在 2 个可复现的代码缺陷。

## 二、主系统 smt-factory-system

| 项 | 值 |
|---|---|
| 分支 | `feat/material-fetching-consumption-flow` |
| HEAD | `55414c7` 2026-09-10 15:52 · feat(wms): per-lot low stock warning, canvas sync sweep, material master balances |
| 远端 | 与 origin 同步；领先 main 16 个提交（未合回 main） |
| 未提交改动 | 2 个文件：`apps/web/src/wms/WmsIqcFlowPages.tsx`、`services/api/server.js`，合计 +179/−37 |

未跟踪文件 **525 个**，构成：

- 目录：`scripts/` 199 · 仓库根目录散落文件 185 · `tests/` 105 · `docs/` 8 · `services/` 6 · `integrations/` 6
- 扩展名：`.cjs` 138 · `.mjs` 107 · `.ps1` 73 · `.ts` 60 · `.py` 37 · `.md` 23 · `.bat` 22 · `.zip`/`.tgz` 4

判断：绝大部分是调试脚本与一次性验证产物（读 Excel、q155/q122 查询、Playwright 冒烟等），
不是应提交的业务代码。**真正待提交的只有 server.js 与 WmsIqcFlowPages.tsx 两处。**

### 未提交改动的实际内容（server.js +195 行）

- 新增 `DELETE /wms/receiving/pre-iqc`（全部删除）与 `DELETE /wms/receiving/pre-iqc/:lotNo`（单条删除），`requirePermission("wms.execute")`
- 删除范围：`wms_receiving_pallet_box_bindings` → `inventory_transactions` → `pda_inspection_records` → `material_lots`
- pre-IQC NG 库位自动 provision

## 三、统一PDA管理 / unifiedpda

| 项 | 值 |
|---|---|
| 版本控制 | **不是 git 仓库**（无版本历史可追溯） |
| 包名 / applicationId | `com.smt.materialloader` / `com.ruijing.linemanager` |
| versionCode / versionName | 2 / 1.0.0（导出 APK 文件名却到 v0.24.0，版本号未与文件名对齐） |
| 目标平台 | compileSdk 34 · minSdk 26 · Java 17 · Compose BOM 2024.06.00 · CameraX 1.3.4 · ML Kit barcode 17.3.0 + 中文 OCR |
| 构建变体 | 8 个：debug / hotelDebug / receivingOnly / release / plantManager / plantManagerRelease / unifiedManagement / unifiedManagementRelease |
| API 故障转移 | 155 → 122 → 234（GET 级联，POST/PUT/DELETE 不重放） |
| 源码规模 | 129 个文件（app/src，不含 build） |
| 多语言 | values / values-zh / values-vi 三套 strings |

最近改动（倒序）：

1. `BarcodeScanner.kt` — **2026-09-11 06:38**（11.7 KB）
2. `MaterialReceivingScreen.kt` / `MaterialReceivingViewModel.kt` — 2026-09-10 17:54
3. `AppNavigation.kt`、`LoginScreen.kt`、`EmployeeRights.kt` — 2026-09-10 06:16
4. collect / shortage / return / pick / fetching / issue 系列 — 2026-09-07 ~ 09-09

### 关键发现：新冷却逻辑从未被构建

- 最新 APK 产物：`app/build/outputs/apk/debug/app-debug.apk` — **2026-09-10 17:56**（87.5 MB）
- `BarcodeScanner.kt` 修改时间：**2026-09-11 06:38**

→ 时间戳晚于最后一次构建，**新相机冷却逻辑（dup 不再毒化、rePresentGapMs=1500ms）还没有编译进任何 APK，
装机验证（待收尾第 1 项）事实上不可能做过**。导出到 `统一PDA管理/` 的 APK 也停留在 2026-09-04。

当前冷却实现要点（已读码确认）：

- `isScanningState` 用单一 `remember { mutableStateOf }` 实例，避免 analyzer 捕获陈旧实例（有注释说明）
- `recentScanTimes`（seen 时间）+ `firedScanTimes`（真正触发过的时间）双表；已触发过的码需离开视野 >1500ms 才可再次触发
- dup 侧：`MaterialReceivingViewModel` 中 `delay(3000)` 自动继续 +「▶ 立即继续扫描下一箱」大绿按钮，`dupLocked` 恒为 false（锁已移除）

## 四、已核实的缺陷

1. **pre-IQC 删除遗漏 `wms_receiving_qr_registrations` 清理**（即待收尾第 2 项，仍未修）
   - 表定义：`server.js:11787`；删除端点：`server.js:20442`（全部）、`20460`（单条）
   - 两个端点清理了 box bindings / inventory_transactions / pda_inspection_records / material_lots，
     但**没有任何 `DELETE FROM wms_receiving_qr_registrations`** → 产生以 `material_lot_id` 悬空引用已删批次的孤儿行，
     且该表被 12314 / 12446 / 12546 / 19833 / 35308 等处 JOIN/INSERT 使用，残留会污染列表与报表。

2. **单条删除的大小写不一致**：`server.js:20465` 用 `WHERE lot_no=$1`，而同表其他删除（`20078`）用
   `UPPER(lot_no)=UPPER($1)`。大小写不匹配时会「显示删除成功但实际删不掉」。

3. **响应对象重复键**：`server.js:20472` `{ lot: lotNo, ..., lot: !!lot }` — `lot` 键定义两次，后者覆盖前者，
   调用方拿到的是布尔值而非 lotNo。

4. **`dupLocked` 已成死字段**：全工程只在 `MaterialReceivingViewModel.kt` 被写为 `false`（5 处），
   无任何读取方；UI 层（MaterialReceivingScreen）不引用。锁语义已迁到 3 秒自动继续 + 大绿按钮，
   字段可删。

5. **`recentScanTimes` / `firedScanTimes` 无界增长**：`BarcodeScanner.kt` 的两个 `mutableMapOf` 只增不清，
   长班次连续扫码会缓慢累积；建议在触发后清理或加 LRU 上限。

## 五、待收尾清单核验（周报 4 项）

| # | 周报项 | 核验结果 |
|---|---|---|
| 1 | BarcodeScanner 新冷却逻辑装机验证 | **未做** — 代码写于 09-11，但最新 APK 是 09-10 17:56，逻辑未进包 |
| 2 | pre-IQC 彻底删除补 `wms_receiving_qr_registrations` 清理 | **未修** — 两个删除端点均无该表清理 |
| 3 | server.js / IqcFlowPages 提交 + push | **未做** — 仍是 2 个 modified，未入提交 |
| 4 | 收→IQC→NG→collect→pick 全链路重测 | 无证据表明已执行 |

## 六、建议下一步（按依赖顺序）

1. 修 server.js 三处缺陷（缺表清理、大小写归一、重复键），顺带删 `dupLocked` 死字段 —— 这三处都在同一批未提交改动里，改完一起提交最干净。
2. 用 `gradlew assembleDebug`（PowerShell + adb 流程）重新出包，让 BarcodeScanner 新逻辑真正进入 APK。
3. PDA 装机（真机 + MuMu）走一遍 收 → IQC → NG → collect → pick，验证冷却逻辑与删除链路。
4. 处理 525 个未跟踪文件：区分「应提交的 docs/tests 资产」与「一次性调试脚本」，后者建议挪到仓库外或加入 .gitignore。
5. `unifiedpda` 纳入 git（哪怕是本地仓库），否则 129 个源文件无任何历史可回溯。

## 附：两个仓库的对接点

- PDA 通过 Retrofit + `EndpointFailoverInterceptor` 打向 155/122/234 的 `:8080`（`server.js`）
- 收料链路：PDA `MaterialReceivingScreen` → `/wms/receiving/*`；pre-IQC 删除按钮在 poReceipt 页面
- IQC 链路：`WmsIqcFlowPages.tsx`（Web 端）与 PDA `IqcInspectionScreen.kt` 共用同一批 `/wms/*` 接口
- 术语与契约以 `smt-factory-system/CONTEXT.md`、`docs/20-canonical-operating-contract.md`、`统一PDA管理/CONTEXT.md` 为准
