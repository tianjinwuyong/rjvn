# NG pickup announcement contract

When a repair station has a completed, authorized NG batch ready for collection, it emits exactly one `NG_PICKUP_ANNOUNCEMENT` envelope. The same event is delivered to:

1. the repair-station display;
2. the line-manager/team-leader PDA;
3. the MES Kanban and audit stream.

The envelope is bound to `domainCode`, `lineCode`, source/repair/destination stations, `workOrderId`, original `eventId`, bucket QR, the complete SN list, and quantity. MES assigns a stable `commandId` and owns the pickup state.

## Default MES announcement policy

The initial published policy is:

```json
{
  "policyVersion": "pickup-default-v1",
  "triggerMode": "ANY",
  "quantityThreshold": 10,
  "timeThresholdMinutes": 30,
  "humanButtonEnabled": true
}
```

An announcement is ready when **any one** condition is true: the bucket reaches 10 NG units, the oldest NG has waited 30 minutes, or an authorized operator presses the announce button. MES may publish a new version; Agents only read and execute the active version.

Pickup feedback is append-only and uses the same `commandId`: `RECEIVED`, `CLAIMED`, `COLLECTED`, `REJECTED`, or `BLOCKED`. A missing acknowledgement remains pending and can trigger Andon escalation. A rejected pickup must include a reason; the repair station cannot silently resend a different batch or alter the SN list.

The shared implementation is `quality.pickup-announcement` in the station component reservoir. It is used by the manual-line repair station runtime and is intended to be the single envelope for future PDA/MES adapters.
