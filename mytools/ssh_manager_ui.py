# =============================================================================
# SSH Manager UI - Graphical interface for SSH Server management
# Run with: python ssh_manager_ui.py
# Or build to exe with PyInstaller
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import sys
import os

class SSHManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SSH Manager UI")
        self.root.geometry("600x500")
        self.root.resizable(True, True)

        # Colors
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.accent_color = "#0e639c"
        self.success_color = "#4ec9b0"
        self.error_color = "#f14c4c"
        self.warning_color = "#cca700"

        self.root.configure(bg=self.bg_color)
        self.setup_ui()

        # Auto-refresh status on start
        self.root.after(500, self.refresh_status)

    def setup_ui(self):
        # Title
        title_frame = tk.Frame(self.root, bg=self.bg_color)
        title_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(
            title_frame,
            text="SSH Server Manager",
            font=("Segoe UI", 18, "bold"),
            fg=self.success_color,
            bg=self.bg_color
        ).pack(side="left")

        # Status indicator
        self.status_indicator = tk.Label(
            title_frame,
            text="●",
            font=("Segoe UI", 16),
            fg=self.warning_color,
            bg=self.bg_color
        )
        self.status_indicator.pack(side="right")

        # Main content frame
        content = tk.Frame(self.root, bg=self.bg_color)
        content.pack(fill="both", expand=True, padx=20, pady=10)

        # Status Section
        status_frame = tk.LabelFrame(
            content,
            text=" Status ",
            font=("Segoe UI", 11),
            fg=self.fg_color,
            bg=self.bg_color,
            bd=1
        )
        status_frame.pack(fill="x", pady=(0, 10))

        self.status_text = tk.Text(
            status_frame,
            height=8,
            font=("Consolas", 10),
            bg="#252526",
            fg=self.fg_color,
            bd=0,
            padx=10,
            pady=10,
            state="disabled"
        )
        self.status_text.pack(fill="x", padx=5, pady=5)

        # Buttons Frame
        btn_frame = tk.Frame(content, bg=self.bg_color)
        btn_frame.pack(fill="x", pady=10)

        btn_style = {
            "font": ("Segoe UI", 10),
            "width": 15,
            "height": 2,
            "cursor": "hand2"
        }

        self.start_btn = tk.Button(
            btn_frame,
            text="▶ Start",
            command=self.start_ssh,
            bg=self.accent_color,
            fg="white",
            activebackground="#1177bb",
            activeforeground="white",
            **btn_style
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = tk.Button(
            btn_frame,
            text="■ Stop",
            command=self.stop_ssh,
            bg="#6a1b1a",
            fg="white",
            activebackground="#8b2c2a",
            activeforeground="white",
            **btn_style
        )
        self.stop_btn.pack(side="left", padx=5)

        self.restart_btn = tk.Button(
            btn_frame,
            text="↻ Restart",
            command=self.restart_ssh,
            bg="#4a4a4a",
            fg="white",
            activebackground="#5a5a5a",
            activeforeground="white",
            **btn_style
        )
        self.restart_btn.pack(side="left", padx=5)

        self.refresh_btn = tk.Button(
            btn_frame,
            text="⟳ Refresh",
            command=self.refresh_status,
            bg="#3c3c3c",
            fg="white",
            activebackground="#4a4a4a",
            activeforeground="white",
            **btn_style
        )
        self.refresh_btn.pack(side="left", padx=5)

        # Log Section
        log_frame = tk.LabelFrame(
            content,
            text=" Console Log ",
            font=("Segoe UI", 11),
            fg=self.fg_color,
            bg=self.bg_color,
            bd=1
        )
        log_frame.pack(fill="both", expand=True, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            bg="#0d0d0d",
            fg="#87ceeb",
            bd=0,
            padx=10,
            pady=10,
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Info bar at bottom
        info_frame = tk.Frame(self.root, bg="#007acc")
        info_frame.pack(fill="x", side="bottom")

        self.info_label = tk.Label(
            info_frame,
            text="SSH Server Management Tool",
            font=("Segoe UI", 9),
            fg="white",
            bg="#007acc",
            anchor="w",
            padx=10
        )
        self.info_label.pack(fill="x")

    def run_powershell(self, cmd):
        """Run powershell command and return output"""
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout, result.stderr, result.returncode
        except Exception as e:
            return "", str(e), 1

    def log(self, msg, color=None):
        """Add message to log"""
        self.log_text.config(state="normal")
        if color:
            self.log_text.insert("end", msg + "\n", color)
        else:
            self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def log_tags_config(self):
        """Configure text tags for colors"""
        self.log_text.tag_config("success", foreground="#4ec9b0")
        self.log_text.tag_config("error", foreground="#f14c4c")
        self.log_text.tag_config("info", foreground="#87ceeb")
        self.log_text.tag_config("warning", foreground="#cca700")

    def get_ssh_status(self):
        """Get SSH service status"""
        stdout, _, rc = self.run_powershell("Get-Service -Name sshd -ErrorAction SilentlyContinue | Select-Object Status, StartType | ConvertTo-Json")
        return stdout

    def refresh_status(self):
        """Refresh status display"""
        self.status_text.config(state="normal")
        self.status_text.delete("1.0", "end")

        self.log("[INFO] Refreshing SSH status...", "info")

        # Get service status
        stdout, stderr, _ = self.run_powershell(
            "Get-Service -Name sshd -ErrorAction SilentlyContinue | "
            "Format-List Status, StartType, DisplayName | Out-String"
        )

        # Get listening ports
        ports_out, _, _ = self.run_powershell(
            "Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue | "
            "Select-Object LocalAddress, LocalPort | Format-Table -AutoSize | Out-String"
        )

        # Get firewall status
        fw_out, _, _ = self.run_powershell(
            "Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue | "
            "Select-Object Enabled | Format-List | Out-String"
        )

        # Get IP addresses
        ip_out, _, _ = self.run_powershell(
            "Get-NetIPAddress -AddressFamily IPv4 | "
            "Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | "
            "Select-Object IPAddress, InterfaceAlias | Format-Table -AutoSize | Out-String"
        )

        # Get SSH version
        ssh_ver, _, _ = self.run_powershell("(ssh -V 2>&1)")

        # Parse and display
        status = "Unknown"
        if "Running" in stdout:
            status = "RUNNING"
            self.status_indicator.config(fg=self.success_color)
        elif "Stopped" in stdout:
            status = "STOPPED"
            self.status_indicator.config(fg=self.error_color)
        else:
            self.status_indicator.config(fg=self.warning_color)

        self.status_text.insert("end", f"SSH Service Status: {status}\n\n")
        self.status_text.insert("end", f"{stdout}\n") if stdout else None
        self.status_text.insert("end", f"Listening Ports:\n{ports_out}\n") if ports_out.strip() else None
        self.status_text.insert("end", f"Firewall:\n{fw_out}\n") if fw_out.strip() else None
        self.status_text.insert("end", f"IP Addresses:\n{ip_out}\n") if ip_out.strip() else None
        self.status_text.insert("end", f"SSH Version: {ssh_ver.strip()}\n") if ssh_ver.strip() else None

        self.status_text.config(state="disabled")
        self.log_tags_config()

    def start_ssh(self):
        self.log("[ACTION] Starting SSH server...", "info")
        self.root.update()

        out, err, rc = self.run_powershell(
            "Start-Service sshd; Set-Service sshd -StartupType Automatic; "
            "Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue; "
            "'SUCCESS'"
        )

        if "SUCCESS" in out or rc == 0:
            self.log("[SUCCESS] SSH server started", "success")
            self.refresh_status()
        else:
            self.log(f"[ERROR] {err or out}", "error")

    def stop_ssh(self):
        self.log("[ACTION] Stopping SSH server...", "info")
        self.root.update()

        out, err, rc = self.run_powershell("Stop-Service sshd -Force; 'SUCCESS'")

        if "SUCCESS" in out or rc == 0:
            self.log("[SUCCESS] SSH server stopped", "warning")
            self.refresh_status()
        else:
            self.log(f"[ERROR] {err or out}", "error")

    def restart_ssh(self):
        self.log("[ACTION] Restarting SSH server...", "info")
        self.root.update()

        out, err, rc = self.run_powershell("Restart-Service sshd -Force; 'SUCCESS'")

        if "SUCCESS" in out or rc == 0:
            self.log("[SUCCESS] SSH server restarted", "success")
            self.refresh_status()
        else:
            self.log(f"[ERROR] {err or out}", "error")

def main():
    root = tk.Tk()

    # Set window icon (optional)
    try:
        root.iconbitmap(default="")
    except:
        pass

    app = SSHManagerUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
