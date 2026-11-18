# -*- coding: utf-8 -*-
"""UI-only primitives shared by factory station agents.

This module intentionally contains no MES, route, device, or database policy.
"""

import os
import sys
import re
import time
import ctypes
import queue
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

_MINIMAL_UI = os.environ.get("STATION_MINIMAL_UI", "0") == "1"
if _MINIMAL_UI:
    _NotebookBase = ttk.Notebook

    class _MinimalNotebook(_NotebookBase):
        """Notebook that omits non-production KPI/analysis tabs."""
        _HIDDEN_TAB_WORDS = ("kpi", "analysis", "分析", "统计")

        def add(self, child, **kw):
            label = str(kw.get("text", "")).lower()
            if any(word in label for word in self._HIDDEN_TAB_WORDS):
                return None
            return super().add(child, **kw)

    ttk.Notebook = _MinimalNotebook

# Keep the Windows backend visible to PyInstaller.  The scanner listener is
# installed from register_scanner_entry() at runtime, so a dynamic-only
# import can otherwise leave packaged EXEs unable to receive keyboard wedges.
try:
    from pynput import keyboard as _pynput_keyboard
    if os.name == "nt":
        from pynput.keyboard import _win32 as _pynput_keyboard_win32  # noqa: F401
except Exception:
    _pynput_keyboard = None


SEMANTIC_COLORS = {
    "canvas": "#08131D",
    "panel": "#101D27",
    "raised": "#192833",
    "border": "#2C414F",
    "text": "#F2F6F8",
    "muted": "#9EB0BC",
    "active": "#18C6D9",
    "pass": "#22D887",
    "attention": "#F2B84B",
    "ng": "#F05252",
    "info": "#4C8DFF",
    "disabled": "#536572",
}

MIN_CONTROL_HEIGHT = 44
NEW_EVENT_CUE_MS = 1800
UI_PREVIEW = os.environ.get("UI_PREVIEW", "").strip().lower() in {"1", "true", "yes"}

def render_streamlit_station_tabs(st, station_code):
    """Render the same six operator tabs for Streamlit station screens."""
    lang = st.selectbox("Language / 语言 / Ngôn ngữ", ("zh", "en", "vi"), key=f"lang_{station_code}")
    labels = {"zh": ("操作手册", "维护手册", "标准作业程序", "每日检查", "操作报告", "专业用户"), "en": ("Operator Manual", "Maintenance Manual", "SOP", "Daily Check", "Operation Report", "Professional User"), "vi": ("Sổ tay vận hành", "Sổ tay bảo trì", "Quy trình SOP", "Kiểm tra hằng ngày", "Báo cáo vận hành", "Người dùng chuyên nghiệp")}[lang]
    tabs = st.tabs(labels)
    for tab, label in zip(tabs, labels):
        with tab:
            st.subheader(label)
            st.info(f"Station {station_code}: MES-managed instructions, checks, and reporting.")


def configure_tk_station(root):
    """Apply the canonical 1366x768 shell and shared ttk sizing."""
    root.geometry("1366x768")
    root.minsize(1024, 700)
    root.configure(bg=SEMANTIC_COLORS["canvas"])
    root.option_add("*Font", ("Segoe UI", 10))
    style = ttk.Style(root)
    style.configure(
        "Treeview",
        rowheight=32,
        font=("Microsoft YaHei UI", 12),
        background=SEMANTIC_COLORS["panel"],
        fieldbackground=SEMANTIC_COLORS["panel"],
        foreground=SEMANTIC_COLORS["text"],
    )
    style.configure(
        "Treeview.Heading",
        font=("Microsoft YaHei UI", 12, "bold"),
    )
    # Operator-facing heartbeat: a small animated heart replaces noisy runtime logs.
    if not getattr(root, "_heartbeat_badge", None):
        badge = tk.Label(root, text="♥  ONLINE · HEARTBEAT", bg="#08131D", fg="#22D887",
                         font=("Segoe UI", 10, "bold"), anchor="e")
        # Keep a reserved top strip instead of overlaying the station header.
        host = tk.Frame(root, bg="#08131D", height=28)
        host.pack(side="top", fill="x", expand=False)
        host.pack_propagate(False)
        # The badge remains a child of the root and is constrained to the
        # reserved strip; the host itself keeps all other controls below it.
        badge.configure(text="\u2665 ONLINE \u00b7 HEARTBEAT", width=24)
        # Keep the heartbeat on the left; the right side is reserved for the
        # MES-authorized Retest and Repair controls.
        badge.place(x=12, y=4, anchor="nw")
        root.after_idle(badge.lift)
        root._heartbeat_badge = badge
        root._heartbeat_host = host
        root._heartbeat_phase = False
        def pulse():
            try:
                if not badge.winfo_exists():
                    return
                root._heartbeat_phase = not root._heartbeat_phase
                badge.configure(fg="#86efac" if root._heartbeat_phase else "#22D887")
                root.after(800, pulse)
            except tk.TclError:
                return
        root.after(800, pulse)
    install_professional_header(root)
    install_kpi_skeleton(root)
    root.after_idle(lambda: install_station_tabs(root))
    return style


