# =============================================================================
# SSH Manager UI - Merged PowerShell GUI 
# Merges: SSHManagerUI + Factory SSH + SSH Enable Tool + Port 22 Scanner
# Run with: .\SSHManagerUI\ssh_manager_ui.ps1
# =============================================================================

#Requires -Version 5.0
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# =============================================================================
# Global Variables
# =============================================================================
$script:stations = @(
    # === 手动线 (EPS18W) ===
    @{ Name = "波峰焊";        IP = "192.168.1.10";  User = "";              Line = "手动线"; Desc = "Wave Soldering" }
    @{ Name = "AOI(手动)";     IP = "192.168.6.90";  User = "Admin";         Line = "手动线"; Desc = "AOI Inspection" }
    @{ Name = "ICT(手动)";     IP = "192.168.6.91";  User = "Admin";         Line = "手动线"; Desc = "ICT Test" }
    @{ Name = "FCT(手动)";     IP = "192.168.6.92";  User = "Administrator"; Line = "手动线"; Desc = "FCT Test" }
    @{ Name = "分板机(手动)";   IP = "192.168.6.93";  User = "Administrator"; Line = "手动线"; Desc = "Depanel Machine" }
    @{ Name = "绑码(手动)";     IP = "192.168.6.94";  User = "";              Line = "手动线"; Desc = "QR Code Binding" }
    @{ Name = "组装ATE(手动)";  IP = "192.168.6.95";  User = "Administrator"; Line = "手动线"; Desc = "Assembly ATE" }
    @{ Name = "超声波(手动)";   IP = "192.168.6.96";  User = "";              Line = "手动线"; Desc = "Ultrasonic" }
    @{ Name = "老化(手动)";     IP = "192.168.6.97";  User = "Administrator"; Line = "手动线"; Desc = "Aging" }
    @{ Name = "高压测试(手动)";  IP = "192.168.6.98";  User = "Administrator"; Line = "手动线"; Desc = "Hi-Pot Test" }
    @{ Name = "包装ATE(手动)";  IP = "192.168.6.99";  User = "Administrator"; Line = "手动线"; Desc = "Packaging ATE" }
    @{ Name = "包装(手动)";     IP = "192.168.6.100"; User = "Administrator"; Line = "手动线"; Desc = "Packaging" }
    # === 自动线 (EPS48W) ===
    @{ Name = "AOI(自动)";     IP = "192.168.6.50";  User = "Admin";         Line = "自动线"; Desc = "AOI Inspection" }
    @{ Name = "ICT(自动)";     IP = "192.168.6.51";  User = "Admin";         Line = "自动线"; Desc = "ICT Test" }
    @{ Name = "FCT(自动)";     IP = "192.168.6.52";  User = "Administrator"; Line = "自动线"; Desc = "FCT Test" }
    @{ Name = "分板机(自动)";   IP = "192.168.6.53";  User = "Administrator"; Line = "自动线"; Desc = "Depanel Machine" }
    @{ Name = "激光打标";       IP = "192.168.6.54";  User = "";              Line = "自动线"; Desc = "Laser Marking" }
    @{ Name = "组装ATE(自动)";  IP = "192.168.6.55";  User = "Administrator"; Line = "自动线"; Desc = "Assembly ATE" }
    @{ Name = "自动超声波";     IP = "192.168.6.56";  User = "wy";            Line = "自动线"; Desc = "Auto Ultrasonic (THIS PC)" }
    @{ Name = "创华老化";       IP = "192.168.6.57";  User = "tianjinwuyong"; Line = "自动线"; Desc = "Aging (Chuanghua)" }
    @{ Name = "高压测试(自动)";  IP = "192.168.6.58";  User = "Administrator"; Line = "自动线"; Desc = "Hi-Pot Test" }
    @{ Name = "包装ATE左";      IP = "192.168.6.59";  User = "Administrator"; Line = "自动线"; Desc = "Packaging ATE Left" }
    @{ Name = "包装ATE右";      IP = "192.168.6.60";  User = "Administrator"; Line = "自动线"; Desc = "Packaging ATE Right" }
)

# =============================================================================
# Color Constants
# =============================================================================
$BG_DARK     = "#1e1e1e"
$BG_PANEL    = "#252526"
$BG_INPUT    = "#3c3c3c"
$FG_DEFAULT  = "#d4d4d4"
$FG_LIGHT    = "#e0e0e0"
$ACCENT      = "#0e639c"
$ACCENT_HVR  = "#1177bb"
$SUCCESS     = "#4ec9b0"
$ERROR       = "#f14c4c"
$WARNING     = "#cca700"
$INFO        = "#87ceeb"
$BTN_START   = "#0e639c"
$BTN_STOP    = "#6a1b1a"
$BTN_RESTART = "#4a4a4a"
$BTN_SCAN    = "#0e639c"
$BTN_SSH     = "#2d7d46"
$STATUSBAR   = "#007acc"

