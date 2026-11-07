"""Download a higher-accuracy fire/smoke YOLO and export OpenVINO."""
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import AppConfig, models_dir  # noqa: E402

# Ưu tiên model fire+smoke chính xác hơn (YOLOv8m > n)
CANDIDATES = [
    (
        "https://huggingface.co/rabahdev/fire-smoke-yolov8n/resolve/main/best.pt",
        "YOLOv8n D-Fire — realtime CPU (~50–150ms)",
    ),
    (
        "https://huggingface.co/Namdoji/fire-smoke-yolov8m/resolve/main/best.pt",
        "YOLOv8m — chính xác hơn nhưng chậm CPU (~500–700ms)",
    ),
]


def main() -> int:
    out = models_dir()
    out.mkdir(parents=True, exist_ok=True)
    pt = out / f"{AppConfig.MODEL_NAME}.pt"
    if pt.exists():
        bak = out / f"{AppConfig.MODEL_NAME}_prev.pt"
        shutil.copy2(pt, bak)
        print(f"Backup: {bak}")

    last_err: Exception | None = None
    for url, note in CANDIDATES:
        try:
            print(f"GET {url}")
            print(f"     {note}")
            tmp = pt.with_suffix(".pt.part")
            urllib.request.urlretrieve(url, tmp)
            tmp.replace(pt)
            print(f"Saved {pt} ({pt.stat().st_size / 1e6:.1f} MB)")
            break
        except Exception as e:
            last_err = e
            print(f"Fail: {e}")
            if pt.exists():
                pt.unlink(missing_ok=True)
    else:
        print(f"Download failed: {last_err}")
        return 1

    from ultralytics import YOLO

    model = YOLO(str(pt))
    names = getattr(model, "names", {}) or {}
    if isinstance(names, dict):
        class_list = [str(names[i]) for i in sorted(names)]
    else:
        class_list = ["smoke", "fire"]
    print("Classes:", class_list)
    if not any("fire" in c.lower() for c in class_list):
        print("WARNING: model không có class fire — cân nhắc model khác")

    print("Export OpenVINO IR ...")
    export_path = model.export(format="openvino", imgsz=640, half=False)
    export_dir = Path(str(export_path))
    xmls = list(export_dir.glob("*.xml")) if export_dir.is_dir() else [export_dir]
    if not xmls:
        print("No xml from export")
        return 1
    xml = xmls[0]
    target_xml = out / f"{AppConfig.MODEL_NAME}.xml"
    target_bin = out / f"{AppConfig.MODEL_NAME}.bin"
    shutil.copy2(xml, target_xml)
    bin_src = xml.with_suffix(".bin")
    if bin_src.exists():
        shutil.copy2(bin_src, target_bin)
    (out / f"{AppConfig.MODEL_NAME}.names").write_text("\n".join(class_list) + "\n", encoding="utf-8")
    print(f"OpenVINO: {target_xml}")
    print(f"BIN: {target_bin} ({target_bin.stat().st_size / 1e6:.1f} MB)")
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
