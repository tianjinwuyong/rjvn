"""Runtime protections shared by Windows station agents."""
import ctypes
import os


class _WindowsMutex:
    def __init__(self, handle): self.handle = handle
    def close(self):
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
    def __del__(self): self.close()
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


def acquire_single_instance(name):
    if os.name != "nt":
        return _WindowsMutex(None)
    # use_last_error=True makes ctypes snapshot the Win32 last-error code at
    # the exact moment of the CreateMutexW call.  Reading GetLastError() as a
    # separate call is unreliable: any intervening Win32 call (numpy/tkinter
    # DLL setup, ctypes internals) can overwrite the thread's last-error with
    # a stale ERROR_ALREADY_EXISTS(183), causing a false "already running".
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\RUIJING_" + str(name))
    if not handle:
        return None
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return _WindowsMutex(handle)


def wait_file_stable(path, stable_seconds=1.0, max_wait=10.0):
    """Wait until a file stops changing (Excel finished writing it).

    Returns True once the file size has been unchanged for ``stable_seconds``,
    or once ``max_wait`` seconds have elapsed so a stuck file never blocks the
    station monitor loop forever.  Returns False immediately if the file
    cannot be stat'ed at all (missing / locked by another reader).
    """
    import time
    path = str(path)
    deadline = time.monotonic() + max_wait
    last_size = None
    stable_since = None
    while True:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        now = time.monotonic()
        if size == last_size:
            if stable_since is None:
                stable_since = now
            elif now - stable_since >= stable_seconds:
                return True
        else:
            stable_since = None
        last_size = size
        if now >= deadline:
            return True  # give up: treat as readable rather than stall forever
        time.sleep(0.2)


def run_diagnostics(mes_url, watch_dir, tcp_port, db_paths):
    """Return a list of ``(name, ok, detail)`` tuples for the station self-test.

    Never raises: every check is isolated so one broken dependency cannot
    prevent the remaining diagnostics from being reported.
    """
    import socket
    import sqlite3
    import urllib.parse
    results = []
    try:
        parsed = urllib.parse.urlparse(str(mes_url or ""))
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=3):
            pass
        results.append(("MES 服务", True, f"{host}:{port}"))
    except Exception as exc:
        results.append(("MES 服务", False, str(exc)))
    try:
        ok = os.path.isdir(str(watch_dir))
        results.append(("监视目录", ok, str(watch_dir)))
    except Exception as exc:
        results.append(("监视目录", False, str(exc)))
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("0.0.0.0", int(tcp_port)))
        finally:
            server.close()
        results.append(("扫描端口", True, str(tcp_port)))
    except Exception as exc:
        results.append(("扫描端口", False, str(exc)))
    for db in (db_paths or ()):
        name = os.path.basename(str(db))
        try:
            conn = sqlite3.connect(str(db), timeout=2)
            try:
                conn.execute("SELECT 1")
            finally:
                conn.close()
            results.append((f"数据库 {name}", True, str(db)))
        except Exception as exc:
            results.append((f"数据库 {name}", False, str(exc)))
    return results

