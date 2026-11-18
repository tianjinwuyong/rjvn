# ATE components

集中保存三个手动线 ATE 共用的 Python 源码组件。

## Python 源码

- `python/atecommonagent.py` — 数据读取、SQLite、文件监控、NG/DUP 和语音
- `python/ate_common_station_ui.py` — ATE 界面和扫描输入
- `python/station_ui_primitives.py` — 扫码枪键盘捕获
- `python/station_scan_alarm.py` — 全屏报警和语音

## 构建规格

`build/` 中保存 Assembly、Hi-Volt、Package 三个 ATE 的 PyInstaller spec 文件。

构建使用：

`C:\Users\tianj\AppData\Local\Programs\Python\Python38\python.exe`

依赖安装：

`python -m pip install -r requirements.txt`

注意：修改公共组件后，需要将 `python` 中的文件同步回正式项目目录，再使用各 ATE 的 spec 重新编译。
