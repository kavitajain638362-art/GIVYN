"""Fetch the pinned MediaPipe models when building from a clean checkout."""

import hashlib
from pathlib import Path
from urllib.request import urlopen

MODEL_ROOT = "https://storage.googleapis.com/mediapipe-models/"
MODELS = {
    "face_landmarker.task": (
        "face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
    ),
    "selfie_multiclass_256x256.tflite": (
        "image_segmenter/selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite",
        "c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0",
    ),
}


def fetch_models():
    directory = Path(__file__).resolve().with_name("models")
    directory.mkdir(exist_ok=True)
    for name, (url, expected_hash) in MODELS.items():
        path = directory / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash:
            continue
        with urlopen(MODEL_ROOT + url, timeout=30) as response:
            content = response.read(20 * 1024 * 1024)
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise RuntimeError(f"MediaPipe model checksum mismatch: {name}")
        path.write_bytes(content)


if __name__ == "__main__":
    fetch_models()
