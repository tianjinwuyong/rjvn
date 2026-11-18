"""Common read-only local resource model for Ruijing station agents."""
from pathlib import Path
import sqlite3
import shutil


def build_local_resource_view(db_path, snapshot, resource_dirs=()):
    """Return local SQLite, Outbox, attachment, and disk facts without mutating data."""
    db_path = Path(db_path)
    try:
        db_bytes = db_path.stat().st_size
    except OSError:
        db_bytes = 0
    root = db_path.parent
    directories = []
    for item in resource_dirs or ('attachments', 'evidence', 'exports'):
        path = root / item
        try:
            files = [p for p in path.rglob('*') if p.is_file()] if path.exists() else []
            size = sum(p.stat().st_size for p in files)
        except OSError:
            files, size = [], 0
            directories.append({'name': item, 'path': str(path), 'exists': path.exists(),
                            'files': len(files), 'bytes': size,
                            'entries': [str(p.relative_to(path)) for p in files[:100]]})
    try:
        usage = shutil.disk_usage(str(root))
        disk = {'total': usage.total, 'free': usage.free, 'used': usage.used}
    except OSError:
        disk = {'total': 0, 'free': 0, 'used': 0}
    tables = []
    if db_path.exists():
        try:
            with sqlite3.connect(str(db_path)) as db:
                names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                for name in names:
                    count = db.execute('SELECT COUNT(*) FROM "{}"'.format(name.replace('"', '""'))).fetchone()[0]
                    cursor = db.execute('SELECT * FROM "{}" LIMIT 20'.format(name.replace('"', '""')))
                    columns = [d[0] for d in cursor.description or []]
                    preview = []
                    for values in cursor.fetchall():
                        preview.append({key: str(value)[:240] for key, value in zip(columns, values)})
                    tables.append({'name': name, 'rows': count, 'columns': columns, 'preview': preview})
        except sqlite3.Error:
            tables = []
    outbox_events = []
    for row in snapshot.get('outbox', [])[:100]:
        outbox_events.append({'event_id': row.get('event_id', ''), 'type': row.get('event_type', ''),
                              'sn': row.get('sn', ''), 'result': row.get('result', ''),
                              'attempts': row.get('attempts', 0), 'created_at': row.get('created_at', '')})
    return {'station_code': snapshot.get('station_code', ''),
            'database': {'path': str(db_path), 'exists': db_path.exists(), 'bytes': db_bytes},
            'outbox_pending': len(snapshot.get('outbox', [])),
            'outbox_events': outbox_events, 'tables': tables,
            'directories': directories, 'disk': disk}
