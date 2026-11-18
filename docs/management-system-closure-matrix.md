# Management System Unification Closure Matrix

Updated: 2026-08-07

This is the control record for the unification effort. A software item is closed only when code evidence and a repeatable check exist. A factory item is closed only after the named owner supplies the production value and acceptance evidence. No production SN, NG, repair, binding, or completion data is created by this audit.

## Closed in software

| Area | Evidence | Verification |
|---|---|---|
| Employee web login | `apps/employee-app/src/AuthScreen.tsx` uses shared `/auth/login` | TypeScript/Vite build passed |
| Employee web language foundation | `apps/employee-app/src/i18n.ts` repaired; authenticated language switch added | Source mojibake marker scan passed |
| PDA management overview | `services/api/server.js` exposes `/pda/management/overview` | API syntax check passed |
| Plant/line/operator authorization | Server checks role before scope projection | API source audit |
| Manual-line domain isolation | PDA routes reject non-`manual-line` requests | API source audit; fixture test passes |
| Event idempotency | Event-ledger and WMS exchange use `eventId` conflict handling | Backend test suite passes |
| Feeder validation/loading/return/history | Server routes exist for validate, confirm, load, return, and history | API source audit |
| Station heartbeat projection | Station heartbeat routes and PDA overview projection exist | API source audit |
| PDA Android authentication code | `PdaApi`, `PdaRepository`, `PdaViewModel`, and `AuthTokenInterceptor` now use MES login/session | Android compile pending toolchain availability |

## Verification completed

- Employee app: `npm run build` passed.
- Web management app: `npm run build` passed; duplicate translation-key warnings remain open.
- API: `node --check server.js` and `node --check src/routes/manual-line.js` passed.
- PDA backend fixture tests: 5 passed.
- Browser visual sweep: not run; no browser backend is connected.
- Android build: not run; no `gradlew.bat` and no Gradle CLI are available.

## Still requiring named factory decisions

These cannot be safely invented or closed by code:

1. Production MES/API base URL and TLS certificate route.
2. Authoritative employee/role/line/station master-data owner.
3. PDA inventory, registration owner, and replacement authority.
4. Approved scanner models and connection modes.
5. Pilot line, pilot station, line manager, and acceptance operator.
6. Production deployment window, rollback owner, and signed-APK release authority.
7. Physical scanner/network/browser acceptance and real-data reconciliation.

Until those values and signatures exist, status is `SOFTWARE_READY / PRODUCTION_SIGN-OFF_PENDING`.

## Playwright page sweep — 2026-08-07

- Site tested: `http://127.0.0.1:5178/` with API at `http://127.0.0.1:8080`.
- 24 primary navigation pages opened successfully as the factory-manager role.
- Viewports tested: 1366×768, 1280×800, and 390×844.
- After the responsive patch, horizontal overflow was false at both 1366×768 and 390×844.
- Procurement and e-invoice navigation labels no longer render as raw `nav.*` keys.
- Backend 500s observed during the sweep: `/pmc/work-orders`, `/boms`, `/api/mes/managers/status`, and `/api/mes/overall-balance` intermittently returned `timeout exceeded when trying to connect`; `/dashboard/summary`, `/pmc/customer-pos`, and `/quality/records` returned successfully on direct authenticated reads.
- Build passed after the UI patch. Existing duplicate translation-key and duplicate switch-case warnings remain technical cleanup items.

## UI-agent/code-review follow-up

- Headless Playwright completed the local site sweep because the connected in-app browser backend was unavailable.
- All 24 primary navigation pages opened as the factory-manager role; 8 visible read-only MES tabs were also exercised.
- The follow-up pass found no console errors or HTTP 5xx responses. Direct authenticated API checks still show intermittent backend timeout risk on PMC/BOM/MES aggregate endpoints; this remains an environment/service health item.
- Horizontal overflow is now false at 1366x768 and 390x844, including Management and Virtual Employees.
- Fixed long multilingual agent-card labels and the Management menu-access grid; removed the unreachable duplicate maintenance `andon` switch case.

## Performance follow-up

- PMC work-order and BOM list endpoints now run count/data reads concurrently and cap pagination at 200 rows.
- MES aggregate reads now run independent balance/alert queries concurrently and cache successful read-only dashboard responses for 3 seconds.
- Missing optional e-invoice tables return an empty read-only list instead of a 500 response; no production data is created.
- Fingerprinted production assets receive immutable one-year browser caching.
- Duplicate translation definitions were removed; the build now has no duplicate-key warnings.
- Verification after API restart: PMC work orders 200/~6ms warm, BOMs 200/~6ms warm, MES balance 200/~2ms cached, manager status 200; Playwright opened all 24 modules with no console errors, 5xx responses, or overflow at 1366x768.
- Remaining performance item: the main production JavaScript chunk is still large (~5.2 MB) and requires a larger route extraction to fully code-split.

## Plant Manager PDA follow-up (2026-08-08)

- Located the dedicated Android flavor at `瑞晶越南工位-正式命名/000-线长管理PDA/androidlinemanager`.
- Fixed the Plant Manager list viewport so approval/work-order content stays below the header, status banner, and filters on small PDA screens.
- Fixed the dedicated flavor's start-screen Back action to log out safely instead of popping to an empty navigation stack.
- Removed the shared Home FAB from the dedicated Plant Manager flavor so it cannot escape into the generic manager dashboard.
- `compilePlantManagerKotlin`, `testPlantManagerUnitTest`, and `assemblePlantManager` passed.
- Emulator smoke test passed: install, launch, quick-login, Plant Manager screen render, MES-offline lock, read-only test banner, filters, approval/work-order sections, and no AndroidRuntime crash. No production write action was submitted.