def install_professional_header(root):
    """Add a restrained 2D control-room header shared by every station."""
    if getattr(root, "_professional_header", None): return root._professional_header
    bar = tk.Frame(root, bg="#10283A", height=54, padx=16, pady=7)
    bar.pack(side="top", fill="x", expand=False); bar.pack_propagate(False)
    tk.Label(bar, text="RUIJING  ·  2D STATION CONTROL", bg="#10283A", fg="#F2F6F8", font=("Segoe UI", 13, "bold")).pack(side="left")
    station = str(getattr(root, "station_code", os.environ.get("STATION_CODE", "STATION"))).upper()
    domain = os.environ.get("STATION_LINE_DOMAIN", "AUTO_LINE").replace("_", " ")
    tk.Label(bar, text=f"{station}   ·   {domain}   ·   MES / SQLITE / SCANNER", bg="#10283A", fg="#9EB0BC", font=("Segoe UI", 9, "bold")).pack(side="right")
    root._professional_header = bar
    return bar


def install_station_tabs(root):
    """Install the shared operator tabs in every Tk station shell."""
    if getattr(root, "_hide_shared_station_tabs", False):
        return getattr(root, "_station_tabs", None)
    if os.environ.get("STATION_MINIMAL_UI", "0") == "1":
        return getattr(root, "_station_tabs", None)
    if getattr(root, "_station_function_tabs", None):
        root.after_idle(lambda: install_station_diagnostics(root))
        root.after(1200, lambda: _register_first_scanner_entry(root))
        return root._station_tabs
    style=ttk.Style(root)
    style.configure("Station.TNotebook",background="#08131D",borderwidth=0)
    style.configure("Station.TNotebook.Tab",font=("Segoe UI",10,"bold"),padding=(16,9))
    style.map("Station.TNotebook.Tab",background=[("selected","#18C6D9"),("active","#24495B")],foreground=[("selected","#07111A"),("active","#F2F6F8")])
    existing = _find_station_notebook(root)
    if existing is not None:
        result = _append_station_function_tabs(root, existing)
        root.after_idle(lambda: install_station_diagnostics(root))
        root.after(1200, lambda: _register_first_scanner_entry(root))
        return result
    style = ttk.Style(root)
    style.configure("Station.TNotebook", background="#08131D", borderwidth=0)
    style.configure("Station.TNotebook.Tab", font=("Microsoft YaHei UI", 9, "bold"), padding=(7, 4))
    style.map("Station.TNotebook.Tab", background=[("selected", "#E8EEF2")], foreground=[("selected", "#07111A")])
    bar = tk.Frame(root, bg="#08131D", height=43)
    bar.pack(side="top", fill="x", expand=False, padx=8)
    bar.pack_propagate(False)
    book = ttk.Notebook(bar, style="Station.TNotebook")
    book.pack(side="left", fill="both", expand=True)
    language = tk.StringVar(value=os.environ.get("STATION_UI_LANG", "zh").lower())
    if language.get() not in {"zh", "en", "vi"}: language.set("zh")
    selector = ttk.Combobox(bar, textvariable=language, values=("zh", "en", "vi"), width=5, state="readonly")
    selector.pack(side="right", padx=(6, 0), pady=8)
    labels = {
        "zh": ("操作手册", "维护手册", "标准作业程序", "每日检查", "操作报告", "专业用户"),
        "en": ("Operator Manual", "Maintenance Manual", "SOP", "Daily Check", "Operation Report", "Professional User"),
        "vi": ("Sổ tay vận hành", "Sổ tay bảo trì", "Quy trình SOP", "Kiểm tra hằng ngày", "Báo cáo vận hành", "Người dùng chuyên nghiệp"),
    }
    bodies = {
        "zh": ("查看操作步骤、扫码要求、合格判定和异常处理。", "查看点检、保养、校准、备件和维修放行要求。", "查看MES当前版本SOP；版本不一致时停止生产并联系主管。", "记录开机前安全、设备、物料、网络和MES连接状态。", "报告特殊事件、停机、返修、质量风险和交接信息，先保存本地再提交MES。", "专业用户功能需要授权；配置、复测和维修操作都会记录审计日志。"),
        "en": ("View work steps, scan requirements, pass criteria, and exception handling.", "View inspection, maintenance, calibration, spare-part, and repair-release requirements.", "View the current MES SOP. Stop production and contact the supervisor if the version is not current.", "Record safety, equipment, material, network, and MES checks before startup.", "Report special events, downtime, repair, quality risks, and handover notes; save locally before MES submission.", "Professional functions require authorization; configuration, retest, and repair actions are audit logged."),
        "vi": ("Xem các bước thao tác, yêu cầu quét mã, tiêu chí đạt và xử lý bất thường.", "Xem yêu cầu kiểm tra, bảo trì, hiệu chuẩn, phụ tùng và phê duyệt sửa chữa.", "Xem SOP hiện hành từ MES; dừng sản xuất và báo quản lý nếu phiên bản không đúng.", "Ghi nhận an toàn, thiết bị, vật liệu, mạng và kết nối MES trước khi khởi động.", "Báo cáo sự kiện, dừng máy, sửa chữa, rủi ro chất lượng và bàn giao; lưu cục bộ trước khi gửi MES.", "Chức năng chuyên nghiệp cần cấp quyền; mọi thao tác đều được ghi nhật ký."),
    }
    pages=[]
    for i in range(6):
        page=tk.Frame(book,bg="#101D27")
        message=tk.Label(page,text="",bg="#101D27",fg="#F2F6F8",justify="left",anchor="nw",wraplength=1100,font=("Microsoft YaHei UI",11))
        message.pack(fill="both",expand=True,padx=18,pady=16)
        book.add(page,text="")
        pages.append(message)
    def refresh(*_):
        lang=language.get()
        station=str(getattr(root,"station_code",os.environ.get("STATION_CODE","station")))
        for i,message in enumerate(pages):
            book.tab(i,text=labels[lang][i])
            message.configure(text=f"{labels[lang][i]}\n\n{bodies[lang][i]}\n\nStation: {station}")
    selector.bind("<<ComboboxSelected>>",refresh)
    refresh()
    root._station_tabs=book
    root._station_function_tabs=True
    root._station_tabs_language=language
    root.after_idle(lambda: install_station_diagnostics(root))
    root.after(1200, lambda: _register_first_scanner_entry(root))
    return book


