# Local Cognee memory tool

This tool is isolated from the SMT transactional database. PostgreSQL remains
authoritative. Only paths listed in `approved-sources.txt` may be ingested.

## Setup

```powershell
Copy-Item .env.example .env
# Add an approved LLM/embedding key to .env
.\.venv\Scripts\python.exe memory.py remember
.\.venv\Scripts\python.exe memory.py recall "What should we check for solder bridges?"
```

Never ingest employee files, payroll, credentials, customer-confidential data,
raw production exports, or photographs without a separate approval and
retention policy.
