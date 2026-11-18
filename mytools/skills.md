# 瑞晶工厂部署与运维技能

---

## Playwright 浏览器自动化测试

使用 Playwright MCP 进行浏览器自动化：页面验证、浏览、信息抓取、截图、功能测试。

### 可用 MCP Server: `playwright`

**工具** (通过 `skill_mcp(mcp_name="playwright", tool_name="...", arguments={...})` 调用):

| 工具 | 用途 |
|------|------|
| `browser_navigate` | 导航到 URL |
| `browser_snapshot` | 获取无障碍快照（比截图更适合功能 QA） |
| `browser_take_screenshot` | 页面截图 |
| `browser_console_messages` | 读取浏览器控制台错误/警告 |
| `browser_click` | 点击元素 |
| `browser_find` | 在无障碍树中搜索文本/正则 |
| `browser_wait_for` | 等待文本/元素或时间 |
| `browser_network_requests` | 列出网络请求 |
| `browser_evaluate` | 在页面上下文执行 JS |
| `browser_fill_form` | 填写表单字段 |
| `browser_type` | 向元素输入文本 |
| `browser_tabs` | 管理浏览器标签页 |
| `browser_select_option` | 选择下拉选项 |
| `browser_hover` | 悬停在元素上 |
| `browser_resize` | 调整浏览器窗口大小 |
| `browser_close` | 关闭页面 |
| `browser_handle_dialog` | 处理浏览器对话框 |
| `browser_file_upload` | 上传文件 |

### 快速开始

```typescript
// 导航并截图
skill_mcp({
  mcp_name: "playwright",
  tool_name: "browser_navigate",
  arguments: { url: "http://localhost:5178/#manual-line-3d" }
})

// 检查控制台错误
skill_mcp({
  mcp_name: "playwright",
  tool_name: "browser_console_messages",
  arguments: { level: "error", all: true }
})

// 截图
skill_mcp({
  mcp_name: "playwright",
  tool_name: "browser_take_screenshot",
  arguments: { type: "png", filename: "manual-line-check.png", scale: "css" }
})

// 无障碍快照（功能验证最佳）
skill_mcp({
  mcp_name: "playwright",
  tool_name: "browser_snapshot",
  arguments: { boxes: true }
})
```

### UI 验证工作流

1. **Navigate** → 打开页面
2. **Wait** → 等待页面稳定
3. **Console messages** → 检查控制台错误
4. **Snapshot** → 验证元素存在
5. **Screenshot** → 视觉记录

### 示例：验证 MES 3D 手动线渲染

```typescript
// 1. 导航
browser_navigate({ url: "http://localhost:5178/#manual-line-3d" })

// 2. 等待 3s 等待 3D 初始化
browser_wait_for({ time: 3 })

// 3. 检查控制台错误
browser_console_messages({ level: "error", all: true })

// 4. 截图
browser_take_screenshot({ type: "png", filename: "manual-line-3d.png", scale: "css" })
```

### 关键说明

- `browser_snapshot` 获取无障碍树 → 用于功能 QA 比截图更快、可验证文本
- `browser_console_messages` 配合 `all: true` 返回页面加载以来的所有控制台条目
- `scale: "css"` = 正常视口大小；`scale: "device"` = 高 DPI 截图
- 日志保存到工作区根目录的 `.playwright-mcp/` 目录

---

## 概述

手动线 (EPS18W) 11 台工位的统一部署、启动、监控体系。

**核心架构**：
```
代码共享: \\192.168.6.95\LineSupervisor$ (95 上的网络共享)
         → 所有工位挂载同一份代码 → 维护一份代码

部署路径: C:\LineSupervisor\  (Flask 线长看板)
          C:\Stations\         (工位 EXE)

远程管理: WinRM (PSRemoting)  port 5985
```

---

## 工具清单

### 1. `deploy_factory.ps1` — 统一部署脚本（主脚本）