def _register_first_scanner_entry(root):
    """Apply the manual-line global scanner wedge to legacy auto-line UIs."""
    if getattr(root, "_common_scanner_entry", None):
        return
    found = []
    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, tk.Entry):
                try:
                    if child.bind("<Return>"):
                        found.append(child)
                except tk.TclError:
                    pass
            walk(child)
    try:
        walk(root)
        if found:
            register_scanner_entry(root, found[0])
            root._common_scanner_entry = found[0]
    except tk.TclError:
        return


def _find_station_notebook(root):
    found=[]
    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook): found.append(child)
            walk(child)
    try: walk(root)
    except tk.TclError: return None
    return found[0] if found else None


def _append_station_function_tabs(root, book):
    if getattr(root, "_station_function_tabs", None): return book
    book.configure(style="Station.TNotebook")
    labels=("操作手册", "维护手册", "标准作业程序", "每日检查", "操作报告", "专业用户")
    bodies=("查看操作步骤、扫码要求、合格判定和异常处理。", "查看点检、保养、校准、备件和维修放行要求。", "查看MES当前版本SOP；版本不一致时停止生产。", "记录开机前安全、设备、物料、网络和MES状态。", "报告特殊事件、停机、返修、质量风险和交接信息。", "专业功能需要授权，配置、复测和维修都会记录审计日志。")
    for label,body in zip(labels,bodies):
        page=tk.Frame(book,bg="#101D27")
        tk.Label(page,text=f"{label}\n\n{body}",bg="#101D27",fg="#F2F6F8",justify="left",anchor="nw",font=("Microsoft YaHei UI",11)).pack(fill="both",expand=True,padx=18,pady=16)
        book.add(page,text=label)
    root._station_function_tabs=True;root._station_tabs=book;return book


