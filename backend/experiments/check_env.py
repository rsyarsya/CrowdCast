"""Check that the local AI environment is ready for CrowdCast experiments.

Run from the backend folder:
    .\\.venv\\Scripts\\python.exe experiments\\check_env.py
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"


def check_torch() -> bool:
    try:
        import torch
    except ImportError:
        print("[FAIL] torch is not installed. Install the CUDA build first (see backend/README.md).")
        return False

    print(f"[ OK ] torch {torch.__version__}")
    if not torch.cuda.is_available():
        print("[WARN] CUDA is not available: torch will run on CPU (slow).")
        print("       Likely cause: the CPU-only wheel was installed. Reinstall torch from the PyTorch CUDA index.")
        return False

    props = torch.cuda.get_device_properties(0)
    print(f"[ OK ] CUDA {torch.version.cuda}, GPU: {props.name}, VRAM: {props.total_memory / 1024**3:.1f} GB")
    return True


def check_package(name: str) -> bool:
    try:
        module = __import__(name)
    except ImportError:
        print(f"[FAIL] {name} is not installed (pip install -r requirements-ai.txt).")
        return False
    print(f"[ OK ] {name} {getattr(module, '__version__', 'unknown version')}")
    return True


def check_data() -> bool:
    if not DATA_DIR.exists():
        print(f"[WARN] {DATA_DIR} does not exist yet. Put the datasets/videos there.")
        return False

    files = [p for p in DATA_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    videos = [p for p in files if p.suffix.lower() in {".mp4", ".avi", ".mkv", ".mov"}]
    mats = [p for p in files if p.suffix.lower() == ".mat"]
    images = [p for p in files if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]
    print(f"[INFO] data/: {len(videos)} video(s), {len(images)} image(s), {len(mats)} .mat file(s)")
    for path in videos + mats:
        print(f"       - {path.relative_to(BACKEND_DIR)}")
    return bool(videos or images)


def main() -> int:
    print(f"Python {sys.version.split()[0]} on {platform.system()} {platform.release()}")
    results = [
        check_torch(),
        check_package("ultralytics"),
        check_package("cv2"),
        check_package("pandas"),
        check_package("scipy"),
        check_data(),
    ]
    ready = all(results)
    print("\nReady for Phase 1." if ready else "\nNot ready yet: fix the items above.")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
