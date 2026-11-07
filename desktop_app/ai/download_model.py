"""
Download YOLO fire/smoke weights and convert to OpenVINO IR.

Usage:
  py -3.12 ai/download_model.py
"""
from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import AppConfig, models_dir  # noqa: E402


# Prefer higher-accuracy fire+smoke weights first.
MODEL_URLS = [
    # Nano realtime trên CPU laptop; m (chậm ~600ms+) chỉ dùng khi máy mạnh
    "https://huggingface.co/rabahdev/fire-smoke-yolov8n/resolve/main/best.pt",
    "https://huggingface.co/Namdoji/fire-smoke-yolov8m/resolve/main/best.pt",
    "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
]


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"      GET {url}")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(dest)


def main() -> int:
    out_dir = models_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    pt_path = out_dir / f"{AppConfig.MODEL_NAME}.pt"

    print(f"[1/3] Model dir: {out_dir}")
    if not pt_path.exists():
        print("[2/3] Downloading fire/smoke YOLO weights...")
        last_err: Exception | None = None
        for url in MODEL_URLS:
            try:
                _download(url, pt_path)
                print(f"      Saved {pt_path}")
                if "yolov8n.pt" in url and "fire" not in url:
                    print("      WARNING: Đây là COCO yolov8n fallback — độ chính xác cháy thấp.")
                break
            except Exception as e:
                last_err = e
                print(f"      Fail: {e}")
                if pt_path.exists():
                    pt_path.unlink(missing_ok=True)
        else:
            print(f"Download failed: {last_err}")
            return 1
    else:
        print(f"[2/3] Found existing {pt_path}")

    print("[3/3] Export OpenVINO IR ...")
    try:
        from ultralytics import YOLO

        model = YOLO(str(pt_path))
        names = getattr(model, "names", None) or {}
        if isinstance(names, dict) and names:
            class_list = [str(names[i]) for i in sorted(names)]
        else:
            class_list = ["smoke", "fire"]

        export_path = model.export(format="openvino", imgsz=640, half=False)
        export_dir = Path(str(export_path))
        xmls = list(export_dir.glob("*.xml")) if export_dir.is_dir() else [export_dir]
        if xmls:
            xml = xmls[0]
            target_xml = out_dir / f"{AppConfig.MODEL_NAME}.xml"
            target_bin = out_dir / f"{AppConfig.MODEL_NAME}.bin"
            shutil.copy2(xml, target_xml)
            bin_src = xml.with_suffix(".bin")
            if bin_src.exists():
                shutil.copy2(bin_src, target_bin)
            names_file = out_dir / f"{AppConfig.MODEL_NAME}.names"
            names_file.write_text("\n".join(class_list) + "\n", encoding="utf-8")
            print(f"      OpenVINO model: {target_xml}")
            print(f"      Classes: {', '.join(class_list)}")
        else:
            print(f"      Export folder: {export_dir}")
    except Exception as e:
        print(f"OpenVINO export failed (app vẫn chạy bằng ultralytics .pt): {e}")
        return 0

    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