# =============================================================================
# Form Creation
# =============================================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "SSH Manager UI - Factory Tools"
$form.Size = New-Object System.Drawing.Size(920, 680)
$form.MinimumSize = New-Object System.Drawing.Size(800, 600)
$form.StartPosition = "CenterScreen"
$form.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_DARK)
$form.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$form.Icon = [System.Drawing.Icon]::ExtractAssociatedIcon((Get-Command powershell).Source)

# Add ESC to close
$form.KeyPreview = $true
$form.Add_KeyDown({
    if ($_.KeyCode -eq "Escape") { $form.Close() }
})

# =============================================================================
# Menu Strip
# =============================================================================
$menuStrip = New-Object System.Windows.Forms.MenuStrip
$menuStrip.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#2d2d2d")
$menuStrip.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)

# File menu
$fileMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$fileMenu.Text = "  File  "
$fileMenu.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$exitItem = New-Object System.Windows.Forms.ToolStripMenuItem
$exitItem.Text = "Exit"
$exitItem.Add_Click({ $form.Close() })
$fileMenu.DropDownItems.Add($exitItem) | Out-Null

# Tools menu
$toolsMenu = New-Object System.Windows.Forms.ToolStripMenuItem
$toolsMenu.Text = "  Tools  "
$toolsMenu.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)

$refreshItem = New-Object System.Windows.Forms.ToolStripMenuItem
$refreshItem.Text = "Refresh All"
$refreshItem.Add_Click({ Refresh-AllStatus })
$toolsMenu.DropDownItems.Add($refreshItem) | Out-Null

$scanAllItem = New-Object System.Windows.Forms.ToolStripMenuItem
$scanAllItem.Text = "Scan All Ports 22"
$scanAllItem.Add_Click({ Start-ScanAllPorts })
$toolsMenu.DropDownItems.Add($scanAllItem) | Out-Null

$aboutItem = New-Object System.Windows.Forms.ToolStripMenuItem
$aboutItem.Text = "About"
$aboutItem.Add_Click({ Show-MsgBox "SSH Manager UI v2.0`nMerged PowerShell GUI for Factory SSH Management", "About" })
$toolsMenu.DropDownItems.Add($aboutItem) | Out-Null

$menuStrip.Items.Add($fileMenu) | Out-Null
$menuStrip.Items.Add($toolsMenu) | Out-Null
$form.Controls.Add($menuStrip)
$form.MainMenuStrip = $menuStrip

# =============================================================================
# Tab Control
# =============================================================================
$tabControl = New-Object System.Windows.Forms.TabControl
$tabControl.Dock = "Fill"
$tabControl.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_DARK)
$tabControl.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$tabControl.Padding = New-Object System.Drawing.Point(12, 4)
$tabControl.Font = New-Object System.Drawing.Font("Segoe UI", 9)

# ---- Tab 1: Local SSH Management ----
$tabLocal = New-Object System.Windows.Forms.TabPage
$tabLocal.Text = "  Local SSH  "
$tabLocal.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_DARK)
$tabLocal.Padding = New-Object System.Windows.Forms.Padding(10)

# Title
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "SSH Server Management"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 16, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
$lblTitle.Location = New-Object System.Drawing.Point(15, 10)
$lblTitle.Size = New-Object System.Drawing.Size(400, 35)
$tabLocal.Controls.Add($lblTitle)

# Status indicator (dot)
$lblStatusDot = New-Object System.Windows.Forms.Label
$lblStatusDot.Text = "●"
$lblStatusDot.Font = New-Object System.Drawing.Font("Segoe UI", 20)
$lblStatusDot.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($WARNING)
$lblStatusDot.Location = New-Object System.Drawing.Point(770, 12)
$lblStatusDot.Size = New-Object System.Drawing.Size(30, 30)
$lblStatusDot.TextAlign = "MiddleCenter"
$tabLocal.Controls.Add($lblStatusDot)

# Status box
$txtStatus = New-Object System.Windows.Forms.TextBox
$txtStatus.Multiline = $true
$txtStatus.ReadOnly = $true
$txtStatus.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0d0d0d")
$txtStatus.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$txtStatus.Font = New-Object System.Drawing.Font("Consolas", 9)
$txtStatus.Location = New-Object System.Drawing.Point(15, 50)
$txtStatus.Size = New-Object System.Drawing.Size(875, 200)
$txtStatus.ScrollBars = "Vertical"
$txtStatus.BorderStyle = "FixedSingle"
$tabLocal.Controls.Add($txtStatus)

# Buttons frame
$grpActions = New-Object System.Windows.Forms.GroupBox
$grpActions.Text = " Actions "
$grpActions.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$grpActions.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$grpActions.Location = New-Object System.Drawing.Point(15, 260)
$grpActions.Size = New-Object System.Drawing.Size(875, 60)
$grpActions.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_PANEL)
$tabLocal.Controls.Add($grpActions)

