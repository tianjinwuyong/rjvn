# Factory Station SSH Credentials

## Overview
This document contains SSH credentials for all factory stations.

## Password
**Common password for all stations: `rj`**

---

## Manual Line (EPS18W) 手动线

| Station | IP | Username | Password |
|---------|-----|----------|----------|
| 波峰焊 | 192.168.1.10 | Administrator | rj |
| AOI | 192.168.6.90 | Administrator | rj |
| ICT | 192.168.6.91 | Admin | rj |
| FCT | 192.168.6.92 | Administrator | rj |
| 分板机 | 192.168.6.93 | Administrator | rj |
| 绑码 | 192.168.6.94 | Administrator | rj |
| 组装ATE | 192.168.6.95 | Administrator | rj |
| 超声波 | 192.168.6.96 | Administrator | rj |
| 安托森老化 | 192.168.6.97 | Administrator | rj |
| 高压测试仪 | 192.168.6.98 | Administrator | rj |
| 包装ATE | 192.168.6.99 | Administrator | rj |
| 包装 | 192.168.6.100 | Administrator | rj |

---

## Auto Line (EPS48W) 自动线

| Station | IP | Username | Password |
|---------|-----|----------|----------|
| 波峰焊 | (same subnet) | - | - |
| AOI | 192.168.6.50 | Administrator | rj |
| ICT | 192.168.6.51 | Admin | rj |
| FCT | 192.168.6.52 | Administrator | rj |
| 分板机 | 192.168.6.53 | Administrator | rj |
| 激光打标机 | 192.168.6.54 | Administrator | rj |
| 组装ATE | 192.168.6.55 | Administrator | rj |
| 自动超声波 | 192.168.6.56 | wy | rj |
| 创华老化 CH | 192.168.6.57 | tianjinwuyong | rj |
| 高压测试仪 | 192.168.6.58 | Administrator | rj |
| 包装ATE左边 | 192.168.6.59 | Administrator | rj |
| 包装ATE右边 | 192.168.6.60 | Administrator | rj |

---

## SSH Commands

### Connect to a station
```bash
ssh Administrator@192.168.6.90
ssh Admin@192.168.6.51
ssh wy@192.168.6.56
```

### With password (use sshpass)
```bash
sshpass -p rj ssh Administrator@192.168.6.90
```

### Copy SSH key to station (for passwordless login)
```bash
sshpass -p rj ssh-copy-id Administrator@192.168.6.90
```

---

## This PC (192.168.6.56)
- User: `wy`
- Password: `rj`
- SSH Server running on port 22

---

## Quick SSH Script Usage

From `factory_ssh.ps1`:
```powershell
.\factory_ssh.ps1 -Station "AOI手动"
.\factory_ssh.ps1 -Station "FCT自动"
```

---

## SMB 共享配置 (手工线工位)

### 脚本: `setup-smb-manual-line.ps1`

**用途：** 在手工线工位电脑上配置 SMB 文件共享，让 `.50` 服务器能读取 `ate_center.db`

**参数：**
| 参数 | 说明 | 示例 |
|------|------|------|
| `-StationNumber` | 工位编号 (91-100) | `92` |
| `-ShareName` | 共享名，默认 `ManualLine` | `ManualLine` |
| `-SMBUser` | SMB 用户名 | `Administrator` |
| `-SMBPass` | SMB 密码 | `rj` |

**使用前提：**
1. 在工位电脑上以 **管理员身份** 运行 PowerShell
2. 当前用户有 D盘 写权限

**在工位电脑上运行：**
```powershell
# 管理员 PowerShell
cd C:\Users\tianj\Desktop\越南工厂瑞晶\mytools
.\setup-smb-manual-line.ps1 -StationNumber 92
.\setup-smb-manual-line.ps1 -StationNumber 95
.\setup-smb-manual-line.ps1 -StationNumber 96
```

**脚本做了什么：**
1. 启用 SMB1.0/CIFS 文件共享支持（Server Windows only）
2. 确认 `Administrator` (或 `Admin`) 用户存在
3. 创建 `D:\ManualLine\StationNN\dist\` 目录结构（ASCII-safe 路径）
4. 设置 NTFS 权限 (Everyone + 指定用户完全控制，继承到子目录)
5. 创建 SMB 共享 `ManualLine` 指向 `dist` 目录
6. 创建/启用防火墙入站规则 (TCP 445 + 139)

**验证共享是否正常（工位电脑本地测试）：**
```powershell
# 在工位电脑上运行
Get-SmbShare
# 应该看到 ManualLine 共享

# 测试本机访问
explorer \\192.168.6.92\ManualLine
```

**从 `.50` 服务器验证连接：**
```python
# 用 pysmb 测试
from smb.SMBConnection import SMBConnection
conn = SMBConnection('Administrator', 'rj', 'server', '')
ok = conn.connect('192.168.6.92', 445)  # 直连 TCP 445
ok = conn.connect('192.168.6.92', 139)  # 或 NetBIOS 139

# 用 smbclient (Linux)
smbclient -U 'Administrator'%'rj' //192.168.6.92/ManualLine -N -c 'ls'
```

**脚本运行后的下一步：**

1. 手动把 `ate_center.db` 复制到 `D:\ManualLine\StationNN\dist\` 文件夹
2. 更新 `lineSupervisor.py` 中的路径配置：
```python
SMB_USER = 'Administrator'   # 或 'Admin' (根据工位)
SMB_PASS = 'rj'
SMB_PORT = 445              # 直连 TCP (大多数工位)
# SMB_PORT = 139           # NetBIOS (某些工位需要用这个)
SHARE_NAME = 'ManualLine'    # 共享名
# 共享根目录是 D:\ManualLine\StationNN\dist\
REMOTE_PATH = '/ate_center.db'  # 直接读取 share 根目录下的 db 文件
```

**常见问题：**

| 问题 | 原因 | 解决方法 |
|------|------|------|
| `Unable to connect to IPC$` | `is_direct_tcp` 参数不对 | 试试 `is_direct_tcp=False` |
| 0 字节文件 | 路径/共享名不对 | 用 `Get-SmbShare` 确认共享名 |
| 超时 | 防火墙拦了 | 工位运行脚本或手动开放 445 端口 |
| 密码错误 | Windows 用户密码不是 `rj` | 工位电脑重新设密码为 `rj` |

**工位编号对应：**
| 编号 | 工位名 | IP |
|------|--------|-----|
| 91 | ICT | 192.168.6.91 |
| 92 | FCT | 192.168.6.92 |
| 93 | 分板机 | 192.168.6.93 |
| 94 | 绑码 | 192.168.6.94 |
| 95 | 组装ATE | 192.168.6.95 |
| 96 | 超声波 | 192.168.6.96 |
| 97 | 波峰焊 | 192.168.6.97 |
| 98 | 成品老化 | 192.168.6.98 |
| 99 | 高压ATE | 192.168.6.99 |
| 100 | 包装ATE | 192.168.6.100 |