def install_station_diagnostics(root, replace=False, hide_legacy=False, keep_legacy=(), append=False):
    """Add the five read-only production diagnostics pages to every station.

    These pages use the local SQLite tables when present and never write
    production data. When replace=True, the existing station-specific pages
    are removed from the visible notebook first, matching the ATE layout.
    """
    if getattr(root, "_station_diagnostics", None):
        return root._station_diagnostics
    book = _find_station_notebook(root)
    if book is None:
        return None
    book.configure(style="Station.TNotebook")
    legacy_tabs = list(book.tabs())
    if replace:
        for child in list(book.tabs()):
            book.forget(child)
    pages = {}
    for key, label in (
        ("live", "LIVE RESULTS"),
        ("mes", "MES NG CACHE"),
        ("parsed", "PARSED NG"),
        ("sn", "LOCAL SN"),
        ("resources", "RESOURCES"),
    ):
        frame = tk.Frame(book, bg="#101D27")
        if append:
            book.add(frame, text=label)
        else:
            book.insert(0, frame, text=label)
        pages[key] = frame
    if hide_legacy:
        for index, tab_id in enumerate(legacy_tabs):
            if index in set(keep_legacy):
                continue
            try:
                book.hide(tab_id)
            except tk.TclError:
                pass

    trees = {}
    tree_columns = {
        "live": (("time", "时间"), ("source", "来源"), ("sn", "SN"), ("result", "结果"), ("file", "文件")),
        "mes": (("time", "时间"), ("sn", "SN"), ("source", "来源"), ("reason", "原因")),
        "parsed": (("time", "时间"), ("sn", "SN"), ("result", "结果"), ("reason", "原因")),
        "sn": (("time", "时间"), ("sn", "SN"), ("result", "结果"), ("file", "来源文件")),
    }
    for key, columns in tree_columns.items():
        tree = ttk.Treeview(pages[key], columns=tuple(col for col, _ in columns), show="headings")
        for col, title in columns:
            tree.heading(col, text=title)
            tree.column(col, width=220 if col in {"sn", "file", "reason"} else 140, anchor="w")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        trees[key] = tree

    resource_label = tk.Label(pages["resources"], text="", bg="#101D27", fg="#F2F6F8", anchor="nw", justify="left")
    resource_label.pack(fill="both", expand=True, padx=16, pady=16)

    station = str(getattr(root, "station_code", os.environ.get("STATION_CODE", "station")))
    db_candidates = []
    for raw in (os.environ.get("ATE_DB_PATH", ""), str(Path(sys.executable).parent / f"{station}.db"), str(Path.cwd() / f"{station}.db")):
        if raw and raw not in db_candidates:
            db_candidates.append(raw)

    def db_path():
        for raw in db_candidates:
            if Path(raw).exists():
                return raw
        return None

    def value(row, *names):
        for name in names:
            if name in row.keys() and row[name] is not None:
                return str(row[name])
        return ""

    def query(table, limit=200):
        path = db_path()
        if not path:
            return []
        try:
            con = sqlite3.connect(path, timeout=0.3)
            con.row_factory = sqlite3.Row
            rows = con.execute(f"SELECT * FROM [{table}] ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
            con.close()
            return rows
        except Exception:
            return []

    def fill(tree, rows, mapping):
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=tuple(value(row, *names) for names in mapping))

    def refresh():
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        local = query("atecommon_local_records")
        mes = query("atecommon_mes_ng_cache")
        parsed = query("atecommon_parsed_ng")
        fill(trees["live"], local, (("created_at", "timestamp", "time"), ("source", "source_file"), ("sn", "serial_number", "sn"), ("result", "result"), ("source_file", "file")))
        fill(trees["sn"], local, (("created_at", "timestamp", "time"), ("serial_number", "sn"), ("result", "result"), ("source_file", "file")))
        fill(trees["mes"], mes, (("created_at", "received_at", "timestamp", "time"), ("sn", "serial_number"), ("source", "source_station", "source"), ("reason", "reason", "error")))
        fill(trees["parsed"], parsed, (("created_at", "parsed_at", "timestamp", "time"), ("sn", "serial_number"), ("result", "result"), ("reason", "reason", "error")))
        watch = Path(os.environ.get("ATE_WATCH_DIR", r"D:\ATS\测试报表"))
        files = []
        try:
            files = sorted((p for p in watch.rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".xlsx", ".xls"}), key=lambda p: p.stat().st_mtime, reverse=True)[:100]
        except Exception:
            pass
        resource_label.configure(text=f"Station: {station}\n数据库: {db_path() or '未找到'}\n监控目录: {watch}\n资源文件: {len(files)}\n\n" + "\n".join(str(p) for p in files))
        try:
            root.after(2000, refresh)
        except tk.TclError:
            pass

    root._station_diagnostics = pages
    refresh()
    return pages


