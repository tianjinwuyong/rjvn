# -*- coding: utf-8 -*-
"""
SSH Enable Tool - GUI to enable SSH on factory stations
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import socket
from concurrent.futures import ThreadPoolExecutor

class SSHEnableTool:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH Enable Tool - Factory Stations")
        self.root.geometry("800x600")

        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.accent = "#0e639c"
        self.success = "#4ec9b0"
        self.error = "#f14c4c"
        self.warning = "#cca700"

        self.root.configure(bg=self.bg_color)

        self.stations = [
            ("AOI(手动)", "192.168.6.90", "Administrator"),
            ("AOI(自动)", "192.168.6.50", "Administrator"),
            ("ICT(自动)", "192.168.6.51", "Admin"),
            ("FCT(自动)", "192.168.6.52", "Administrator"),
            ("分板机(自动)", "192.168.6.53", "Administrator"),
            ("激光打标", "192.168.6.54", "Administrator"),
            ("组装ATE(自动)", "192.168.6.55", "Administrator"),
            ("自动超声波", "192.168.6.56", "Administrator"),
            ("创华老化", "192.168.6.57", "Administrator"),
            ("高压测试(自动)", "192.168.6.58", "Administrator"),
            ("包装ATE左边", "192.168.6.59", "Administrator"),
            ("包装ATE右边", "192.168.6.60", "Administrator"),
            ("FCT(手动)", "192.168.6.92", "Administrator"),
            ("分板机(手动)", "192.168.6.93", "Administrator"),
            ("绑码(手动)", "192.168.6.94", "Administrator"),
            ("组装ATE(手动)", "192.168.6.95", "Administrator"),
            ("超声波(手动)", "192.168.6.96", "Administrator"),
            ("老化(手动)", "192.168.6.97", "Administrator"),
            ("高压测试(手动)", "192.168.6.98", "Administrator"),
            ("包装ATE(手动)", "192.168.6.99", "Administrator"),
            ("包装(手动)", "192.168.6.100", "Administrator"),
        ]

        self.setup_ui()

    def setup_ui(self):
        # Title
        title = tk.Frame(self.root, bg=self.bg_color)
        title.pack(fill="x", padx=20, pady=10)

        tk.Label(title, text="SSH Enable Tool", font=("Segoe UI", 18, "bold"),
                fg=self.success, bg=self.bg_color).pack(side="left")
        tk.Label(title, text="v1.0", font=("Segoe UI", 10),
                fg=self.fg_color, bg=self.bg_color).pack(side="right")

        # Credentials frame
        cred_frame = tk.LabelFrame(self.root, text=" Credentials ", font=("Segoe UI", 11),
                                   fg=self.fg_color, bg=self.bg_color, padx=10, pady=5)
        cred_frame.pack(fill="x", padx=20, pady=(0, 10))

        tk.Label(cred_frame, text="Password:", fg=self.fg_color, bg=self.bg_color).grid(row=0, column=0, sticky="w")
        self.password_var = tk.StringVar(value="rj")
        tk.Entry(cred_frame, textvariable=self.password_var, width=30, show="*").grid(row=0, column=1, padx=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg=self.bg_color)
        btn_frame.pack(fill="x", padx=20, pady=5)

        tk.Button(btn_frame, text="Scan All", command=self.scan_all,
                 bg=self.accent, fg="white", width=15, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Enable SSH Selected", command=self.enable_selected,
                 bg=self.success, fg="black", width=15, cursor="hand2").pack(side="left", padx=5)
        tk.Button(btn_frame, text="Enable SSH All", command=self.enable_all,
                 bg="#4a4a4a", fg="white", width=15, cursor="hand2").pack(side="left", padx=5)

        # Station list
        list_frame = tk.Frame(self.root, bg=self.bg_color)
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        # Headers
        headers = tk.Frame(list_frame, bg="#2d2d2d")
        headers.pack(fill="x")
        tk.Label(headers, text="", bg="#2d2d2d", width=5).grid(row=0, column=0)
        tk.Label(headers, text="Station", bg="#2d2d2d", fg="white", width=20, anchor="w").grid(row=0, column=1)
        tk.Label(headers, text="IP", bg="#2d2d2d", fg="white", width=15).grid(row=0, column=2)
        tk.Label(headers, text="Status", bg="#2d2d2d", fg="white", width=15).grid(row=0, column=3)
        tk.Label(headers, text="SSH Port", bg="#2d2d2d", fg="white", width=10).grid(row=0, column=4)

        # Canvas for scrollable list
        canvas = tk.Canvas(list_frame, bg=self.bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.list_frame = tk.Frame(canvas, bg=self.bg_color)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.window_id = canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self.window_id, width=e.width))

        self.checkbuttons = []
        self.status_labels = {}
        self.port_labels = {}

        for i, (name, ip, user) in enumerate(self.stations):
            row = tk.Frame(self.list_frame, bg=self.bg_color)
            row.pack(fill="x", pady=1)

            var = tk.BooleanVar(value=True)
            cb = tk.Checkbutton(row, variable=var, bg=self.bg_color, fg=self.fg_color,
                               selectcolor="#2d2d2d", activebackground=self.bg_color)
            cb.grid(row=0, column=0, padx=5)

            tk.Label(row, text=name, bg=self.bg_color, fg=self.fg_color, width=20, anchor="w").grid(row=0, column=1)
            tk.Label(row, text=ip, bg=self.bg_color, fg=self.fg_color, width=15).grid(row=0, column=2)

            status_label = tk.Label(row, text="Unknown", bg=self.bg_color, fg=self.warning, width=15)
            status_label.grid(row=0, column=3)
            self.status_labels[ip] = status_label

            port_label = tk.Label(row, text="-", bg=self.bg_color, fg=self.fg_color, width=10)
            port_label.grid(row=0, column=4)
            self.port_labels[ip] = port_label

            self.checkbuttons.append((var, ip, user))

        # Log
        log_frame = tk.LabelFrame(self.root, text=" Log ", font=("Segoe UI", 11),
                                  fg=self.fg_color, bg=self.bg_color)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(10, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, font=("Consolas", 9),
                                                  bg="#0d0d0d", fg="#87ceeb", state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def check_port(self, ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            r = sock.connect_ex((ip, 22))
            sock.close()
            return r == 0
        except:
            return False

    def scan_all(self):
        self.log("[INFO] Scanning all stations...")
        for name, ip, user in self.stations:
            open = self.check_port(ip)
            self.root.after(0, lambda ip=ip, open=open: self._update_status(ip, open))

        self.log("[INFO] Scan complete!")

    def _update_status(self, ip, port_open):
        if port_open:
            self.status_labels[ip].config(text="OPEN", fg=self.success)
            self.port_labels[ip].config(text="22", fg=self.success)
        else:
            self.status_labels[ip].config(text="CLOSED", fg=self.error)
            self.port_labels[ip].config(text="-", fg=self.error)

    def enable_ssh_remote(self, ip, user, password):
        """Try to enable SSH via remote command"""
        script = '''
        $ErrorActionPreference = "Stop"
        try {
            # Install OpenSSH if not present
            $ssh = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
            if (-not $ssh) {
                Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" -ErrorAction Stop
            }
            # Start and enable service
            Start-Service sshd -ErrorAction SilentlyContinue
            Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
            # Enable firewall
            Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
            Write-Output "SUCCESS"
        } catch {
            Write-Output "FAILED: $($_.Exception.Message)"
        }
        '''

        try:
            result = subprocess.run([
                "powershell", "-NoProfile", "-Command",
                f'$cred = New-Object System.Management.Automation.PSCredential ("{user}", (ConvertTo-SecureString "{password}" -AsPlainText -Force)); Invoke-Command -ComputerName {ip} -Credential $cred -ScriptBlock {{ {script} }}'
            ], capture_output=True, text=True, timeout=60)

            if "SUCCESS" in result.stdout:
                return "SUCCESS"
            return f"FAILED: {result.stdout[:100]}"
        except Exception as e:
            return f"ERROR: {str(e)[:50]}"

    def enable_all(self):
        self.log("[INFO] Enabling SSH on all stations...")
        password = self.password_var.get()

        for var, ip, user in self.checkbuttons:
            if var.get():
                self.log(f"[INFO] Enabling SSH on {ip}...")
                result = self.enable_ssh_remote(ip, user, password)
                self.log(f"[RESULT] {ip}: {result}")
                if "SUCCESS" in result:
                    self.status_labels[ip].config(text="ENABLED", fg=self.success)
                    self.port_labels[ip].config(text="22", fg=self.success)
                else:
                    self.status_labels[ip].config(text="FAILED", fg=self.error)
            else:
                self.log(f"[SKIP] {ip}: disabled by user")

        self.log("[INFO] Done!")

    def enable_selected(self):
        self.log("[INFO] Enabling SSH on selected stations...")
        password = self.password_var.get()

        for var, ip, user in self.checkbuttons:
            if var.get():
                self.log(f"[INFO] Enabling SSH on {ip}...")
                result = self.enable_ssh_remote(ip, user, password)
                self.log(f"[RESULT] {ip}: {result}")
                if "SUCCESS" in result:
                    self.status_labels[ip].config(text="ENABLED", fg=self.success)
                    self.port_labels[ip].config(text="22", fg=self.success)
                else:
                    self.status_labels[ip].config(text="FAILED", fg=self.error)

        self.log("[INFO] Done!")

if __name__ == "__main__":
    root = tk.Tk()
    app = SSHEnableTool(root)
    root.mainloop()
