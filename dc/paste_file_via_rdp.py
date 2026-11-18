import os
import re
import sys
import time
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


def paste(ip, path):
    window = Desktop(backend="win32").window(title_re=re.escape(ip) + ".*")
    window.maximize()
    window.set_focus()
    time.sleep(1.0)
    rect = window.rectangle()
    window.click_input(coords=(20, rect.height() - 22))
    time.sleep(0.8)
    send_keys(r"D:\stations", pause=0.05)
    send_keys("{ENTER}")
    time.sleep(2.5)
    send_keys("^v")
    time.sleep(5)


if __name__ == "__main__":
    paste(sys.argv[1], sys.argv[2])
    print("RDP_FILE_PASTE_SENT", sys.argv[1], os.path.basename(sys.argv[2]))