function New-DarkButton {
    param($Text, $X, $Bg, $Width = 120)
    $btn = New-Object System.Windows.Forms.Button
    $btn.Text = $Text
    $btn.Location = New-Object System.Drawing.Point($X, 20)
    $btn.Size = New-Object System.Drawing.Size($Width, 28)
    $btn.BackColor = [System.Drawing.ColorTranslator]::FromHtml($Bg)
    $btn.ForeColor = "White"
    $btn.FlatStyle = "Flat"
    $btn.FlatAppearance.BorderSize = 0
    $btn.Cursor = "Hand"
    $btn.Font = New-Object System.Drawing.Font("Segoe UI", 9)
    return $btn
}

$btnStart = New-DarkButton "▶ Start" 15 $BTN_START
$btnStop = New-DarkButton "■ Stop" 145 $BTN_STOP
$btnRestart = New-DarkButton "↻ Restart" 275 $BTN_RESTART
$btnRefresh = New-DarkButton "⟳ Refresh" 405 "#3c3c3c"
$btnOpenFW = New-DarkButton "🔥 Open Port 22" 535 $BTN_SCAN 130

$grpActions.Controls.AddRange(@($btnStart, $btnStop, $btnRestart, $btnRefresh, $btnOpenFW))

# Firewall status group
$grpFirewall = New-Object System.Windows.Forms.GroupBox
$grpFirewall.Text = " Port 22 Status "
$grpFirewall.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$grpFirewall.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$grpFirewall.Location = New-Object System.Drawing.Point(15, 330)
$grpFirewall.Size = New-Object System.Drawing.Size(875, 120)
$grpFirewall.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_PANEL)
$tabLocal.Controls.Add($grpFirewall)

$txtFirewall = New-Object System.Windows.Forms.TextBox
$txtFirewall.Multiline = $true
$txtFirewall.ReadOnly = $true
$txtFirewall.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0d0d0d")
$txtFirewall.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$txtFirewall.Font = New-Object System.Drawing.Font("Consolas", 9)
$txtFirewall.Location = New-Object System.Drawing.Point(10, 25)
$txtFirewall.Size = New-Object System.Drawing.Size(850, 85)
$txtFirewall.ScrollBars = "Vertical"
$txtFirewall.BorderStyle = "FixedSingle"
$grpFirewall.Controls.Add($txtFirewall)

# ---- Tab 2: Factory Station SSH ----
$tabStations = New-Object System.Windows.Forms.TabPage
$tabStations.Text = "  Factory Stations  "
$tabStations.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_DARK)
$tabStations.Padding = New-Object System.Windows.Forms.Padding(10)

# Top bar: filter + buttons
$topPanel = New-Object System.Windows.Forms.Panel
$topPanel.Location = New-Object System.Drawing.Point(0, 0)
$topPanel.Size = New-Object System.Drawing.Size(900, 45)
$topPanel.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_PANEL)
$tabStations.Controls.Add($topPanel)

$lblFilter = New-Object System.Windows.Forms.Label
$lblFilter.Text = "Filter:"
$lblFilter.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$lblFilter.Location = New-Object System.Drawing.Point(10, 12)
$lblFilter.Size = New-Object System.Drawing.Size(40, 20)
$topPanel.Controls.Add($lblFilter)

$txtFilter = New-Object System.Windows.Forms.TextBox
$txtFilter.Location = New-Object System.Drawing.Point(50, 10)
$txtFilter.Size = New-Object System.Drawing.Size(160, 22)
$txtFilter.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_INPUT)
$txtFilter.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$txtFilter.BorderStyle = "FixedSingle"
$topPanel.Controls.Add($txtFilter)

$btnFilter = New-DarkButton "🔍 Filter" 220 "#3c3c3c" 80
$btnFilter.Location = New-Object System.Drawing.Point(220, 8)
$btnFilter.Size = New-Object System.Drawing.Size(80, 26)
$topPanel.Controls.Add($btnFilter)

$btnScanPorts = New-DarkButton "📡 Scan Port 22" 310 $BTN_SCAN 120
$btnScanPorts.Location = New-Object System.Drawing.Point(310, 8)
$btnScanPorts.Size = New-Object System.Drawing.Size(120, 26)
$topPanel.Controls.Add($btnScanPorts)

$btnEnableAll = New-DarkButton "🛠 Enable SSH All" 440 $BTN_SCAN 130
$btnEnableAll.Location = New-Object System.Drawing.Point(440, 8)
$btnEnableAll.Size = New-Object System.Drawing.Size(130, 26)
$topPanel.Controls.Add($btnEnableAll)

$btnRefreshStations = New-DarkButton "⟳ Refresh" 580 "#3c3c3c" 80
$btnRefreshStations.Location = New-Object System.Drawing.Point(580, 8)
$btnRefreshStations.Size = New-Object System.Drawing.Size(80, 26)
$topPanel.Controls.Add($btnRefreshStations)

