import os
import sys
import time

import tkinter as tk
from pywinauto import Desktop


def classify(image):
    red = 0
    yellow = 0
    for r, g, b in image.convert("RGB").resize((120, 80)).getdata():
        if r > 110 and g < 80 and b < 80:
            red += 1
        if r > 180 and g > 170 and b < 80:
            yellow += 1
    return red, yellow


if __name__ == "__main__":
    sys.path.insert(0, os.environ["AUTO_LINE_ROOT"])
    from station_scan_alarm import show_blocking_alarm

    root = tk.Tk()
    root.withdraw()
    show_blocking_alarm(
        root, "NG", "6G7W00246A", "56 Supersonic: upstream ICT L2 NG"
    )
    root.update()
    alarm = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
    # Bind directly to the Tk alarm HWND. Process-wide enumeration is
    # unreliable when the hidden root has not been mapped by Windows yet.
    window = Desktop(backend="win32").window(handle=alarm.winfo_id())
    samples = []
    sizes = []
    center_colors = []
    for _ in range(12):
        root.update()
        image = window.capture_as_image()
        sizes.append(image.size)
        center_colors.append(image.convert("RGB").getpixel((image.width // 2, image.height // 2)))
        samples.append(classify(image))
        time.sleep(0.25)
    for child in alarm.winfo_children():
        if isinstance(child, tk.Button):
            child.invoke()
            break
    root.update()
    root.destroy()
    red_frames = sum(red > yellow for red, yellow in samples)
    yellow_frames = sum(yellow > red for red, yellow in samples)
    print("SAMPLES", samples)
    print("SIZES", sizes)
    print("CENTER_COLORS", center_colors)
    print("RED_FRAMES", red_frames)
    print("YELLOW_FRAMES", yellow_frames)
    if red_frames == 0 or yellow_frames == 0:
        raise SystemExit("FLASH_TEST_FAILED")
    print("PYWINAUTO_NG_FLASH_TEST=PASS")
