"""Automatic-line result-file trigger; never polls tester data."""
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class _ExcelHandler(FileSystemEventHandler):
    def __init__(self, watcher):
        self.watcher = watcher

    def on_created(self, event):
        self.watcher.notify(event.src_path, event.is_directory)

    def on_modified(self, event):
        self.watcher.notify(event.src_path, event.is_directory)

    def on_moved(self, event):
        self.watcher.notify(event.dest_path, event.is_directory)


class ExcelEventWatcher:
    RESULT_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}

    def __init__(self, directory, callback, debounce_seconds=2.0,
                 stable_checks=1, stable_interval=0.1):
        self.directory = Path(directory)
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.stable_checks = stable_checks
        self.stable_interval = stable_interval
        self.observer = None
        self.timers = {}
        self.lock = threading.Lock()

    def start(self):
        self.stop()
        if not self.directory.exists():
            return False
        self.observer = Observer()
        self.observer.schedule(_ExcelHandler(self), str(self.directory), recursive=True)
        self.observer.start()
        return True

    def notify(self, path, is_directory=False):
        changed = Path(path)
        if (is_directory or changed.name.startswith("~$")
                or changed.suffix.lower() not in self.RESULT_EXTENSIONS):
            return
        with self.lock:
            key = str(changed.resolve())
            old_timer = self.timers.pop(key, None)
            if old_timer:
                old_timer.cancel()
            timer = threading.Timer(
                self.debounce_seconds, self._dispatch_when_stable, args=(changed, key),
            )
            timer.daemon = True
            self.timers[key] = timer
            timer.start()

    def _dispatch_when_stable(self, path, key):
        previous = None
        stable = 0
        for _ in range(max(6, self.stable_checks * 4)):
            try:
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
            except (FileNotFoundError, PermissionError, OSError):
                signature = None
            if signature is not None and signature == previous:
                stable += 1
                if stable >= self.stable_checks:
                    with self.lock:
                        self.timers.pop(key, None)
                    self.callback()
                    return
            else:
                stable = 0
                previous = signature
            time.sleep(self.stable_interval)
        with self.lock:
            self.timers.pop(key, None)
        # A later filesystem event retries the file. Do not parse a file that
        # is still being written or locked by the tester.

    def stop(self):
        with self.lock:
            timers = list(self.timers.values())
            self.timers.clear()
        for timer in timers:
            timer.cancel()
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None
