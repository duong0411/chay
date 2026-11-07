"""GStreamer camera open (Windows ksvideosrc / Linux v4l2src).

OpenCV pip mặc định KHÔNG có GStreamer. Module này:
  - tự detect OpenCV có GST hay không
  - nếu có → mở cam bằng pipeline low-latency (drop=1, max-buffers=1)
  - nếu không → trả None để fallback DirectShow
"""
from __future__ import annotations

import sys
from functools import lru_cache

import cv2


@lru_cache(maxsize=1)
def gstreamer_available() -> bool:
    try:
        info = cv2.getBuildInformation()
    except Exception:
        return False
    for line in info.splitlines():
        if "GStreamer" in line and "YES" in line.upper():
            return True
    # Thử mở pipeline giả — một số build khai báo sai
    try:
        cap = cv2.VideoCapture("videotestsrc num-buffers=1 ! fakesink", cv2.CAP_GSTREAMER)
        ok = bool(cap.isOpened())
        cap.release()
        return ok
    except Exception:
        return False


def _fourcc_mjpg_caps(width: int, height: int, fps: int) -> str:
    return (
        f"image/jpeg,width={width},height={height},framerate={fps}/1"
    )


def build_pipeline(
    index: int,
    *,
    width: int = 640,
    height: int = 480,
    fps: int = 15,
    usb_like: bool = False,
) -> str:
    """
    Pipeline low-latency giống appsink drop=true max-buffers=1.
    Windows: ksvideosrc | Linux: v4l2src
    """
    w, h, f = int(width), int(height), int(fps)
    sink = (
        "videoconvert ! video/x-raw,format=BGR ! "
        "appsink name=appsink emit-signals=true max-buffers=1 drop=true sync=false"
    )

    if sys.platform.startswith("win"):
        # Ưu tiên MJPG trên USB giá rẻ (Shopee GENERAL WEBCAM) — nhẹ bandwidth
        if usb_like:
            return (
                f"ksvideosrc device-index={index} do-timestamp=true ! "
                f"{_fourcc_mjpg_caps(w, h, f)} ! jpegdec ! {sink}"
            )
        return (
            f"ksvideosrc device-index={index} do-timestamp=true ! "
            f"video/x-raw,width={w},height={h},framerate={f}/1 ! {sink}"
        )

    # Linux
    return (
        f"v4l2src device=/dev/video{index} ! "
        f"image/jpeg,width={w},height={h},framerate={f}/1 ! jpegdec ! {sink}"
    )


def open_gstreamer(
    index: int,
    *,
    width: int = 640,
    height: int = 480,
    fps: int = 15,
    usb_like: bool = False,
) -> cv2.VideoCapture | None:
    if not gstreamer_available():
        return None

    pipelines = [
        build_pipeline(index, width=width, height=height, fps=fps, usb_like=usb_like),
    ]
    # Fallback: raw (không MJPG) nếu cam không hỗ trợ JPEG
    if usb_like:
        pipelines.append(
            build_pipeline(index, width=width, height=height, fps=fps, usb_like=False)
        )
    # Thử giảm resolution nếu vẫn fail
    if usb_like and (width > 320 or height > 240):
        pipelines.append(
            build_pipeline(index, width=320, height=240, fps=min(fps, 15), usb_like=True)
        )

    for pipe in pipelines:
        cap = cv2.VideoCapture(pipe, cv2.CAP_GSTREAMER)
        if not cap.isOpened():
            cap.release()
            continue
        ok = False
        for _ in range(12):
            ok, frame = cap.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                return cap
        cap.release()
    return None