**运行位置**: 95 (PowerShell Admin)

**功能**: 一步完成 — 创建共享 → 同步代码 → 部署 EXE → 创建启动脚本 → 设置计划任务 → 启动

```powershell
# 完整部署（第一次）
& "C:\Users\tianj\Desktop\越南工厂瑞晶\mytools\deploy_factory.ps1"

# 仅查看状态
.\deploy_factory.ps1 -StatusOnly

# 重启所有 Flask
.\deploy_factory.ps1 -RestartAll

# 持续监控（30秒轮询）
.\deploy_factory.ps1 -Monitor

# 仅重新部署 EXE（不改 Flask）
.\deploy_factory.ps1 -DeployOnly

# 仅启动（不重新部署）
.\deploy_factory.ps1 -StartOnly
```

**部署的工位清单**:
| Code | 工位 | IP | EXE |
|------|------|----|-----|
| 02-ICT | ICT | 192.168.6.91 | ICT_station.exe, apiserver_fwd_ict.exe |
| 03-FCT | FCT | 192.168.6.92 | FCT_station.exe |
| 04-分板机 | 分板机 | 192.168.6.93 | PCBADividerStation.exe |
| 05-绑码 | 绑码 | 192.168.6.94 | QRBinding_v2.exe |
| 06-激光打标 | 激光打标 | 192.168.6.95 | (Flask only) |
| 07-组装ATE | 组装ATE | 192.168.6.95 | AssemblyATE.exe, ScannerHelper_ATE.exe |
| 08-超声 | 超声 | 192.168.6.96 | UltrasonicStation.exe |
| 09-成品老化 | 成品老化 | 192.168.6.97 | AgingCab.exe |
| 10-高压测试 | 高压测试 | 192.168.6.98 | HiVoltATE.exe |
| 11-包装ATE | 包装ATE | 192.168.6.99 | PackingATE.exe |
| 12-包装 | 包装 | 192.168.6.100 | PackingStation.exe |

**代码更新流程**:
1. 更新 `C:\Users\tianj\Desktop\越南工厂瑞晶\线长看板系统\lineSupervisor.py`
2. 在 95 上重新运行 `deploy_factory.ps1`
3. 所有工位自动同步新代码

---

### 2. `winrm_full_setup.ps1` — WinRM 批量配置

**运行位置**: 95 (PowerShell Admin)

**功能**: 在所有工位上一键配置 WinRM（服务、防火墙、Basic认证、TrustedHosts）

```powershell
& "C:\Users\tianj\Desktop\越南工厂瑞晶\mytools\winrm_full_setup.ps1"
```

**注意**: 96, 97, 1.10 需要先手动 RDP 配置（见下方手动配置命令）

---

## 手动配置（96 / 97 / 1.10 专用）

 RDP 进去 → PowerShell Admin → 逐行运行：

```powershell
Set-Service WinRM -StartupType Automatic
Start-Service WinRM
Set-ItemProperty -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Service -Name auth_basic -Value 1
Set-ItemProperty -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WSMAN\Service -Name allow_unencrypted -Value 1
netsh advfirewall firewall add rule name="WinRM-HTTP-In" dir=in action=allow protocol=tcp localport=5985 profile=any
```

---

## 启动流程（早晨开机）

1. 工控机开机 → 计划任务自动执行 `launch_flask.ps1` → Flask 启动
2. 工控机开机 → 计划任务自动执行 `launch_stations.ps1` → 工位 EXE 启动

**无需手动操作。**

---

## 故障排查

**Flask 停了**:
```powershell
.\deploy_factory.ps1 -StatusOnly   # 先看哪个停了
.\deploy_factory.ps1 -RestartAll   # 重启所有
```

**WinRM 连不上**:
```powershell
# 在 95 上测试
Test-NetConnection <目标IP> -Port 5985
```

