# -*- mode: python ; coding: utf-8 -*-
# Lean EXE: PyQt5 + OpenCV + OpenVINO + MQTT (không đóng gói PyTorch/Ultralytics)
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

block_cipher = None
root = Path(SPECPATH)

datas = []
binaries = []
hiddenimports = [
    "openvino",
    "openvino.runtime",
    "paho",
    "paho.mqtt",
    "paho.mqtt.client",
    "cv2",
    "numpy",
    "core",
    "core.config",
    "core.models",
    "core.camera_enum",
    "core.gst_capture",
    "core.device_api",
    "core.mqtt_client",
    "ai",
    "ai.fire_detector",
    "ui",
    "ui.main_window",
    "ui.styles",
    "ui.widgets",
    "ui.camera_widget",
    "cv2_enumerate_cameras",
]

# Bundle OpenVINO plugins/libs so EXE can compile YOLO IR
try:
    ov_datas, ov_bins, ov_hidden = collect_all("openvino")
    datas += ov_datas
    binaries += ov_bins
    hiddenimports += ov_hidden
except Exception:
    binaries += collect_dynamic_libs("openvino")

models = root / "models"
if models.exists():
    datas.append((str(models), "models"))

excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "ultralytics",
    "tensorflow",
    "tensorboard",
    "paddle",
    "paddlepaddle",
    "matplotlib",
    "scipy",
    "pandas",
    "sklearn",
    "skimage",
    "IPython",
    "notebook",
    "jupyter",
    "sympy",
    "numba",
    "llvmlite",
    "onnx",
    "onnxruntime",
    "tkinter",
    "_tkinter",
]

a = Analysis(
    ["main.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SafetyRemoteDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
