# Station UI terminology verification queue

This queue prevents guessed translations from entering production Station Agents. English candidates describe the intended system meaning; Chinese and Vietnamese wording must be approved by native-speaking production owners before bulk replacement.

| Priority | Concept / source label | English candidate | Chinese status | Vietnamese status | Pronunciation / UI rule | Owner / state |
|---|---|---|---|---|---|---|
| P0 | ACKNOWLEDGE ALARM | Acknowledge alarm | Needs production review | Needs native review | Acknowledgement does not close the alarm | Quality + MES / blocked |
| P0 | CONFIRM NG AND SEND TO REPAIR | Confirm NG and send to repair | Needs production review | Needs native review | Creates/activates repair handoff; no station skip | Quality + Repair / blocked |
| P0 | REPAIR RETURN | Receive repaired unit | Needs production review | Needs native review | Receiving is distinct from repair completion | Repair + MES / blocked |
| P0 | REPAIR CLOSED LOOP | Repair closed loop | Needs production review | Needs native review | Must show owner, elapsed time and final disposition | Quality + MES / blocked |
| P0 | PALLET BINDING | Pallet binding | Needs production review | Needs native review | Do not translate as case binding | Packaging / blocked |
| P0 | CASE / OUTER-BOX BINDING | Outer-box binding | Needs production review | Needs native review | Do not translate as pallet binding | Packaging / blocked |
| P0 | CONFIRM RETEST | Confirm retest | Needs production review | Needs native review | Authorization-gated; keep separate from alarm acknowledge | Quality / blocked |
| P1 | Scanner | Scanner input | Needs production review | Needs native review | Scanner field remains primary focus target | Production / blocked |
| P1 | ATE | ATE | Approved abbreviation | Needs native review | Speak as A–T–E | Engineering / partial |
| P1 | AOI | AOI | Approved abbreviation | Needs native review | Speak as A–O–I | Engineering / partial |
| P1 | Historical alarm | Historical alarm | Needs production review | Needs native review | Silent; never triggers new-event cue | Quality / blocked |
| P1 | Offline queue | Offline queue | Needs production review | Needs native review | Must not imply MES acceptance | MES / blocked |

## Release gate

- Never replace uncertain labels automatically.
- Record approver, approval date and exact approved wording for all three languages.
- Verify the approved text at 1366×768 and at 125% Windows scaling.
- Re-run station smoke tests for scanner focus, button overlap, alarm lifecycle and repair workflow after language updates.
