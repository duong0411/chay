from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.config import AppConfig, models_dir
from core.models import Detection


class FireDetector:
    """YOLOv8 fire/smoke detector via OpenVINO runtime (CPU)."""

    def __init__(self, conf: float = AppConfig.INFER_CONF, iou: float = AppConfig.INFER_IOU) -> None:
        self.conf = conf
        self.iou = iou
        self.ready = False
        self.backend = "none"
        self.error = ""
        self.class_names: list[str] = ["fire", "smoke"]
        self._compiled = None
        self._input_name = ""
        self._input_size = (640, 640)
        self._ultralytics = None
        self._load()

    def _find_ov_model(self) -> Path | None:
        root = models_dir()
        candidates = [
            root / f"{AppConfig.MODEL_NAME}.xml",
            root / "yolov8n_fire.xml",
            root / "best.xml",
            root / "fire.xml",
        ]
        for p in candidates:
            if p.exists() and p.with_suffix(".bin").exists():
                return p
        # Nested OpenVINO export folders from ultralytics
        for xml in root.rglob("*.xml"):
            if xml.with_suffix(".bin").exists() and "fire" in xml.stem.lower():
                return xml
        for xml in root.rglob("*.xml"):
            if xml.with_suffix(".bin").exists():
                return xml
        return None

    def _find_pt_model(self) -> Path | None:
        root = models_dir()
        for name in (f"{AppConfig.MODEL_NAME}.pt", "yolov8n_fire.pt", "best.pt", "fire.pt"):
            p = root / name
            if p.exists():
                return p
        for p in root.rglob("*.pt"):
            return p
        return None

    def _load(self) -> None:
        import sys

        errors: list[str] = []
        ov_path = self._find_ov_model()
        if ov_path is not None:
            try:
                from openvino import Core

                core = Core()
                model = core.read_model(str(ov_path))
                try:
                    self._compiled = core.compile_model(
                        model,
                        "CPU",
                        {"INFERENCE_NUM_THREADS": str(AppConfig.OPENVINO_THREADS)},
                    )
                except Exception:
                    self._compiled = core.compile_model(model, "CPU")
                inp = self._compiled.inputs[0]
                self._input_name = inp.get_any_name()
                shape = list(inp.shape)
                # NCHW
                if len(shape) == 4:
                    self._input_size = (int(shape[3]), int(shape[2]))
                self.backend = "openvino"
                self.ready = True
                names_file = ov_path.with_suffix(".names")
                if names_file.exists():
                    self.class_names = [
                        ln.strip() for ln in names_file.read_text(encoding="utf-8").splitlines() if ln.strip()
                    ]
                return
            except Exception as e:
                errors.append(f"OpenVINO: {e}")
        else:
            errors.append(f"Không thấy .xml/.bin trong {models_dir()}")

        # EXE lean build không đóng gói ultralytics — chỉ thử khi chạy source
        frozen = bool(getattr(sys, "frozen", False))
        pt = self._find_pt_model()
        if pt is not None and not frozen:
            try:
                from ultralytics import YOLO

                self._ultralytics = YOLO(str(pt))
                names = getattr(self._ultralytics, "names", None) or {}
                if isinstance(names, dict) and names:
                    self.class_names = [names[i] for i in sorted(names)]
                self.backend = "ultralytics"
                self.ready = True
                return
            except Exception as e:
                errors.append(f"Ultralytics: {e}")
        elif pt is not None and frozen:
            errors.append("EXE cần OpenVINO (.xml/.bin). Copy thư mục models cạnh file .exe")

        self.error = " | ".join(errors) if errors else "Chưa có model. Chạy: python ai/download_model.py"

    def _letterbox(self, img: np.ndarray, new_shape: tuple[int, int]) -> tuple[np.ndarray, float, tuple[int, int]]:
        h, w = img.shape[:2]
        nh, nw = new_shape[1], new_shape[0]
        r = min(nh / h, nw / w)
        tw, th = int(round(w * r)), int(round(h * r))
        resized = cv2.resize(img, (tw, th), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((nh, nw, 3), 114, dtype=np.uint8)
        dw, dh = (nw - tw) // 2, (nh - th) // 2
        canvas[dh : dh + th, dw : dw + tw] = resized
        return canvas, r, (dw, dh)

    def _nms(self, boxes: list[list[float]], scores: list[float], iou_thr: float) -> list[int]:
        if not boxes:
            return []
        b = np.array(boxes, dtype=np.float32)
        s = np.array(scores, dtype=np.float32)
        x1, y1, x2, y2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
        areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
        order = s.argsort()[::-1]
        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            order = order[1:][iou <= iou_thr]
        return keep

    def _parse_ov(self, out: Any, r: float, dwdh: tuple[int, int], orig_shape: tuple[int, int]) -> list[Detection]:
        # Ultralytics OpenVINO export usually: (1, 4+nc, N) or (1, N, 4+nc)
        arr = np.array(out)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.shape[0] < arr.shape[1] and arr.shape[0] <= 84:
            arr = arr.T
        # arr: (N, 4+nc)
        boxes: list[list[float]] = []
        scores: list[float] = []
        labels: list[str] = []
        dw, dh = dwdh
        oh, ow = orig_shape
        for row in arr:
            if row.shape[0] < 5:
                continue
            cx, cy, w, h = row[:4]
            cls_scores = row[4:]
            cls_id = int(np.argmax(cls_scores))
            conf = float(cls_scores[cls_id])
            if conf < self.conf:
                continue
            x1 = (cx - w / 2 - dw) / r
            y1 = (cy - h / 2 - dh) / r
            x2 = (cx + w / 2 - dw) / r
            y2 = (cy + h / 2 - dh) / r
            x1 = max(0, min(ow - 1, x1))
            y1 = max(0, min(oh - 1, y1))
            x2 = max(0, min(ow - 1, x2))
            y2 = max(0, min(oh - 1, y2))
            name = self.class_names[cls_id] if cls_id < len(self.class_names) else str(cls_id)
            boxes.append([x1, y1, x2, y2])
            scores.append(conf)
            labels.append(name)
        keep = self._nms(boxes, scores, self.iou)
        return [
            Detection(
                label=labels[i],
                conf=scores[i],
                xyxy=(int(boxes[i][0]), int(boxes[i][1]), int(boxes[i][2]), int(boxes[i][3])),
            )
            for i in keep
        ]

    def _enhance_for_fire(self, frame_bgr: np.ndarray) -> np.ndarray:
        """CLAHE nhẹ — giúp lửa/khói rõ hơn trên webcam USB tối, không đổi kích thước model."""
        try:
            lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l2 = clahe.apply(l)
            return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)
        except Exception:
            return frame_bgr

    def _filter_dets(self, dets: list[Detection], frame_shape: tuple[int, int]) -> list[Detection]:
        """Giữ box lửa/khói đủ lớn + đủ conf — bỏ nhiễu nhỏ."""
        oh, ow = frame_shape
        min_area = max(64.0, 0.0008 * ow * oh)
        out: list[Detection] = []
        for d in dets:
            if not self.is_fire_label(d.label):
                continue
            if d.conf < self.conf:
                continue
            x1, y1, x2, y2 = d.xyxy
            area = max(0, x2 - x1) * max(0, y2 - y1)
            if area < min_area:
                continue
            out.append(d)
        out.sort(key=lambda d: d.conf, reverse=True)
        return out

    def infer(self, frame_bgr: np.ndarray) -> tuple[list[Detection], float]:
        if frame_bgr is None or not self.ready:
            return [], 0.0
        t0 = time.perf_counter()
        # Letterbox 640 đúng train size. CLAHE chỉ khi frame tối (webcam USB thiếu sáng)
        mean = float(frame_bgr.mean()) if frame_bgr.size else 128.0
        src = self._enhance_for_fire(frame_bgr) if mean < 55.0 else frame_bgr
        dets: list[Detection] = []

        if self.backend == "openvino" and self._compiled is not None:
            letter, r, dwdh = self._letterbox(src, self._input_size)
            rgb = cv2.cvtColor(letter, cv2.COLOR_BGR2RGB)
            blob = rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
            result = self._compiled([blob])
            out = result[self._compiled.outputs[0]]
            dets = self._parse_ov(out, r, dwdh, frame_bgr.shape[:2])
        elif self.backend == "ultralytics" and self._ultralytics is not None:
            res = self._ultralytics.predict(
                source=src,
                conf=self.conf,
                iou=self.iou,
                verbose=False,
            )[0]
            if res.boxes is not None:
                for box in res.boxes:
                    xyxy = box.xyxy[0].tolist()
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = self.class_names[cls_id] if cls_id < len(self.class_names) else str(cls_id)
                    dets.append(
                        Detection(
                            label=name,
                            conf=conf,
                            xyxy=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
                        )
                    )

        dets = self._filter_dets(dets, frame_bgr.shape[:2])
        ms = (time.perf_counter() - t0) * 1000.0
        return dets, ms

    @staticmethod
    def is_fire_label(label: str) -> bool:
        low = label.lower()
        return any(k in low for k in ("fire", "flame", "smoke", "cháy", "lửa", "khói"))

    def draw(self, frame_bgr: np.ndarray, detections: list[Detection], *, inplace: bool = False) -> np.ndarray:
        out = frame_bgr if inplace else frame_bgr.copy()
        for d in detections:
            x1, y1, x2, y2 = d.xyxy
            color = (42, 42, 255) if self.is_fire_label(d.label) else (28, 159, 255)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            tag = f"{d.label} {d.conf:.0%}"
            (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(out, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), color, -1)
            cv2.putText(
                out,
                tag,
                (x1 + 4, y1 - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
        return out
