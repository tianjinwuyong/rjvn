# 自动线 2D 构建与检查记录

日期：2026-08-07  
范围：`002-自动线` 的 2D Agent；明确不包含任何 3D Agent。

## 结果

- 11 个存在的 2D spec 已成功构建并写入各自 `dist` 目录。
- `Auto_Packing_ATE_Right_Agent.spec` 与 `Auto_Pallet_Binding_Agent.spec` 的乱码 `pathex` 已改为相对目录发现，重新构建通过。
- `Auto_QRBinding_Agent.spec` 在目录中不存在，因此没有伪造构建结果。
- 48 个 2D Python 源文件完成语法检查；共享到达/历史/复测/维修模块完成导入检查。
- 每次替换前均保留了带时间戳的 EXE 备份。

## 关键输出哈希

| Agent | 输出 | SHA-256 |
|---|---|---|
| 右包装 ATE | `002-自动线/(11)包装ATE右/dist/Auto_Packing_ATE_Right_Agent.exe` | `1A41D500EFDADA3B93075865BD40EFD8DC43652D1961B92AB81464E170251014` |
| 栈板绑码 | `002-自动线/(13)栈板绑码/dist/Auto_Pallet_Binding_Agent.exe` | `5D5AD80E1BCF3CFA17EC3B82954651FC040F4CD77ECA6A75A90DE1A892B57506` |

完整清单与其他输出哈希见 `dc/auto-line-build-report.json`。

## 验证边界

本机尝试启动新生成的 EXE 时被 Windows Application Control 策略拦截，不能把“进程存活”冒充为通过。源代码、共享模块、PyInstaller 构建和输出文件哈希均已验证；部署到目标机后还需要在目标机执行一次交互式启动检查。