# Password field
$lblPW = New-Object System.Windows.Forms.Label
$lblPW.Text = "PW:"
$lblPW.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$lblPW.Location = New-Object System.Drawing.Point(680, 12)
$lblPW.Size = New-Object System.Drawing.Size(30, 20)
$topPanel.Controls.Add($lblPW)

$txtPassword = New-Object System.Windows.Forms.TextBox
$txtPassword.Text = "rj"
$txtPassword.Location = New-Object System.Drawing.Point(710, 10)
$txtPassword.Size = New-Object System.Drawing.Size(70, 22)
$txtPassword.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_INPUT)
$txtPassword.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$txtPassword.BorderStyle = "FixedSingle"
$txtPassword.PasswordChar = '*'
$topPanel.Controls.Add($txtPassword)

# Station ListView
$listStations = New-Object System.Windows.Forms.ListView
$listStations.Location = New-Object System.Drawing.Point(0, 45)
$listStations.Size = New-Object System.Drawing.Size(890, 280)
$listStations.View = "Details"
$listStations.FullRowSelect = $true
$listStations.GridLines = $true
$listStations.CheckBoxes = $true
$listStations.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0d0d0d")
$listStations.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$listStations.Font = New-Object System.Drawing.Font("Consolas", 9)
$listStations.HeaderStyle = "Nonclickable"
$listStations.BorderStyle = "FixedSingle"
$listStations.MultiSelect = $true

$listStations.Columns.Add("", 28)
$listStations.Columns.Add("Station", 130)
$listStations.Columns.Add("IP", 130)
$listStations.Columns.Add("User", 110)
$listStations.Columns.Add("Line", 80)
$listStations.Columns.Add("Port 22", 90)
$listStations.Columns.Add("Status", 130)

# Context menu for station ListView
$ctxMenu = New-Object System.Windows.Forms.ContextMenuStrip
$ctxSSH = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxSSH.Text = "SSH Connect"
$ctxSSH.Add_Click({ Connect-SelectedStation })
$ctxMenu.Items.Add($ctxSSH) | Out-Null

$ctxPing = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxPing.Text = "Ping Station"
$ctxPing.Add_Click({ Ping-SelectedStation })
$ctxMenu.Items.Add($ctxPing) | Out-Null

$ctxScan = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxScan.Text = "Scan Port 22"
$ctxScan.Add_Click({ Scan-SinglePort })
$ctxMenu.Items.Add($ctxScan) | Out-Null

$ctxOpenFWItem = New-Object System.Windows.Forms.ToolStripMenuItem
$ctxOpenFWItem.Text = "Open Port 22 (Firewall)"
$ctxOpenFWItem.Add_Click({ Open-RemotePort22 })
$ctxMenu.Items.Add($ctxOpenFWItem) | Out-Null

$listStations.ContextMenuStrip = $ctxMenu
$tabStations.Controls.Add($listStations)

# Double-click to SSH
$listStations.Add_DoubleClick({ Connect-SelectedStation })

# Console log at bottom
$grpConsole = New-Object System.Windows.Forms.GroupBox
$grpConsole.Text = " Console "
$grpConsole.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($FG_DEFAULT)
$grpConsole.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$grpConsole.Location = New-Object System.Drawing.Point(0, 330)
$grpConsole.Size = New-Object System.Drawing.Size(890, 280)
$grpConsole.BackColor = [System.Drawing.ColorTranslator]::FromHtml($BG_PANEL)
$tabStations.Controls.Add($grpConsole)

$txtConsole = New-Object System.Windows.Forms.TextBox
$txtConsole.Multiline = $true
$txtConsole.ReadOnly = $true
$txtConsole.BackColor = [System.Drawing.ColorTranslator]::FromHtml("#0d0d0d")
$txtConsole.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($INFO)
$txtConsole.Font = New-Object System.Drawing.Font("Consolas", 9)
$txtConsole.Location = New-Object System.Drawing.Point(10, 25)
$txtConsole.Size = New-Object System.Drawing.Size(870, 245)
$txtConsole.ScrollBars = "Vertical"
$txtConsole.BorderStyle = "FixedSingle"
$grpConsole.Controls.Add($txtConsole)

# =============================================================================
# Status Bar
# =============================================================================
$statusBar = New-Object System.Windows.Forms.StatusStrip
$statusBar.BackColor = [System.Drawing.ColorTranslator]::FromHtml($STATUSBAR)

$statusLabel = New-Object System.Windows.Forms.ToolStripStatusLabel
$statusLabel.Text = " Ready"
$statusLabel.ForeColor = "White"
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)

$statusBar.Items.Add($statusLabel) | Out-Null
$form.Controls.Add($statusBar)