def _show_station_document(root, title, body):
    win = tk.Toplevel(root); win.title(title); win.geometry("760x520"); win.transient(root)
    text = tk.Text(win, wrap="word", font=("Microsoft YaHei UI", 12)); text.pack(fill="both", expand=True, padx=12, pady=12)
    text.insert("1.0", body); text.configure(state="disabled")
    ttk.Button(win, text="Close / 关闭 / Đóng", command=win.destroy).pack(anchor="e", padx=12, pady=(0, 12))


def install_station_basics_menu(root):
    if os.environ.get("STATION_MINIMAL_UI", "0") == "1":
        return None
    if getattr(root, "_station_basics_menu", None): return root._station_basics_menu
    menu = tk.Menu(root, tearoff=False)
    docs = (("Operator Manual / 操作手册 / Hướng dẫn vận hành", "OPERATOR MANUAL / 操作手册 / HƯỚNG DẪN VẬN HÀNH"), ("Maintenance Manual / 维修手册 / Hướng dẫn bảo trì", "MAINTENANCE MANUAL / 维修手册 / HƯỚNG DẪN BẢO TRÌ"), ("SOP / 作业指导书 / Quy trình SOP", "SOP / 作业指导书 / QUY TRÌNH SOP"))
    for label, title in docs:
        menu.add_command(label=label, command=lambda t=title: _show_station_document(root, t, f"{t}\n\nMES-managed document.\nMES管理文档。\nTài liệu do MES quản lý.\n\nStation: {getattr(root, 'station_code', os.environ.get('STATION_CODE', 'UNKNOWN'))}"))
    menu.add_separator()
    menu.add_command(label="Daily Check / 日检 / Kiểm tra ngày", command=lambda: _show_station_document(root, "Daily Check / 日检 / Kiểm tra ngày", "Operator authorization / 操作员授权 / Quyền vận hành\n\nMaintenance status / 维修状态 / Trạng thái bảo trì\n\nSOP current / SOP有效 / SOP hiện hành\n\nSQLite available / SQLite可用 / SQLite hoạt động\n\nMES reachable / MES可达 / MES kết nối\n\nOutbox healthy / 队列正常 / Hàng đợi OK\n\nAgent heartbeat / 心跳正常 / Nhịp tim agent"))
    menu.add_command(label="Operation Report / 操作报告 / Báo cáo vận hành", command=lambda: _show_station_document(root, "Operation Report / 操作报告 / Báo cáo vận hành", "Report special events to MES.\n向MES报告特殊情况。\nBáo cáo sự kiện đặc biệt cho MES.\n\nThe report is saved locally before MES transmission."))
    root.configure(menu=menu); root._station_basics_menu = menu
    return menu


def install_kpi_skeleton(root):
    if os.environ.get("STATION_MINIMAL_UI", "0") == "1":
        return None
    """Add a compact, data-neutral KPI strip shared by Tk station shells.

    Values remain an em dash until the station binds its read-only snapshot;
    this prevents the UI from inventing production counts.  The chart canvas
    is intentionally fixed-size and does not animate or reflow the page.
    """
    if getattr(root, "_kpi_panel", None):
        return root._kpi_panel
    panel = tk.Frame(root, bg="#0B1B2B", height=82, padx=16, pady=8)
    panel.pack(side="top", fill="x", expand=False)
    panel.pack_propagate(False)
    tk.Label(panel, text="KPI", bg="#0b1b2b", fg="#94a3b8",
             font=("Segoe UI", 9, "bold"), width=5).pack(side="left", padx=(0, 4))
    vars_by_key = {}
    for key, label, color in (("total", "TOTAL", "#e2e8f0"), ("pass", "PASS", "#4ade80"),
                              ("ng", "NG", "#f87171"), ("yield", "YIELD", "#38bdf8")):
        card = tk.Frame(panel, bg="#142A3A", width=112, height=62, highlightthickness=1, highlightbackground="#2C414F")
        card.pack(side="left", padx=3)
        card.pack_propagate(False)
        tk.Label(card, text=label, bg="#142A3A", fg="#9EB0BC",
                 font=("Segoe UI", 9, "bold")).pack(pady=(5, 0))
        value = tk.StringVar(value="—")
        vars_by_key[key] = value
        tk.Label(card, textvariable=value, bg="#142A3A", fg=color,
                 font=("Segoe UI", 18, "bold")).pack()
    root._kpi_panel = panel
    root._kpi_vars = vars_by_key
    return panel


