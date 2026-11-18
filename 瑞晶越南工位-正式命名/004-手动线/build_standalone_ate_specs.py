from pathlib import Path

HERE = Path(__file__).resolve().parent
COMMON = [str(HERE / "atecommonagent.py"), str(HERE / "ate_common_station_ui.py")]
HIDDEN = [
    "atecommonagent", "ate_common_station_ui", "openpyxl", "watchdog",
    "watchdog.observers", "watchdog.events", "win32com.client",
    "tkinter.filedialog", "tkinter.messagebox", "tkinter.ttk",
    "tkinter.simpledialog", "tkinter.scrolledtext",
]

configs = [
    ("(07)组装ATE", "assembly_common_ui.py", "assembly_ate_common", "Assembly ATE / 组装ATE"),
    ("(10)高压ATE", "hivolt_common_ui.py", "hivolt_ate_common", "High-Voltage ATE / 高压ATE"),
    ("(11)包装ATE", "packing_common_ui.py", "packing_ate_common", "Packaging ATE / 包装ATE"),
]

for dirname, entry_name, exe_name, _title in configs:
    entry = HERE / dirname / entry_name
    spec = HERE / dirname / f"{exe_name}.spec"
    spec.write_text(f'''# standalone common ATE; no legacy station agent
from pathlib import Path

a = Analysis(
    [{str(entry)!r}],
    pathex=[{str(HERE)!r}],
    binaries=[],
    datas={[(p, ".") for p in COMMON]!r},
    hiddenimports={HIDDEN!r},
    hookspath=[], hooksconfig={{}}, runtime_hooks=[],
    excludes=["PySide6", "shiboken6", "numpy", "pandas", "lxml", "matplotlib", "scipy"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={exe_name!r},
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               upx_exclude=[], name={exe_name!r})
''', encoding="utf-8")
print("STANDALONE_ATE_SPECS_OK")
