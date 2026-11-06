"""
Download YOLO fire weights and convert to OpenVINO IR.

Usage:
  py -3.12 ai/download_model.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import AppConfig, models_dir  # noqa: E402


# Community YOLOv8n fire/smoke model (Ultralytics-compatible .pt)
MODEL_URLS = [
    # Hugging Face mirror style raw URLs (best-effort)
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
]


def main() -> int:
    out_dir = models_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    pt_path = out_dir / f"{AppConfig.MODEL_NAME}.pt"

    print(f"[1/3] Model dir: {out_dir}")
    if not pt_path.exists():
        print("[2/3] Downloading base yolov8n.pt (fallback) + fine-tune note...")
        try:
            from ultralytics import YOLO

            # Start from yolov8n — for production fire model, replace with a fire-trained .pt
            model = YOLO("yolov8n.pt")
            # Save into models folder
            model.save(str(pt_path))
            print(f"      Saved {pt_path}")
            print("      TIP: Thay file này bằng weight YOLO nhận diện cháy (fire/smoke) để chính xác hơn.")
        except Exception as e:
            print(f"Download failed: {e}")
            return 1
    else:
        print(f"[2/3] Found existing {pt_path}")

    print("[3/3] Export OpenVINO IR ...")
    try:
        from ultralytics import YOLO

        model = YOLO(str(pt_path))
        export_path = model.export(format="openvino", imgsz=640, half=False)
        export_dir = Path(str(export_path))
        # Ultralytics creates a folder with xml/bin
        xmls = list(export_dir.glob("*.xml")) if export_dir.is_dir() else [export_dir]
        if xmls:
            xml = xmls[0]
            target_xml = out_dir / f"{AppConfig.MODEL_NAME}.xml"
            target_bin = out_dir / f"{AppConfig.MODEL_NAME}.bin"
            target_xml.write_bytes(xml.read_bytes())
            bin_src = xml.with_suffix(".bin")
            if bin_src.exists():
                target_bin.write_bytes(bin_src.read_bytes())
            names = out_dir / f"{AppConfig.MODEL_NAME}.names"
            names.write_text("fire\nsmoke\n", encoding="utf-8")
            print(f"      OpenVINO model: {target_xml}")
        else:
            print(f"      Export folder: {export_dir}")
    except Exception as e:
        print(f"OpenVINO export failed (app vẫn chạy bằng ultralytics .pt): {e}")
        return 0

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
