# -*- coding: utf-8 -*-
"""Open the fixed read-only station API port ranges for MES access."""
import subprocess

RULES = [("RJ Manual Station Local Info API", 12001, 12013), ("RJ Auto Station Local Info API", 12101, 12113)]
for name, first, last in RULES:
    command = ["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}", "dir=in", "action=allow", "protocol=TCP", f"localport={first}-{last}", "profile=Any"]
    result = subprocess.run(command, capture_output=True, text=True, encoding="mbcs", errors="replace")
    print(f"[{name}] exit={result.returncode} {result.stdout.strip() or result.stderr.strip()}")
