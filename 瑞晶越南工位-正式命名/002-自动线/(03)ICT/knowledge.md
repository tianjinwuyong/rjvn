# NG Retest Policy - All Stations

## Overview
All stations allow failed products to be retested before committing to NG status. This policy applies to:
- ICT (In-Circuit Test)
- FCT (Functional Circuit Test)
- ATE (Automatic Test Equipment)
- 老化柜 (Aging Chamber)
- 包装 (Packing)
- All other production stations

---

## NG Testing Rules

### Rule 1: Retest Opportunities
- **2 retest chances** after initial NG detection
- **Total 3 attempts** allowed (1 initial + 2 retests)
- All 3 attempts must occur within **2 hours** of initial NG detection

### Rule 2: Time Window
- **2 hours** from initial NG detection to complete all retests
- If 2 hours pass without a PASS, the SN is confirmed as NG
- Retests after 2-hour expiry are treated as new initial failures

### Rule 3: Pass Behavior
- If **any attempt shows PASS** → product moves to next station
- Remove SN from retest tracking immediately

### Rule 4: NG Confirmation
NG is confirmed when ANY of these conditions are met:
- 3 FAIL attempts within 2-hour window
- 2-hour window expires with remaining retest attempts unused

### Rule 5: Retest After Expiry
- If 2-hour window expires and product still needs retesting, **authorization is required**
- Only admin/authorized personnel can approve retest after 2-hour window
- Attempt counter resets for the new failure after authorization

---

## System Behavior

| Event | Action |
|-------|--------|
| 1st FAIL | Start 2-hour timer, attempts=1 |
| 2nd FAIL (within 2h) | attempts=2, allow retest |
| 3rd FAIL (within 2h) | Confirm NG, add to ng_pool |
| PASS at any point | Remove from tracking, product passes |
| 2h expires, <3 attempts | Confirm NG, add to ng_pool |
| FAIL after 2h expiry | **Admin authorization required** to retest |

---

## Data Model

### SN Attempt Tracking Examples
```
SN: 1G7800001A
Station: ICT | Line: 004
First Fail: 2026-07-14 10:00:00
Attempts: 3
Status: NG_CONFIRMED (all 3 failed within 2h)

SN: 1G7800002A
Station: ICT | Line: 004
First Fail: 2026-07-14 10:30:00
Attempts: 2
Status: RETEST_WINDOW (within 2h, has 1 more attempt)

SN: 1G7800003A
Station: ICT | Line: 004
First Fail: 2026-07-14 08:00:00
Attempts: 2
Status: NG_CONFIRMED (2h window expired)
```

### Database Schema
```sql
CREATE TABLE ng_retest_tracker (
    sn TEXT PRIMARY KEY,
    station_code TEXT NOT NULL,     -- 'ICT', 'FCT', 'ATE', etc.
    line_name TEXT,
    first_fail_time TEXT,
    attempts INTEGER DEFAULT 1,
    status TEXT,                   -- 'RETEST_WINDOW', 'NG_CONFIRMED', 'PASSED'
    source_file TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);
```

---

## Station Configuration
- Default station: ICT
- Default line: 004
- Retest window: 2 hours
- Max attempts: 3
