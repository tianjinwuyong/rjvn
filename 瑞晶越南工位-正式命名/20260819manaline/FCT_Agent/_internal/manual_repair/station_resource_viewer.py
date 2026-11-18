"""Shared human-readable local-resource view model for every station Agent."""
from pathlib import Path
import os
import json
import sqlite3
import csv
import time
import tkinter as tk
from tkinter import ttk


RESOURCE_SKIP_DIRS = {
    "build", "dist", "_internal", "__pycache__", ".git", ".venv",
    "node_modules", "$recycle.bin",
}


def _resource_files(root, recursive=True):
    root = Path(root)
    if not recursive:
        try:
            candidates = [root / name for name in os.listdir(str(root))]
        except OSError:
            return
        for path in candidates:
            try:
                if path.is_file() and path.suffix.lower() in {".csv", ".xlsx", ".xlsm"} and not path.name.startswith("~$"):
                    yield path
            except OSError:
                continue
        return
    try:
        for current, dirs, files in os.walk(str(root), onerror=lambda _error: None):
            dirs[:] = [d for d in dirs if d.lower() not in RESOURCE_SKIP_DIRS]
            for name in files:
                path = Path(current) / name
                if path.suffix.lower() in {".csv", ".xlsx", ".xlsm"} and not path.name.startswith("~$"):
                    yield path
    except OSError:
        return


def read_resource_set(root, mode="startup", recursive=True, limit=1000000):
    """Read supported local resource files into the common SQLite-ingest shape."""
    root = Path(root)
    resources = []
    tables = []
    if not root.exists():
        return {"root": str(root), "mode": mode, "resources": resources, "tables": tables}
    # Startup discovery must remain bounded on low-power station PCs.
    limit = min(max(int(limit or 0), 1), 10000)
    for path in _resource_files(root, recursive=recursive):
        try:
            stat = path.stat()
            item = {"path": str(path), "extension": path.suffix, "bytes": stat.st_size,
                    "modified_ns": stat.st_mtime_ns}
            resources.append(item)
            view = read_tabular_resource(path, limit=limit)
            tables.append({"path": str(path), "columns": view.get("columns", []),
                           "rows": view.get("rows", []), "error": view.get("error", "")})
        except Exception as exc:
            tables.append({"path": str(path), "columns": [], "rows": [], "error": str(exc)})
    return {"root": str(root), "mode": mode, "resources": resources, "tables": tables}


def build_resource_view(db_path, snapshot=None, limit=20):
    db_path = Path(db_path)
    view = {'database': {'path': str(db_path), 'exists': db_path.exists(), 'bytes': 0},
            'tables': [], 'outbox': [], 'resources': [], 'tabular': []}
    if db_path.exists():
        try:
            view['database']['bytes'] = db_path.stat().st_size
            with sqlite3.connect(str(db_path)) as db:
                names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                for name in names:
                    quoted = '"' + name.replace('"', '""') + '"'
                    count = db.execute('SELECT COUNT(*) FROM ' + quoted).fetchone()[0]
                    cur = db.execute('SELECT * FROM ' + quoted + ' LIMIT ?', (limit,))
                    columns = [d[0] for d in cur.description or []]
                    rows = [{k: str(v)[:240] for k, v in zip(columns, values)} for values in cur.fetchall()]
                    view['tables'].append({'name': name, 'rows': count, 'columns': columns, 'preview': rows})
        except sqlite3.Error as exc:
            view['database']['error'] = str(exc)
    for row in (snapshot or {}).get('outbox', [])[:limit]:
        view['outbox'].append({k: row.get(k, '') for k in ('event_id', 'event_type', 'sn', 'result', 'attempts', 'created_at')})
    for path in sorted(db_path.parent.glob('*')):
        if path.suffix.lower() in ('.csv', '.xlsx', '.xlsm'):
            view['tabular'].append(read_tabular_resource(path, limit=limit))
    return view


