import time
from pynput import keyboard
import scanner_helper as legacy

legacy.SCAN_COLLECTOR = legacy.ScanCollector()
legacy.LAST_KEY_TIME = time.time() * 1000
legacy._handle_scan_result = lambda sn: print(f"[LEGACY CAPTURED] {sn}", flush=True)

print("[READY] legacy scanner listener started; scan now", flush=True)
with keyboard.Listener(on_press=legacy._on_press) as listener:
    listener.join()
