# Station Agent Runtime Bricks

Canonical implementation catalog: `../../station-component-reservoir/catalog.json`.

Contains identity, MES connection, heartbeat, scanner, language, authorization, product gate, result ingestion, alarm, repair, retest, scrap, maintenance and equipment adapters.

## Shared-service stations

- `RPR-001 quality.repair-workbench` — independent repair-station Agent: receive/activate repair order, diagnose, record action/parts, send to retest, return to route or scrap, and close.
- `IQC-001 quality.incoming-inspection` — incoming-material inspection workstation: receipt/lot, sampling plan, inspection result, documents, NCR, disposition and stock release/hold.
