# Assembly ATE Python source set

这是手动线组装 ATE 的完整 Python 源码集合。

## 入口程序

- `assembly_ate_agent.py` — 组装 ATE 主程序
- `run_assembly_ate.py` — 从本目录启动主程序
- `assembly_ate_core.py` — 组装 ATE 核心测试逻辑
- `assembly_common_ui.py` — 公共 ATE 启动入口

## 公共组件

本目录同时包含公共 Agent、界面、扫描枪、报警、文件监控、Excel、重测和 MES 相关源码。

`station_components/` 保存公共组件包源码。

## 启动

使用 Python 3.8：

`C:\Users\tianj\AppData\Local\Programs\Python\Python38\python.exe run_assembly_ate.py`

运行前请确认已安装 `openpyxl`、`watchdog`、`pynput` 和 `pywin32`。