def read_tabular_resource(path, sheet_name=0, limit=500):
    """Read CSV/XLSX resource data into the same columns/rows shape used by station UIs."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.csv':
        with path.open('r', newline='', encoding='utf-8-sig') as handle:
            rows = list(csv.reader(handle))[:limit + 1]
        if not rows:
            return {'path': str(path), 'columns': [], 'rows': []}
        columns = [str(v).strip() or f'column_{i + 1}' for i, v in enumerate(rows[0])]
        data = [dict(zip(columns, [str(v).strip() for v in row])) for row in rows[1:]]
        return {'path': str(path), 'columns': columns, 'rows': data}
    if suffix in ('.xlsx', '.xlsm'):
        try:
            from openpyxl import load_workbook
            book = load_workbook(path, read_only=True, data_only=True)
            sheet = book.worksheets[sheet_name] if isinstance(sheet_name, int) else book[sheet_name]
            values = list(sheet.iter_rows(values_only=True))[:limit + 1]
            columns = [str(v).strip() if v is not None and str(v).strip() else f'column_{i + 1}'
                       for i, v in enumerate(values[0] if values else [])]
            data = [dict(zip(columns, [str(v) if v is not None else '' for v in row])) for row in values[1:]]
            return {'path': str(path), 'columns': columns, 'rows': data}
        except Exception as exc:
            return {'path': str(path), 'columns': [], 'rows': [], 'error': str(exc)}
    return {'path': str(path), 'columns': [], 'rows': [], 'error': 'UNSUPPORTED_RESOURCE_TYPE'}


class ResourceViewerPanel:
    """Shared read-only Excel/CSV panel used by Tk station Agents."""

    EXTENSIONS = ('.xlsx', '.xlsm', '.csv')

    def __init__(self, parent, root_path):
        self.root_path = root_path
        self.status = tk.StringVar(value='选择文件查看前 500 行')
        self.files = ttk.Treeview(parent, columns=('file', 'type', 'size', 'modified'), show='headings')
        for key, label, width in (('file', '文件', 250), ('type', '类型', 70), ('size', '大小', 90), ('modified', '修改时间', 150)):
            self.files.heading(key, text=label)
            self.files.column(key, width=width, anchor='w')
        self.files.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        ttk.Scrollbar(parent, orient='vertical', command=self.files.yview).pack(side='left', fill='y', pady=6)
        preview = tk.Frame(parent)
        preview.pack(side='left', fill='both', expand=True, padx=6, pady=6)
        self.preview = ttk.Treeview(preview, show='headings')
        y_scroll = ttk.Scrollbar(preview, orient='vertical', command=self.preview.yview)
        x_scroll = ttk.Scrollbar(preview, orient='horizontal', command=self.preview.xview)
        self.preview.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.preview.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')
        preview.grid_rowconfigure(0, weight=1)
        preview.grid_columnconfigure(0, weight=1)
        self.files.bind('<<TreeviewSelect>>', self._show_selected)
        self.refresh()

    def _paths(self):
        root = self.root_path() if callable(self.root_path) else self.root_path
        root = Path(root)
        if not root.exists():
            return []
        paths = list(_resource_files(root, recursive=True))
        return sorted(paths, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)[:200]

    def refresh(self):
        self.files.delete(*self.files.get_children())
        paths = self._paths()
        for path in paths:
            stat = path.stat()
            self.files.insert('', 'end', iid=str(path), values=(path.name, path.suffix.upper().lstrip('.'),
                f'{stat.st_size:,} B', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))))
        self.status.set(f'{len(paths)} 个文件 · 只读')

    def _show_selected(self, _event=None):
        selected = self.files.selection()
        if not selected:
            return
        path = Path(selected[0])
        view = read_tabular_resource(path, limit=500)
        columns = list(view.get('columns') or [])
        self.preview.delete(*self.preview.get_children())
        self.preview.configure(columns=columns)
        for column in columns:
            self.preview.heading(column, text=column)
            self.preview.column(column, width=max(120, min(260, len(column) * 12)), anchor='w')
        for row in view.get('rows', []):
            self.preview.insert('', 'end', values=[str(row.get(column, ''))[:500] for column in columns])
        self.status.set(f'{path.name} · {len(view.get("rows", []))} 行 · 只读' if not view.get('error')
                        else f'读取失败: {view["error"]}')


def render_resource_view(view):
    """Render a resource model as plain text for Tkinter, Qt, logs, or mobile adapters."""
    db = view['database']
    lines = ['LOCAL RESOURCES / 本地资源', f"SQLite: {db['path']}", f"Bytes: {db['bytes']}"]
    if db.get('error'):
        lines.append('Database error: ' + db['error'])
    for table in view.get('tables', []):
        lines.append(f"\nTABLE / 数据表: {table['name']} ({table['rows']} rows)")
        lines.append('columns: ' + ', '.join(table.get('columns', [])))
        for row in table.get('preview', []):
            lines.append(' | '.join(f'{k}={v}' for k, v in row.items()))
    lines.append('\nOUTBOX / 待上传事件')
    for row in view.get('outbox', []):
        lines.append(' | '.join(f'{k}={v}' for k, v in row.items()))
    for table in view.get('tabular', []):
        lines.append(f"\nFILE TABLE / 文件表格: {table['path']}")
        lines.append('columns: ' + ', '.join(table.get('columns', [])))
        for row in table.get('rows', []):
            lines.append(' | '.join(f'{k}={v}' for k, v in row.items()))
    return '\n'.join(lines)