def _kpi_counts(total, passed, ng, mes_snapshot=None):
    """Resolve local-first counts, falling back to a read-only MES snapshot."""
    if total is None or passed is None or ng is None:
        source = (mes_snapshot or {}).get("stats", mes_snapshot or {})
        total = total if total is not None else source.get("total")
        passed = passed if passed is not None else source.get("pass", source.get("passed"))
        ng = ng if ng is not None else source.get("ng", source.get("fail"))
    return total, passed, ng


def update_station_kpi(root, *, total=None, passed=None, ng=None, mes_snapshot=None):
    """Bind local counts, or MES read-only snapshot when local data is missing."""
    vars_by_key = getattr(root, "_kpi_vars", None)
    if not vars_by_key:
        return
    values = _kpi_counts(total, passed, ng, mes_snapshot)
    if any(value is None for value in values):
        return
    total_i, pass_i, ng_i = (max(0, int(value)) for value in values)
    vars_by_key["total"].set(str(total_i))
    vars_by_key["pass"].set(str(pass_i))
    vars_by_key["ng"].set(str(ng_i))
    vars_by_key["yield"].set(f"{(pass_i / total_i * 100) if total_i else 0:.1f}%")


def add_preview_watermark(root):
    """Mark a real Agent window as write-blocked preview evidence."""
    if not UI_PREVIEW:
        return None
    banner = tk.Label(
        root,
        text="PREVIEW / NO PRODUCTION DATA",
        bg="#F2B84B",
        fg="#08131D",
        font=("Microsoft YaHei UI", 13, "bold"),
        pady=5,
    )
    banner.pack(fill="x")
    return banner