# =============================================================================
# Tab Control add to form
# =============================================================================
$tabControl.Controls.AddRange(@($tabLocal, $tabStations))
$form.Controls.Add($tabControl)
$tabControl.Dock = "Fill"
# Adjust for menu strip
$tabControl.Top = $menuStrip.Height

# =============================================================================
# Helper Functions
# =============================================================================

function Write-Log {
    param([string]$Msg, [string]$Color = "info")
    $colorMap = @{
        "info"    = $INFO
        "success" = $SUCCESS
        "error"   = $ERROR
        "warning" = $WARNING
    }
    $hex = if ($colorMap.ContainsKey($Color)) { $colorMap[$Color] } else { $INFO }
    $line = "[$(Get-Date -Format HH:mm:ss)] $Msg`r`n"
    $txtConsole.AppendText($line)
    $txtConsole.SelectionStart = $txtConsole.Text.Length
    $txtConsole.ScrollToCaret()
    $statusLabel.Text = " $Msg"
    $form.Refresh()
}

function Show-MsgBox {
    param([string]$Text, [string]$Title = "")
    [System.Windows.Forms.MessageBox]::Show($Text, $Title)
}

function Run-PS {
    param([string]$Cmd)
    try {
        $result = powershell -NoProfile -Command $Cmd 2>&1
        return $result
    } catch {
        return "ERROR: $_"
    }
}

# =============================================================================
# TAB 1: Local SSH Functions
# =============================================================================

function Refresh-LocalSSHStatus {
    $txtStatus.Clear()
    
    # Get service status
    $svc = Get-Service -Name sshd -ErrorAction SilentlyContinue
    $statusText = "SSH Service: "
    if ($svc) {
        $s = $svc.Status.ToString().ToUpper()
        $statusText += $s
        $statusText += " | StartType: $($svc.StartType)"
        if ($svc.Status -eq 'Running') {
            $lblStatusDot.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
        } else {
            $lblStatusDot.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($ERROR)
        }
    } else {
        $statusText += "NOT INSTALLED"
        $lblStatusDot.ForeColor = [System.Drawing.ColorTranslator]::FromHtml($WARNING)
    }
    
    $txtStatus.AppendText("$statusText`r`n`r`n")
    
    # Port 22 listening
    $listening = Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        $txtStatus.AppendText("Port 22: LISTENING`r`n")
        $listening | ForEach-Object {
            $txtStatus.AppendText("  $($_.LocalAddress):22`r`n")
        }
    } else {
        $txtStatus.AppendText("Port 22: NOT LISTENING`r`n")
    }
    
    # Firewall rules
    $txtStatus.AppendText("`r`n--- Firewall Rules ---`r`n")
    $fwRules = Get-NetFirewallRule -DisplayGroup "OpenSSH Server*" -ErrorAction SilentlyContinue
    if ($fwRules) {
        $fwRules | ForEach-Object {
            $enabled = if ($_.Enabled -eq 'True') { "ENABLED" } else { "DISABLED" }
            $txtStatus.AppendText("  $($_.DisplayName): $enabled`r`n")
        }
    } else {
        # Check port 22 directly
        $port22 = Get-NetFirewallRule -ErrorAction SilentlyContinue | 
            Where-Object { $_.Profile -ne $null } |
            ForEach-Object {
                $f = $_
                $addrObj = $f | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
                if ($addrObj -and $addrObj.LocalPort -eq 22) {
                    $enabled = if ($f.Enabled -eq 'True') { "ENABLED" } else { "DISABLED" }
                    return "  $($f.DisplayName): $enabled"
                }
            }
        if ($port22) {
            $port22 | ForEach-Object { $txtStatus.AppendText("$_`r`n") }
        } else {
            $txtStatus.AppendText("  No firewall rules for port 22 found`r`n")
        }
    }
    
    # IP addresses
    $txtStatus.AppendText("`r`n--- IP Addresses ---`r`n")
    $ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }
    $ips | ForEach-Object {
        $txtStatus.AppendText("  $($_.IPAddress.PadRight(16)) $($_.InterfaceAlias)`r`n")
    }
    
    # SSH version
    $ver = ssh -V 2>&1
    if ($ver) {
        $txtStatus.AppendText("`r`n$ver`r`n")
    }
    
    $txtStatus.SelectionStart = 0
    $txtStatus.ScrollToCaret()
}

