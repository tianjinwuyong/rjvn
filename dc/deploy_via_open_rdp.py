import sys
import time
import base64
import re
import win32clipboard
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


def clipboard_text(value):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(value, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()


def run_remote(ip, command):
    matches = Desktop(backend="win32").windows(
        title_re=re.escape(ip) + ".*", top_level_only=True
    )
    if not matches:
        raise RuntimeError(f"RDP window not found: {ip}")
    # Multiple RDP tabs/windows can exist for one station.  Use the first
    # visible top-level session rather than failing with an ambiguous match.
    window = next((w for w in matches if w.is_visible()), matches[0])
    # `windows()` already returns realized top-level wrappers; older
    # pywinauto DialogWrapper instances do not expose `wait()`.
    window.maximize()
    window.set_focus()
    time.sleep(1.2)
    # Scanner agents can capture all keyboard input. Close the foreground
    # agent before opening the deployment shell.
    send_keys("%{F4}")
    time.sleep(1.5)
    rect = window.rectangle()
    window.click_input(coords=(32, rect.height() - 48))
    time.sleep(0.8)
    send_keys("powershell", pause=0.05)
    time.sleep(1.0)
    send_keys("^+{ENTER}")
    time.sleep(1.8)
    send_keys("%y")
    time.sleep(1.5)
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    clipboard_text(
        "powershell.exe -NoProfile -ExecutionPolicy Bypass "
        f"-EncodedCommand {encoded}"
    )
    send_keys("^v")
    time.sleep(0.4)
    send_keys("{ENTER}")


if __name__ == "__main__":
    run_remote(sys.argv[1], sys.argv[2])
    print("RDP_COMMAND_SENT", sys.argv[1])
