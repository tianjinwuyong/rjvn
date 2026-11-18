"""Decode motherboard/daughterboard QR codes and forward them to Depanel TCP 1003."""

import os
import re
import socket
import sys
import time

try:
    import cv2
except ImportError:
    print("ERROR: OpenCV is missing. Install opencv-python.", flush=True)
    raise


CAMERA_INDEX = int(os.environ.get("DEPANEL_CAMERA_INDEX", "0"))
DEPANEL_HOST = os.environ.get("DEPANEL_HOST", "127.0.0.1")
DEPANEL_PORT = int(os.environ.get("DEPANEL_PORT", "1003"))
REARM_SECONDS = float(os.environ.get("DEPANEL_QR_REARM_SECONDS", "2.0"))
SHOW_PREVIEW = os.environ.get("DEPANEL_CAMERA_PREVIEW", "1") != "0"


def normalize_qr(value):
    value = re.sub(r"\s+", "", str(value or "")).upper()
    if len(value) == 10 and value.isalnum():
        return value
    if len(value) == 14 and value.isdigit():
        return value
    return ""


def send_to_depanel(code):
    with socket.create_connection((DEPANEL_HOST, DEPANEL_PORT), timeout=3) as client:
        client.sendall((code + "\r\n").encode("ascii"))
        client.settimeout(3)
        return client.recv(128).decode("ascii", "replace").strip()


def main():
    camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not camera.isOpened():
        raise RuntimeError(
            f"Camera {CAMERA_INDEX} cannot be opened. It may be used exclusively "
            "by the cutting application."
        )

    detector = cv2.QRCodeDetector()
    last_code = ""
    last_seen = 0.0
    print(
        f"Camera {CAMERA_INDEX} -> {DEPANEL_HOST}:{DEPANEL_PORT}; "
        "press Q or ESC to stop.",
        flush=True,
    )
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                print("WARN: camera frame unavailable", flush=True)
                time.sleep(0.2)
                continue

            decoded, points, _ = detector.detectAndDecode(frame)
            code = normalize_qr(decoded)
            now = time.monotonic()
            if code:
                if code != last_code or now - last_seen >= REARM_SECONDS:
                    try:
                        reply = send_to_depanel(code)
                        print(f"{code} -> {reply}", flush=True)
                        if reply.startswith("OK"):
                            last_code = code
                    except Exception as exc:
                        print(f"{code} -> ERROR {exc}", flush=True)
                last_seen = now
            elif now - last_seen >= REARM_SECONDS:
                last_code = ""

            if SHOW_PREVIEW:
                if points is not None:
                    pts = points.astype(int).reshape(-1, 2)
                    for index in range(len(pts)):
                        cv2.line(
                            frame,
                            tuple(pts[index]),
                            tuple(pts[(index + 1) % len(pts)]),
                            (0, 255, 0),
                            2,
                        )
                cv2.putText(
                    frame,
                    code or "WAITING FOR QR",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0) if code else (0, 200, 255),
                    2,
                )
                cv2.imshow("Depanel Camera QR Bridge", frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")):
                    break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL: {exc}", flush=True)
        if getattr(sys, "frozen", False):
            input("Press Enter to close...")
        raise