**手动重启单台**:
```powershell
# 找该工位 IP，RDP 进去
# 或从 95 PSRemote:
$ip = "192.168.6.99"
$s = New-PSSession $ip -Credential (New-Object PSCredential "Administrator", (ConvertTo-SecureString "rj" -AsPlainText -Force)) -Authentication Basic -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck)
# 杀 Flask
Invoke-Command -Session $s { Stop-Process -Name python -Force -ErrorAction SilentlyContinue }
# 启动
Invoke-Command -Session $s { Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\LineSupervisor\launch_flask.ps1" -WindowStyle Hidden }
```

---

## 文件路径速查

| 文件 | 本地路径 |
|------|----------|
| Flask 源码 | `C:\Users\tianj\Desktop\越南工厂瑞晶\线长看板系统\` |
| 工位 EXE 源码 | `C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\004-手动线\` |
| 部署脚本 | `C:\Users\tianj\Desktop\越南工厂瑞晶\mytools\deploy_factory.ps1` |
| 工位 IP 映射 | `C:\Users\tianj\Desktop\越南工厂瑞晶\工位IP映射.md` |

---

## 注意事项

- 95 有两个工位（激光打标 + 组装ATE），都部署在同一台 PC
- AOI (192.168.6.90) 是 Linux，跳板机，不在 WinRM 管理范围内
- 自动线 (EPS48W) 暂不涉及，专注手动线
- 所有工位 Windows 密码: `rj`

---

## 手动线工位 EXE 构建与部署

### 构建（本地开发机）

在开发机上用 Python 构建所有 10 个工位 .exe：

```powershell
python C:\Users\tianj\Desktop\越南工厂瑞晶\build_stations.py
```

**构建脚本**: `C:\Users\tianj\Desktop\越南工厂瑞晶\build_stations.py`

**输出目录**: `C:\Users\tianj\Desktop\越南工厂瑞晶\build_output\{StationName}\dist\`

**10 个工位对应的 EXE**:

| 工位 | EXE 文件名 |
|------|-----------|
| ICT | ICT_station.exe |
| FCT | FCT_station.exe |
| PCBA分板 | PCBADividerStation.exe |
| PCBA外壳绑码 | QRBinding_v2.exe |
| 组装ATE | AssemblyATE.exe |
| 超声 | UltrasonicStation.exe |
| 成品老化 | AgingCab.exe |
| 高压ATE | HiVoltATE.exe |
| 包装ATE | PackingATE.exe |
| 栈板绑码 | PackingStation.exe |

**构建参数**:
- PyInstaller + hidden imports: openpyxl, websockets, tkinter, asyncio, PIL, winreg 等
- 每个 EXE ~33-35 MB
- 构建后先本地测试，确认 `station.py` 逻辑正确再部署

### 部署到物理工位

部署到 `D:\Stations`（每台工位自己的 D 盘）：

```powershell
# 伪代码 — 用 WinRM 复制 + 重启
$stations = @(
    @{ip="192.168.6.91";  exe="ICT_station.exe"},
    @{ip="192.168.6.92";  exe="FCT_station.exe"},
    @{ip="192.168.6.93";  exe="PCBADividerStation.exe"},
    @{ip="192.168.6.94";  exe="QRBinding_v2.exe"},
    @{ip="192.168.6.95";  exe="AssemblyATE.exe"},
    @{ip="192.168.6.96";  exe="UltrasonicStation.exe"},
    @{ip="192.168.6.97";  exe="AgingCab.exe"},
    @{ip="192.168.6.98";  exe="HiVoltATE.exe"},
    @{ip="192.168.6.99";  exe="PackingATE.exe"},
    @{ip="192.168.6.100"; exe="PackingStation.exe"}
)
```

**注意**:
- 先用 `open-firewall-ports.ps1` 打开 WinRM 5985 才能远程部署
- `.91/.95/.97` 已有 WinRM；其余需先开防火墙
- 每台工位还要开放 `10080`(HTTP) 和 `1004`(WS) 端口
- Flask 已从所有工位删除（不再需要 `D:\Stations\Flask`）
- 工位运行的是 `station.py` 对应的 EXE，不是 Flask

### 工位源文件位置

| 工位 | 源文件 |
|------|--------|
| ICT | `004-手动线/(03)ICT/ICT station.py` |
| FCT | `004-手动线/(04)FCT/FCT station.py` |
| PCBA分板 | `004-手动线/(05)PCBA分板工位/组装ATE station.py` |
| PCBA外壳绑码 | `004-手动线/(06)PCBA外壳绑码/qrbinding.py` |
| 组装ATE | `004-手动线/(07)组装ATE/组装ATE station.py` |
| 超声 | `004-手动线/(08)超声/组装ATE station.py` |
| 成品老化 | `004-手动线/(09)成品老化/成品老化柜 station.py` |
| 高压ATE | `004-手动线/(10)高压ATE/高压ATE station.py` |
| 包装ATE | `004-手动线/(11)包装ATE/包装ATE station.py` |
| 栈板绑码 | `004-手动线/(13)栈板绑码/包装工位 station.py` |

> ⚠️ `组装ATE station.py` 被 3 个工位共用（PCBA分板/组装ATE/超声），但文件 MD5 不同、内容有差异，不能互换

---

## 工位 Sync API (端口 8089)

每个工位 EXE 内置 SyncHandler，MES 和 3D 看板通过此端口读取本地数据。

### 端点

| Method | Path | 返回 |
|--------|------|------|
| GET | `/health` | `{status: ok}` |
| GET | `/stats` | `{total, pass, fail, dup, date}` 从 SQLite |
| GET | `/pools` | `{sn_pool, ng_pool, dup_pool, counts}` 内存池 |
| GET | `/sn_records?limit=100` | 最近 N 条扫描记录 |
| GET | `/ng_pool` | NG 队列 |
| GET | `/dup_pool` | 重码池 |

### 认证

```
Header: X-Api-Key: VN-FACTORY-2024
Or:     ?key=VN-FACTORY-2024
```

默认 Key，可通过环境变量 `STATION_API_KEY` 覆盖。

### 架构

```
3D Dashboard → POST /api/mes/manual-line/station-stats
  → backend 代理到 http://192.168.1.x:8089/stats
    → station 读 SQLite → 返回 {total, pass, fail, dup}