function Refresh-FirewallStatus {
    $txtFirewall.Clear()
    
    $txtFirewall.AppendText("Checking Windows Firewall rules for port 22...`r`n`r`n")
    $form.Refresh()
    
    # Check OpenSSH firewall rule
    $rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
    if ($rule) {
        $state = if ($rule.Enabled -eq 'True') { "✅ ENABLED" } else { "❌ DISABLED" }
        $txtFirewall.AppendText("OpenSSH-Server-In-TCP: $state`r`n")
    } else {
        $txtFirewall.AppendText("OpenSSH-Server-In-TCP: ❌ NOT FOUND`r`n")
    }
    
    # Check all port 22 rules
    $txtFirewall.AppendText("`r`nChecking all inbound rules with port 22...`r`n")
    $allRules = Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction SilentlyContinue |
        ForEach-Object {
            $r = $_
            $portFilter = $_ | Get-NetFirewallPortFilter -ErrorAction SilentlyContinue
            if ($portFilter -and $portFilter.LocalPort -eq 22) {
                return $r
            }
        }
    
    if ($allRules) {
        $allRules | ForEach-Object {
            $txtFirewall.AppendText("  ✅ $($_.DisplayName)`r`n")
        }
    } else {
        $txtFirewall.AppendText("  No enabled inbound rules for port 22`r`n`r`n")
        $txtFirewall.AppendText("➡ Click 'Open Port 22' to create the firewall rule`r`n")
    }
    
    # Also show listening status
    $listening = Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
    if ($listening) {
        $txtFirewall.AppendText("`r`nPort 22 is LISTENING on:`r`n")
        $listening | ForEach-Object {
            $txtFirewall.AppendText("  ✅ $($_.LocalAddress):22`r`n")
        }
    } else {
        $txtFirewall.AppendText("`r`nPort 22 is NOT listening (SSH service not running)`r`n")
    }
    
    $txtFirewall.SelectionStart = 0
    $txtFirewall.ScrollToCaret()
}

