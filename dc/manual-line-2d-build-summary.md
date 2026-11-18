# 手动线 2D 构建记录

日期：2026-08-07  
范围：`004-手动线`；不包含任何 Qt/3D/Win7 临时构建目录。

## 结果

手动线 14 个 2D spec 全部构建成功，输出位于每个工站自己的 `dist` 目录：

`wave_solder_heartbeat_agent`、PDA 扫码上料、AOI、ICT、FCT、分板、外壳绑码、组装 ATE、超声、成品老化、高压 ATE、包装 ATE、外箱绑码、栈板绑码。

修复项：

- 超声 spec 改为 PyInstaller 可用的 `SPECPATH`，避免 `__file__` 缺失。
- 栈板绑码 2D spec 的乱码路径改为动态目录，并排除 PySide6/3D 依赖。

## 检查

- 76 个手动线 Python 源文件通过语法检查。
- 共享到达、历史、维修、复测模块通过导入检查。
- 分板工站已补接 `station_arrival_core`：扫描先执行到达/NG/站点跳跃校验，再进入母板查询；新 EXE SHA-256 为 `6C00E72651315DBBAFD4DAC9C918A4355FADE329A7670D5CE354CD76C23BFAE2`。
- 每个输出均已计算 SHA-256；以各自 `dist` 中的 EXE 为准。
- 尚未远程部署；也没有把本机被 Windows Application Control 拦截的启动尝试算作通过。

部署前应在目标电脑上做一次交互式启动和 MES/本地端口检查。
