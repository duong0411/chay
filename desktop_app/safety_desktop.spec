# -*- mode: python ; coding: utf-8 -*-
# Lean EXE: PyQt5 + OpenCV + OpenVINO + MQTT (không đóng gói PyTorch/Ultralytics)
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = []
models = root / "models"
if models.exists():
    datas.append((str(models), "models"))

hiddenimports = [
    "openvino",
    "paho",
    "paho.mqtt",
    "paho.mqtt.client",
    "cv2",
    "numpy",
    "core",
    "core.config",
    "core.models",
    "core.device_api",
    "core.mqtt_client",
    "ai",
    "ai.fire_detector",
    "ui",
    "ui.main_window",
    "ui.styles",
    "ui.widgets",
    "ui.camera_widget",
]

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
    binaries=[],
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
