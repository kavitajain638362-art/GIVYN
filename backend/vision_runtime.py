"""Load the native libraries used by the CPU MediaPipe tasks on Vercel Linux."""

from functools import lru_cache
from pathlib import Path
import sys


@lru_cache(maxsize=1)
def load_mediapipe():
    directory = Path(__file__).with_name("models") / "native-linux-x86_64"
    if sys.platform == "linux" and directory.is_dir():
        import ctypes

        # MediaPipe's wheel links these SONAMEs even for CPU-only inference.
        for library in ("libGLdispatch.so.0", "libGLESv2.so.2", "libEGL.so.1"):
            ctypes.CDLL(str(directory / library), mode=ctypes.RTLD_GLOBAL)
    import mediapipe

    return mediapipe