function Open-LocalPort22 {
    Write-Log "Opening port 22 in firewall..." "info"
    
    # Check if running as admin
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Log "Need Administrator privileges to open firewall port! Restart PowerShell as Admin." "error"
        Show-MsgBox "Please run PowerShell as Administrator to open port 22 in the firewall." "Admin Required"
        return
    }
    
    # Method 1: Use OpenSSH rule if available
    $rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
    if ($rule) {
        Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
        Write-Log "Enabled firewall rule: OpenSSH-Server-In-TCP" "success"
    } else {
        # Method 2: Create rule if OpenSSH rule doesn't exist
        New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" `
            -DisplayName "OpenSSH Server sshd" `
            -Description "Inbound rule for OpenSSH SSH Server" `
            -Direction Inbound -Protocol TCP -LocalPort 22 `
            -Action Allow -Profile Any -Enabled True -ErrorAction SilentlyContinue | Out-Null
        Write-Log "Created firewall rule: OpenSSH-Server-In-TCP (port 22)" "success"
    }
    
    # Ensure SSH service is running
    $svc = Get-Service -Name sshd -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Log "SSH server not installed. Use 'Start' button to install." "warning"
    } else {
        Start-Service sshd -ErrorAction SilentlyContinue
        Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
        Write-Log "SSH service started and set to Automatic" "success"
    }
    
    Start-Sleep 1
    Refresh-FirewallStatus
    Refresh-LocalSSHStatus
    Write-Log "Port 22 should now be open and accessible" "success"
}

# Button events for Tab 1
$btnStart.Add_Click({
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Log "Need Administrator to manage SSH service" "error"
        Show-MsgBox "Please run PowerShell as Administrator to manage SSH service." "Admin Required"
        return
    }
    Write-Log "Starting SSH server..." "info"
    $result = Run-PS "Start-Service sshd -ErrorAction SilentlyContinue; Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue; Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue; echo 'DONE'"
    Refresh-LocalSSHStatus
    Refresh-FirewallStatus
    Write-Log "SSH server started" "success"
})

$btnStop.Add_Click({
    Write-Log "Stopping SSH server..." "info"
    $result = Run-PS "Stop-Service sshd -Force -ErrorAction SilentlyContinue; echo 'DONE'"
    Refresh-LocalSSHStatus
    Refresh-FirewallStatus
    Write-Log "SSH server stopped" "warning"
})

$btnRestart.Add_Click({
    Write-Log "Restarting SSH server..." "info"
    $result = Run-PS "Restart-Service sshd -Force -ErrorAction SilentlyContinue; echo 'DONE'"
    Refresh-LocalSSHStatus
    Refresh-FirewallStatus
    Write-Log "SSH server restarted" "success"
})

$btnRefresh.Add_Click({
    Write-Log "Refreshing local SSH status..." "info"
    Refresh-LocalSSHStatus
    Refresh-FirewallStatus
    Write-Log "Refresh complete" "success"
})

$btnOpenFW.Add_Click({ Open-LocalPort22 })

# =============================================================================
# TAB 2: Station Functions
# =============================================================================

function Load-Stations {
    param([string]$Filter = "")
    
    $listStations.Items.Clear()
    $stations = $script:stations
    
    if ($Filter) {
        $stations = $stations | Where-Object {
            $_.Name -like "*$Filter*" -or $_.IP -like "*$Filter*" -or $_.Line -like "*$Filter*"
        }
    }
    
    foreach ($s in $stations) {
        $item = New-Object System.Windows.Forms.ListViewItem("")
        $item.SubItems.Add($s.Name)
        $item.SubItems.Add($s.IP)
        $item.SubItems.Add($s.User)
        $item.SubItems.Add($s.Line)
        $item.SubItems.Add("-")
        $item.SubItems.Add("Unknown")
        $item.Tag = $s
        $item.Checked = $true
        $listStations.Items.Add($item) | Out-Null
    }
    
    Write-Log "Loaded $($stations.Count) stations" "info"
}

function Test-Port22 {
    param([string]$IP)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($IP, 22, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(1500)
        if ($wait -and $client.Connected) {
            $client.EndConnect($async)
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Update-StationStatus {
    param([System.Windows.Forms.ListViewItem]$Item, [bool]$PortOpen)
    if ($PortOpen) {
        $Item.SubItems[5].Text = "✅ OPEN"
        $Item.SubItems[5].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
        $Item.SubItems[6].Text = "SSH Ready"
        $Item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
    } else {
        $Item.SubItems[5].Text = "❌ Closed"
        $Item.SubItems[5].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($ERROR)
        $Item.SubItems[6].Text = "Not reachable"
        $Item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($ERROR)
    }
}

function Start-ScanAllPorts {
    Write-Log "Scanning port 22 on all stations..." "info"
    $total = $listStations.Items.Count
    $count = 0
    
    foreach ($item in $listStations.Items) {
        $s = $item.Tag
        $open = Test-Port22 -IP $s.IP
        Update-StationStatus -Item $item -PortOpen $open
        $count++
        $statusLabel.Text = " Scanning: $count/$total - $($s.IP)"
        $form.Refresh()
        Start-Sleep -Milliseconds 50
    }
    
    $openCount = @($listStations.Items | Where-Object { $_.SubItems[5].Text -eq "✅ OPEN" }).Count
    Write-Log "Scan complete: $openCount/$total stations have port 22 open" "success"
}

function Connect-SelectedStation {
    if ($listStations.SelectedItems.Count -eq 0) { return }
    $item = $listStations.SelectedItems[0]
    $s = $item.Tag
    
    $user = $s.User
    if (-not $user) { $user = $env:USERNAME }
    
    Write-Log "Connecting to $($s.Name) ($($s.IP)) as $user..." "info"
    
    # Start SSH in a new window
    $sshCmd = "ssh $user@$($s.IP)"
    if (-not $s.User) {
        $sshCmd = "ssh $($s.IP)"
    }
    
    try {
        Start-Process powershell -ArgumentList "-NoExit", "-Command", $sshCmd
        Write-Log "SSH session launched for $($s.Name)" "success"
    } catch {
        Write-Log "Failed to launch SSH: $_" "error"
    }
}

function Ping-SelectedStation {
    if ($listStations.SelectedItems.Count -eq 0) { return }
    $item = $listStations.SelectedItems[0]
    $s = $item.Tag
    
    Write-Log "Pinging $($s.IP)..." "info"
    $result = ping -n 2 $s.IP
    if ($LASTEXITCODE -eq 0) {
        Write-Log "$($s.Name) is reachable" "success"
        $item.SubItems[6].Text = "Online"
        $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
    } else {
        Write-Log "$($s.Name) is NOT reachable" "error"
        $item.SubItems[6].Text = "Offline"
        $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($ERROR)
    }
}

function Scan-SinglePort {
    if ($listStations.SelectedItems.Count -eq 0) { return }
    $item = $listStations.SelectedItems[0]
    $s = $item.Tag
    
    Write-Log "Scanning port 22 on $($s.Name) ($($s.IP))..." "info"
    $open = Test-Port22 -IP $s.IP
    Update-StationStatus -Item $item -PortOpen $open
    if ($open) {
        Write-Log "Port 22 OPEN on $($s.Name)" "success"
    } else {
        Write-Log "Port 22 CLOSED on $($s.Name)" "error"
    }
}

function Open-RemotePort22 {
    if ($listStations.SelectedItems.Count -eq 0) { return }
    $item = $listStations.SelectedItems[0]
    $s = $item.Tag
    
    $user = $s.User
    if (-not $user) { $user = "Administrator" }
    $password = $txtPassword.Text
    
    Write-Log "Attempting to open port 22 on $($s.Name) ($($s.IP))..." "info"
    Write-Log "Method: Remote PowerShell (requires WinRM enabled on target)" "warning"
    
    # Try via remote PowerShell
    try {
        $secPass = ConvertTo-SecureString $password -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential ("$user", $secPass)
        
        $session = New-PSSession -ComputerName $s.IP -Credential $cred -ErrorAction Stop -ErrorVariable psErr
        
        $result = Invoke-Command -Session $session -ScriptBlock {
            # Install OpenSSH if not installed
            $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
            if (-not ($cap.State -eq "Installed")) {
                Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" -ErrorAction SilentlyContinue
            }
            # Start and enable SSH service
            Start-Service sshd -ErrorAction SilentlyContinue
            Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
            # Enable port 22 in firewall
            $rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
            if ($rule) {
                Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
            } else {
                New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server sshd" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True -ErrorAction SilentlyContinue
            }
            return "SUCCESS"
        } -ErrorAction Stop
        
        Remove-PSSession $session
        
        if ($result -eq "SUCCESS") {
            Write-Log "✅ Port 22 opened on $($s.Name)! SSH should now be ready." "success"
            $item.SubItems[5].Text = "✅ OPEN"
            $item.SubItems[5].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
            $item.SubItems[6].Text = "SSH Ready"
            $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
        }
    } catch {
        Write-Log "Failed: $_" "error"
        Write-Log "WinRM may not be enabled on the target. Try manual setup:" "warning"
        Write-Log "  On $($s.Name): run 'Enable-NetFirewallRule -Name OpenSSH-Server-In-TCP'" "info"
    }
}

function EnableAll-Stations {
    $password = $txtPassword.Text
    $selectedItems = @($listStations.Items | Where-Object { $_.Checked })
    
    if ($selectedItems.Count -eq 0) {
        Write-Log "No stations selected (check the boxes)" "warning"
        return
    }
    
    Write-Log "=== Enabling SSH on $($selectedItems.Count) stations... ===" "info"
    $successCount = 0
    
    foreach ($item in $selectedItems) {
        $s = $item.Tag
        $user = $s.User
        if (-not $user) { $user = "Administrator" }
        
        Write-Log "Processing $($s.Name) ($($s.IP))..." "info"
        $item.SubItems[6].Text = "Enabling..."
        $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($WARNING)
        $form.Refresh()
        
        try {
            $secPass = ConvertTo-SecureString $password -AsPlainText -Force
            $cred = New-Object System.Management.Automation.PSCredential ("$user", $secPass)
            $session = New-PSSession -ComputerName $s.IP -Credential $cred -ErrorAction Stop
            
            $result = Invoke-Command -Session $session -ScriptBlock {
                $ErrorActionPreference = "SilentlyContinue"
                $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
                if (-not ($cap.State -eq "Installed")) {
                    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
                }
                Start-Service sshd
                Set-Service sshd -StartupType Automatic
                $rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
                if ($rule) { Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" }
                else {
                    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server sshd" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
                }
                return "SUCCESS"
            }
            
            Remove-PSSession $session
            
            if ($result -eq "SUCCESS") {
                Write-Log "✅ SSH enabled on $($s.Name)" "success"
                $item.SubItems[5].Text = "✅ OPEN"
                $item.SubItems[5].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
                $item.SubItems[6].Text = "SSH Ready"
                $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($SUCCESS)
                $successCount++
            }
        } catch {
            Write-Log "❌ Failed on $($s.Name): $_" "error"
            $item.SubItems[6].Text = "Failed"
            $item.SubItems[6].ForeColor = [System.Drawing.ColorTranslator]::FromHtml($ERROR)
        }
    }
    
    Write-Log "=== Enable complete: $successCount/$($selectedItems.Count) succeeded ===" "success"
}

# =============================================================================
# Wire up Tab 2 events
# =============================================================================

$btnFilter.Add_Click({
    Load-Stations -Filter $txtFilter.Text
})

$txtFilter.Add_KeyDown({
    if ($_.KeyCode -eq "Enter") {
        Load-Stations -Filter $txtFilter.Text
    }
})

$btnScanPorts.Add_Click({ Start-ScanAllPorts })
$btnEnableAll.Add_Click({ EnableAll-Stations })
$btnRefreshStations.Add_Click({ Load-Stations -Filter $txtFilter.Text })

# =============================================================================
# Auto-refresh timer
# =============================================================================
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 30000  # 30 seconds
$timer.Add_Tick({
    if ($tabControl.SelectedTab -eq $tabLocal) {
        Refresh-LocalSSHStatus
    }
})
$timer.Start()

# =============================================================================
# Form Load - Initialize
# =============================================================================
$form.Add_Shown({
    Refresh-LocalSSHStatus
    Refresh-FirewallStatus
    Load-Stations
    Write-Log "SSH Manager UI loaded. $($script:stations.Count) stations configured." "info"
    Write-Log "Select a station and double-click to SSH, or right-click for options." "info"
    Write-Log "---" "info"
})

# =============================================================================
# Keyboard shortcuts
# =============================================================================
$form.Add_KeyDown({
    if ($_.Control -and $_.KeyCode -eq "R") { 
        if ($tabControl.SelectedTab -eq $tabLocal) { Refresh-LocalSSHStatus; Refresh-FirewallStatus }
        elseif ($tabControl.SelectedTab -eq $tabStations) { Load-Stations }
    }
})

# =============================================================================
# Display Form
# =============================================================================
$form.ShowDialog() | Out-Null