```

### 端口说明

| 端口 | 用途 |
|------|------|
| 8089 | Sync API（MES/3D 读数据）|
| 1004 | WebSocket（扫码/NG 广播到本地 UI）|
| 10080 | Station HTTP API（start/stop/status，遗留）|

### 部署后测试

USB 部署完成后，在工位机器上测试：
```cmd
curl http://localhost:8089/health
curl -H "X-Api-Key: VN-FACTORY-2024" http://localhost:8089/stats
```

### 部署步骤

1. U盘拷贝 `C:\usb_deploy\Stations\*.exe` → `D:\Stations\`
2. 杀旧进程：`taskkill /F /IM ICT_station.exe`
3. 启新EXE：`D:\Stations\ICT_station.exe`
4. 新EXE启动时自动开 8089 端口防火墙
5. 验证：`curl http://localhost:8089/health`

### WinRM 远程管理（仅同网段可用）

```powershell
# 远程杀进程
Invoke-Command -ComputerName 192.168.6.91 -Credential $cred -ScriptBlock {
    Stop-Process -Name ICT_station -Force -ErrorAction SilentlyContinue
}

# 远程启动
Invoke-Command -ComputerName 192.168.6.91 -Credential $cred -ScriptBlock {
    Start-Process "D:\Stations\ICT_station.exe" -WorkingDirectory "D:\Stations" -WindowStyle Hidden
}
```

**跨网段（192.168.6.x → 192.168.1.x）**：SMB 和 WinRM 均不可达，必须 USB 部署。
