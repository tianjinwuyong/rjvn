import subprocess
import sys
from pathlib import Path


def main():
    root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    host = root / "station_local_info_api_host.exe"
    if not host.exists():
        raise SystemExit("Missing station_local_info_api_host.exe")
    for name, first, last in (("RJ Manual Station Local Info API", 12001, 12013),
                              ("RJ Auto Station Local Info API", 12101, 12113)):
        subprocess.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={name}",
                        "dir=in", "action=allow", "protocol=TCP", f"localport={first}-{last}",
                        "profile=Any"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    children = [subprocess.Popen([str(host), "--line-domain", domain], cwd=str(root),
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                for domain in ("MANUAL_LINE", "AUTO_LINE")]
    print("RJ Station MES APIs started")
    print("Manual ports: 12001-12013")
    print("Auto ports: 12101-12113")
    for child in children:
        child.wait()


if __name__ == "__main__":
    main()
