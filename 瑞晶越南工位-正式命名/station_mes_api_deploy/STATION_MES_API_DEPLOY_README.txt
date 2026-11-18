RJ Station MES SQLite API Deployment

This package exposes read-only SQLite information for all 26 stations.

Manual line ports: 12001-12013
Auto line ports:   12101-12113

Install:
1. Copy the package files beside the 004-手动线 and 002-自动线 folders.
2. Open PowerShell as Administrator.
3. Run:
   Set-ExecutionPolicy -Scope Process Bypass -Force
   .\start_all_station_apis.ps1
4. Start the normal manual/auto keepalive scripts if the station agents are not running.

Read-only endpoints on each station port:
  /health
  /api/station/local-info
  /api/station/scans
  /api/station/ng
  /api/station/test-results
  /api/station/resources
  /api/station/outbox
  /api/station/agent-messages
  /api/station/reports

The API rejects POST, PUT, PATCH and DELETE. MES can read local history but
cannot modify station SQLite evidence through this gateway.
