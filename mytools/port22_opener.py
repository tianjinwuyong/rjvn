# -*- coding: utf-8 -*-
"""
Port 22 Opener - Open SSH port on all factory stations
Merges: local admin + SSH + WinRM into one UI
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import socket
import threading
import paramiko
import time
import os
import sys
from datetime import datetime

# =============================================================================
# Station Database (all 23 factory stations)
# =============================================================================
STATIONS = [
    # 手动线 (EPS18W)
    {"name": "波峰焊",       "ip": "192.168.1.10",  "user": "Admin",         "line": "手动线"},
    {"name": "AOI(手动)",    "ip": "192.168.6.90",  "user": "Admin",         "line": "手动线"},
    {"name": "ICT(手动)",    "ip": "192.168.6.91",  "user": "Admin",         "line": "手动线"},
    {"name": "FCT(手动)",    "ip": "192.168.6.92",  "user": "Administrator", "line": "手动线"},
    {"name": "分板机(手动)",  "ip": "192.168.6.93",  "user": "Administrator", "line": "手动线"},
    {"name": "绑码(手动)",    "ip": "192.168.6.94",  "user": "Administrator", "line": "手动线"},
    {"name": "组装ATE(手动)", "ip": "192.168.6.95",  "user": "Administrator", "line": "手动线"},
    {"name": "超声波(手动)",  "ip": "192.168.6.96",  "user": "Administrator", "line": "手动线"},
    {"name": "老化(手动)",    "ip": "192.168.6.97",  "user": "Administrator", "line": "手动线"},
    {"name": "高压测试(手动)", "ip": "192.168.6.98",  "user": "Administrator", "line": "手动线"},
    {"name": "包装ATE(手动)", "ip": "192.168.6.99",  "user": "Administrator", "line": "手动线"},
    {"name": "包装(手动)",    "ip": "192.168.6.100", "user": "Administrator", "line": "手动线"},
    # 自动线 (EPS48W)
    {"name": "AOI(自动)",    "ip": "192.168.6.50",  "user": "Admin",         "line": "自动线"},
    {"name": "ICT(自动)",    "ip": "192.168.6.51",  "user": "Admin",         "line": "自动线"},
    {"name": "FCT(自动)",    "ip": "192.168.6.52",  "user": "Administrator", "line": "自动线"},
    {"name": "分板机(自动)",  "ip": "192.168.6.53",  "user": "Administrator", "line": "自动线"},
    {"name": "激光打标",      "ip": "192.168.6.54",  "user": "Administrator", "line": "自动线"},
    {"name": "组装ATE(自动)", "ip": "192.168.6.55",  "user": "Administrator", "line": "自动线"},
    {"name": "自动超声波",    "ip": "192.168.6.56",  "user": "wy",            "line": "自动线"},
    {"name": "创华老化",      "ip": "192.168.6.57",  "user": "tianjinwuyong", "line": "自动线"},
    {"name": "高压测试(自动)", "ip": "192.168.6.58",  "user": "Administrator", "line": "自动线"},
    {"name": "包装ATE左",     "ip": "192.168.6.59",  "user": "Administrator", "line": "自动线"},
    {"name": "包装ATE右",     "ip": "192.168.6.60",  "user": "Administrator", "line": "自动线"},
]

# THIS PC
THIS_PC_IP = "192.168.6.56"

# =============================================================================
# PowerShell script to enable SSH + port 22 (run remotely)
# =============================================================================
ENABLE_SSH_SCRIPT = r"""
$ErrorActionPreference = "SilentlyContinue"
# Install OpenSSH if not installed
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
}
# Start and enable SSH service
Start-Service sshd
Set-Service sshd -StartupType Automatic
# Enable OpenSSH firewall rule
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
if ($rule) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
} else {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
# Extra explicit port 22 rule
$r2 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $r2) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
Write-Output "SUCCESS"
"""

LOCAL_ENABLE_SCRIPT = r"""
$ErrorActionPreference = "SilentlyContinue"
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
}
Start-Service sshd
Set-Service sshd -StartupType Automatic
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
if ($rule) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
} else {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server (sshd)" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
$r2 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $r2) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
Write-Output "LOCAL_SUCCESS"
"""


class Port22Opener:
    def __init__(self, root):
        self.root = root
        self.root.title("Port 22 Opener - Factory Stations")
        self.root.geometry("920x680")
        self.root.minsize(800, 600)

        # Colors
        self.bg = "#1e1e1e"
        self.fg = "#d4d4d4"
        self.accent = "#0e639c"
        self.success = "#4ec9b0"
        self.error = "#f14c4c"
        self.warning = "#cca700"
        self.info = "#87ceeb"

        self.root.configure(bg=self.bg)

        # Station state: {ip: {port_open: bool, status_text: str, status_color: str}}
        self.station_state = {}
        for s in STATIONS:
            self.station_state[s["ip"]] = {
                "port_open": False,
                "status_text": "Unknown",
                "status_color": self.warning,
            }

        self.setup_ui()

    # =========================================================================
    # UI Setup
    # =========================================================================
    def setup_ui(self):
        # -- Title --
        title_frame = tk.Frame(self.root, bg=self.bg)
        title_frame.pack(fill="x", padx=20, pady=(10, 5))

        tk.Label(title_frame, text="Port 22 Opener", font=("Segoe UI", 20, "bold"),
                 fg=self.success, bg=self.bg).pack(side="left")

        tk.Label(title_frame, text="v2.0", font=("Segoe UI", 10),
                 fg=self.fg, bg=self.bg).pack(side="right")

        # -- Credentials & Buttons bar --
        bar = tk.Frame(self.root, bg="#252526")
        bar.pack(fill="x", padx=15, pady=(0, 5))

        tk.Label(bar, text="Password:", fg=self.fg, bg="#252526",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 5))

        self.pw_var = tk.StringVar(value="rj")
        tk.Entry(bar, textvariable=self.pw_var, width=16, show="*",
                 bg="#3c3c3c", fg=self.fg, bd=0, font=("Consolas", 9),
                 insertbackground="white").pack(side="left", padx=(0, 15))

        # Admin status
        self.admin_label = tk.Label(bar, text="⛔ Not Admin", fg=self.error,
                                    bg="#252526", font=("Segoe UI", 9))
        self.admin_label.pack(side="left", padx=(0, 15))

        # Buttons
        btn_style = {"font": ("Segoe UI", 9), "height": 1, "cursor": "hand2", "bd": 0}

        tk.Button(bar, text="📡 Scan All", command=self.start_scan_all,
                  bg=self.accent, fg="white", width=14, **btn_style).pack(side="left", padx=3)
        tk.Button(bar, text="🔓 Open Checked", command=self.start_open_checked,
                  bg="#2d7d46", fg="white", width=14, **btn_style).pack(side="left", padx=3)
        tk.Button(bar, text="🔓 Open This PC", command=self.start_open_local,
                  bg="#0e639c", fg="white", width=14, **btn_style).pack(side="left", padx=3)
        tk.Button(bar, text="🔓 Open All", command=self.start_open_all,
                  bg="#4a4a4a", fg="white", width=14, **btn_style).pack(side="left", padx=3)

        # -- Station List (TreeView) --
        list_frame = tk.Frame(self.root, bg=self.bg)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Columns
        columns = ("check", "station", "ip", "user", "line", "port22", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                 height=14, selectmode="none")

        self.tree.heading("check", text="☑")
        self.tree.heading("station", text="Station")
        self.tree.heading("ip", text="IP")
        self.tree.heading("user", text="User")
        self.tree.heading("line", text="Line")
        self.tree.heading("port22", text="Port 22")
        self.tree.heading("status", text="Status")

        self.tree.column("check", width=35, anchor="center")
        self.tree.column("station", width=130)
        self.tree.column("ip", width=120)
        self.tree.column("user", width=100)
        self.tree.column("line", width=70)
        self.tree.column("port22", width=80, anchor="center")
        self.tree.column("status", width=140)

        # Style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#0d0d0d", foreground=self.fg,
                        fieldbackground="#0d0d0d", font=("Consolas", 9))
        style.configure("Treeview.Heading", background="#2d2d2d", foreground="white",
                        font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#2d2d2d")])

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Click on check column to toggle
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

        # Populate
        self.check_vars = {}  # ip -> BooleanVar
        self.populate_stations()

        # -- Console Log --
        log_frame = tk.LabelFrame(self.root, text=" Console ", font=("Segoe UI", 10),
                                  fg=self.fg, bg=self.bg, padx=5, pady=5)
        log_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10,
                                                   font=("Consolas", 9),
                                                   bg="#0d0d0d", fg=self.info,
                                                   insertbackground="white",
                                                   state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # Tags for colors
        self.log_text.tag_config("success", foreground=self.success)
        self.log_text.tag_config("error", foreground=self.error)
        self.log_text.tag_config("info", foreground=self.info)
        self.log_text.tag_config("warning", foreground=self.warning)

        # -- Status bar --
        self.status_bar = tk.Label(self.root, text=" Ready", bg="#007acc", fg="white",
                                   anchor="w", padx=10, font=("Segoe UI", 9))
        self.status_bar.pack(fill="x", side="bottom")

        # Check admin on start
        self.root.after(500, self.check_admin)

    def populate_stations(self):
        self.tree.delete(*self.tree.get_children())
        for s in STATIONS:
            ip = s["ip"]
            var = tk.BooleanVar(value=True)
            self.check_vars[ip] = var
            state = self.station_state[ip]
            port_text = "✅ OPEN" if state["port_open"] else "❌ Closed"
            port_fg = self.success if state["port_open"] else self.error
            self.tree.insert("", "end", iid=ip, values=(
                "☑", s["name"], s["ip"], s["user"], s["line"],
                port_text, state["status_text"]
            ))

    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item and col == "#1":  # check column
            var = self.check_vars.get(item)
            if var:
                var.set(not var.get())
                new_check = "☑" if var.get() else "☐"
                self.tree.set(item, column="check", value=new_check)

    def update_station_display(self, ip, port_open=None, status_text=None, status_color=None):
        if port_open is not None:
            self.station_state[ip]["port_open"] = port_open
            port_text = "✅ OPEN" if port_open else "❌ Closed"
            self.tree.set(ip, column="port22", value=port_text)
        if status_text is not None:
            self.station_state[ip]["status_text"] = status_text
            self.tree.set(ip, column="status", value=status_text)
        if status_color is not None:
            self.station_state[ip]["status_color"] = status_color

    # =========================================================================
    # Admin check
    # =========================================================================
    def check_admin(self):
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "[Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent() | ForEach-Object { $_.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }"],
                               capture_output=True, text=True, timeout=10)
            is_admin = r.stdout.strip() == "True"
            if is_admin:
                self.admin_label.config(text="✅ Admin", fg=self.success)
            else:
                self.admin_label.config(text="⛔ Not Admin", fg=self.error)
        except:
            self.admin_label.config(text="⚠ Check failed", fg=self.warning)

    # =========================================================================
    # Logging
    # =========================================================================
    def log(self, msg, tag=None):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}] ", "info")
        self.log_text.insert("end", msg + "\n", tag or "info")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update()

    def set_status(self, msg):
        self.status_bar.config(text=f" {msg}")
        self.root.update()

    # =========================================================================
    # Port scanning
    # =========================================================================
    def check_port(self, ip, timeout=1.5):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            r = sock.connect_ex((ip, 22))
            sock.close()
            return r == 0
        except:
            return False

    def start_scan_all(self):
        threading.Thread(target=self.scan_all, daemon=True).start()

    def scan_all(self):
        self.log("Scanning port 22 on all stations...", "info")
        self.set_status("Scanning all stations...")

        for s in STATIONS:
            ip = s["ip"]
            self.update_station_display(ip, status_text="Scanning...", status_color=self.warning)
            self.root.update()
            port_open = self.check_port(ip)
            if port_open:
                self.update_station_display(ip, port_open=True, status_text="SSH Ready",
                                            status_color=self.success)
                self.log(f"  {s['name']:12s} {ip:15s} ✅ Port 22 OPEN", "success")
            else:
                self.update_station_display(ip, port_open=False, status_text="Closed",
                                            status_color=self.error)
                self.log(f"  {s['name']:12s} {ip:15s} ❌ Closed", "error")

        open_count = sum(1 for ip in self.station_state if self.station_state[ip]["port_open"])
        self.log(f"Scan complete: {open_count}/23 open", "info")
        self.set_status(f"Scan done: {open_count}/23 open")

    # =========================================================================
    # THIS PC - enable port 22 locally
    # =========================================================================
    def start_open_local(self):
        threading.Thread(target=self.open_local, daemon=True).start()

    def open_local(self):
        self.log("=" * 50, "info")
        self.log("Opening port 22 on THIS PC (192.168.6.56)...", "info")
        self.set_status("Enabling SSH on this PC...")

        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", LOCAL_ENABLE_SCRIPT],
                               capture_output=True, text=True, timeout=120)
            output = r.stdout + r.stderr
            if "LOCAL_SUCCESS" in output:
                self.log("✅ SSH + Port 22 enabled on THIS PC!", "success")
                self.update_station_display(THIS_PC_IP, status_text="✅ Enabled",
                                            status_color=self.success)
                # Re-scan
                port_open = self.check_port(THIS_PC_IP)
                self.update_station_display(THIS_PC_IP, port_open=port_open)
            else:
                self.log(f"❌ Failed: {output[:200]}", "error")
                self.update_station_display(THIS_PC_IP, status_text="Failed",
                                            status_color=self.error)
        except Exception as e:
            self.log(f"❌ Error: {e}", "error")
            self.update_station_display(THIS_PC_IP, status_text="Error", status_color=self.error)

        self.set_status("This PC done")
        self.log("=" * 50, "info")

    # =========================================================================
    # Open via SSH on stations that already have SSH running
    # =========================================================================
    def enable_via_ssh(self, station, password):
        """SSH into a station with open port 22 and enable firewall + SSH"""
        name = station["name"]
        ip = station["ip"]
        user = station["user"]

        self.log(f"  SSH to {name} ({ip}) as {user}...", "info")
        self.update_station_display(ip, status_text="SSH'ing...", status_color=self.warning)
        self.root.update()

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(ip, username=user, password=password, timeout=10)

            # Run the enable script
            cmd = f'powershell -NoProfile -Command "{ENABLE_SSH_SCRIPT}"'
            stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="replace")
            error = stderr.read().decode("utf-8", errors="replace")

            client.close()

            if "SUCCESS" in output or exit_code == 0:
                self.log(f"  ✅ {name} - Port 22 enabled via SSH!", "success")
                self.update_station_display(ip, status_text="✅ Enabled", status_color=self.success)
                # Re-scan
                port_open = self.check_port(ip)
                self.update_station_display(ip, port_open=port_open)
                return True
            else:
                self.log(f"  ❌ {name} - SSH command failed: {output[:100]} {error[:100]}", "error")
                self.update_station_display(ip, status_text="Failed", status_color=self.error)
                return False

        except paramiko.AuthenticationException:
            self.log(f"  ❌ {name} - SSH auth failed (wrong password?)", "error")
            self.update_station_display(ip, status_text="Auth failed", status_color=self.error)
            return False
        except paramiko.SSHException as e:
            self.log(f"  ❌ {name} - SSH error: {e}", "error")
            self.update_station_display(ip, status_text="SSH error", status_color=self.error)
            return False
        except socket.timeout:
            self.log(f"  ❌ {name} - Connection timeout", "error")
            self.update_station_display(ip, status_text="Timeout", status_color=self.error)
            return False
        except Exception as e:
            self.log(f"  ❌ {name} - {e}", "error")
            self.update_station_display(ip, status_text="Error", status_color=self.error)
            return False

    # =========================================================================
    # Open via WinRM (PowerShell Remoting)
    # =========================================================================
    def enable_via_winrm(self, station, password):
        """Try to enable SSH via WinRM/PowerShell Remoting"""
        name = station["name"]
        ip = station["ip"]
        user = station["user"]

        self.log(f"  WinRM to {name} ({ip}) as {user}...", "info")
        self.update_station_display(ip, status_text="WinRM...", status_color=self.warning)
        self.root.update()

        ps_cmd = (
            f'$sec = ConvertTo-SecureString "{password}" -AsPlainText -Force; '
            f'$cred = New-Object System.Management.Automation.PSCredential ("{user}", $sec); '
            f'try {{ '
            f'  $s = New-PSSession -ComputerName {ip} -Credential $cred -ErrorAction Stop; '
            f'  Invoke-Command -Session $s -ScriptBlock {{ {ENABLE_SSH_SCRIPT} }}; '
            f'  Remove-PSSession $s; '
            f'  Write-Output "WINRM_OK" '
            f'}} catch {{ Write-Output "WINRM_FAIL: $($_.Exception.Message)" }}'
        )

        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                               capture_output=True, text=True, timeout=90)
            output = r.stdout + r.stderr

            if "WINRM_OK" in output or "SUCCESS" in output:
                self.log(f"  ✅ {name} - Port 22 enabled via WinRM!", "success")
                self.update_station_display(ip, status_text="✅ Enabled", status_color=self.success)
                port_open = self.check_port(ip)
                self.update_station_display(ip, port_open=port_open)
                return True
            else:
                self.log(f"  ⏭ {name} - WinRM failed: {output[:100]}", "warning")
                self.update_station_display(ip, status_text="WinRM fail", status_color=self.warning)
                return False

        except subprocess.TimeoutExpired:
            self.log(f"  ⏭ {name} - WinRM timeout", "warning")
            self.update_station_display(ip, status_text="Timeout", status_color=self.warning)
            return False
        except Exception as e:
            self.log(f"  ⏭ {name} - WinRM error: {e}", "warning")
            return False

    # =========================================================================
    # Open checked stations
    # =========================================================================
    def start_open_checked(self):
        checked = [s for s in STATIONS if self.check_vars.get(s["ip"], tk.BooleanVar(value=False)).get()]
        if not checked:
            messagebox.showinfo("No Selection", "No stations checked. Tick the boxes next to stations.")
            return
        threading.Thread(target=self.open_stations, args=(checked,), daemon=True).start()

    def start_open_all(self):
        threading.Thread(target=self.open_stations, args=(STATIONS,), daemon=True).start()

    def open_stations(self, stations_list):
        password = self.pw_var.get()
        if not password:
            messagebox.showerror("Error", "Please enter the password")
            return

        self.log("=" * 50, "info")
        self.log(f"Opening port 22 on {len(stations_list)} stations...", "info")
        self.set_status("Working...")

        results = {"success": 0, "failed": 0}

        for s in stations_list:
            ip = s["ip"]
            name = s["name"]

            # 1) THIS PC - do locally
            if ip == THIS_PC_IP:
                self.open_local()
                results["success"] += 1
                continue

            time.sleep(0.5)

            # 2) If port 22 already open → SSH in
            port_open = self.check_port(ip, timeout=2)
            if port_open:
                ok = self.enable_via_ssh(s, password)
                if ok:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                continue

            # 3) Try WinRM
            ok = self.enable_via_winrm(s, password)
            if ok:
                results["success"] += 1
            else:
                results["failed"] += 1
                self.log(f"  💡 {name} needs manual setup. Run on station:", "warning")
                self.log(f"     netsh advfirewall firewall add rule name=\"SSH Port 22\" dir=in action=allow protocol=TCP localport=22", "info")

            self.root.update()

        self.log("=" * 50, "info")
        self.log(f"Done: ✅ {results['success']}  ❌ {results['failed']}", "info")
        self.set_status(f"Done: {results['success']} success, {results['failed']} failed")


# =============================================================================
# Main
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    try:
        root.iconbitmap(default="")
    except:
        pass
    app = Port22Opener(root)
    root.mainloop()
