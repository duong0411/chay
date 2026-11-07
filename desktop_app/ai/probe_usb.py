import time

import cv2
import numpy as np


def score(frame):
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean = float(g.mean())
    std = float(g.std())
    lap = float(cv2.Laplacian(g, cv2.CV_64F).var())
    b, g2, r = cv2.split(frame)
    ch = float(np.std([b.mean(), g2.mean(), r.mean()]))
    # Heuristic: JPEG-as-raw garbage → cực cao laplacian
    okish = 5 < mean < 250 and 5 < std < 90 and lap < 800
    return mean, std, lap, ch, okish


configs = []
for fourcc in [None, "MJPG", "YUY2"]:
    for wh in [(640, 480), (320, 240), (480, 360)]:
        configs.append((fourcc, wh))

for fourcc, (w, h) in configs:
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("fail open", fourcc, (w, h))
        continue
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, 15)
    time.sleep(0.25)
    ok, frame = False, None
    for _ in range(20):
        ok, frame = cap.read()
        if ok and frame is not None:
            break
        time.sleep(0.04)
    label = fourcc or "DEFAULT"
    if ok and frame is not None:
        mean, std, lap, ch, okish = score(frame)
        print(
            f"{label:7} {w}x{h} shape={frame.shape} mean={mean:.1f} std={std:.1f} "
            f"lap={lap:.0f} ok={okish}"
        )
        if okish:
            cv2.imwrite(f"models/_probe_{label}_{w}x{h}.jpg", frame)
    else:
        print(f"{label:7} {w}x{h} NO FRAME")
    cap.release()