def register_scanner_entry(root, entry):
    """Register the visible SN field plus the proven ATE global wedge hook."""
    entry.configure(
        font=("Consolas", 16, "bold"),
        bg=SEMANTIC_COLORS["raised"],
        fg=SEMANTIC_COLORS["text"],
        insertbackground=SEMANTIC_COLORS["active"],
        relief="solid",
        highlightthickness=2,
        highlightcolor=SEMANTIC_COLORS["active"],
        highlightbackground=SEMANTIC_COLORS["border"],
    )
    root.after_idle(entry.focus_set)
    try:
        from pynput import keyboard
        state = {"buffer": [], "last": 0.0, "finish_job": None, "events": queue.Queue()}

        def _clear_previous_scan():
            """Clear the prior scan before the first character of a new scan.

            Scanner wedges reuse the same Entry for every board.  Leaving the
            previous value in the widget lets a new keyboard burst appear to
            be appended to the old SN, especially when the application has
            not cleared the Entry after its Return handler.
            """
            try:
                if isinstance(entry, tk.Text):
                    entry.delete("1.0", tk.END)
                else:
                    entry.delete(0, tk.END)
            except Exception:
                pass

        def _root_foreground():
            try:
                fg = int(ctypes.windll.user32.GetForegroundWindow())
                hwnd = int(root.winfo_id())
                while fg:
                    if fg == hwnd:
                        return True
                    fg = int(ctypes.windll.user32.GetParent(fg))
            except Exception:
                return False
            return False

        def _deliver_value(value):
            value = str(value or "").strip().upper()
            if len(value) < 3 or any(ch.isspace() or not ch.isprintable() for ch in value):
                return
            try:
                if isinstance(entry, tk.Text):
                    current = entry.get("1.0", "end-1c").strip().upper()
                else:
                    current = entry.get().strip().upper()
            except Exception:
                current = ""
            if current == value or current.endswith(value):
                return
            if isinstance(entry, tk.Text):
                entry.delete("1.0", tk.END)
                entry.insert("1.0", value)
            else:
                entry.delete(0, tk.END)
                entry.insert(0, value)
            entry.event_generate("<Return>")

        def _finish_burst():
            raw = "".join(state["buffer"]).strip().upper()
            state["buffer"] = []
            state["finish_job"] = None
            _deliver_value(raw)

        def _process_key(key):
            try:
                now = time.monotonic()
                if now - state["last"] > 3.0:
                    state["buffer"] = []
                state["last"] = now
                char = key.char.upper() if getattr(key, "char", None) else None
                if char and char.isprintable() and not char.isspace():
                    if not state["buffer"]:
                        _clear_previous_scan()
                    state["buffer"].append(char)
                    if state["finish_job"] is not None:
                        try:
                            root.after_cancel(state["finish_job"])
                        except Exception:
                            pass
                    # Barcode wedges arrive much faster than human typing.
                    # Finalize after the short inter-character gap, even if
                    # the scanner is configured without a trailing Enter.
                    # Long shell labels on slower remote stations can have
                    # inter-character gaps above 1.5s. Keep collecting until
                    # the scanner's Enter arrives or the longer quiet period.
                    state["finish_job"] = root.after(2500, _finish_burst)
                    return
                if key == keyboard.Key.enter:
                    raw = "".join(state["buffer"]).strip().upper()
                    state["buffer"] = []
                    if state["finish_job"] is not None:
                        try:
                            root.after_cancel(state["finish_job"])
                        except Exception:
                            pass
                        state["finish_job"] = None
                    root.after(0, lambda value=raw: _deliver_value(value))
            except Exception:
                pass

        def _drain_keyboard_events():
            # pynput callbacks run on a worker thread.  All Tk operations,
            # including after/after_cancel and Entry updates, must run on the
            # Tk main thread or keyboard wedges become intermittent.
            try:
                while True:
                    _process_key(state["events"].get_nowait())
            except queue.Empty:
                pass
            try:
                if root.winfo_exists():
                    root.after(20, _drain_keyboard_events)
            except Exception:
                pass

        def _on_press(key):
            try:
                state["events"].put_nowait(key)
            except Exception:
                pass

        old_listener = getattr(root, "_ate_scanner_listener", None)
        if old_listener is not None:
            try:
                old_listener.stop()
            except Exception:
                pass
        listener = keyboard.Listener(on_press=_on_press)
        listener.daemon = True
        listener.start()
        root._ate_scanner_listener = listener
        root.after(20, _drain_keyboard_events)
    except Exception:
        # The station remains usable through its visible Entry and TCP path.
        pass
    return entry


def restore_scanner_focus(root, entry):
    try:
        if root.winfo_exists() and entry.winfo_exists():
            root.after_idle(entry.focus_set)
    except Exception:
        pass


def voice_pronunciation(text):
    """Make station acronyms intelligible without changing displayed text."""
    value = str(text or "")
    value = re.sub(r"\bATE\b", "A, T, E", value, flags=re.IGNORECASE)
    value = re.sub(r"\bAOI\b", "A, O, I", value, flags=re.IGNORECASE)
    return value


class NewEventGuard:
    """Suppress repeated presentation of the same immutable alarm event."""

    def __init__(self, retention_seconds=8 * 60 * 60):
        self.retention_seconds = max(60, int(retention_seconds))
        self._seen = {}

    def accept(self, event_id):
        key = str(event_id or "").strip()
        if not key:
            return True
        now = time.monotonic()
        cutoff = now - self.retention_seconds
        self._seen = {item: stamp for item, stamp in self._seen.items() if stamp >= cutoff}
        if key in self._seen:
            return False
        self._seen[key] = now
        return True


def stable_alarm_key(status, sn, detail):
    """Fallback key for callers that do not yet provide an MES event id."""
    return "|".join(str(value or "").strip() for value in (status, sn, detail))


def present_new_alarm_once(window, root, cue_ms=NEW_EVENT_CUE_MS):
    """Briefly surface a new alarm, then stop competing for scanner focus."""
    try:
        window.attributes("-topmost", True)
        window.lift()
    except Exception:
        pass

    def settle():
        try:
            if window.winfo_exists():
                window.attributes("-topmost", False)
            if root and root.winfo_exists():
                root.focus_set()
        except Exception:
            pass

    try:
        return window.after(max(250, int(cue_ms)), settle)
    except Exception:
        return None
