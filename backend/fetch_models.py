"""Fetch the pinned MediaPipe models when building from a clean checkout."""

import hashlib
from io import BytesIO
from pathlib import Path
import platform
import sys
import tarfile
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
DEBIAN_POOL = "https://deb.debian.org/debian/pool/main/libg/libglvnd/"
LINUX_LIBS = (
    ("libglvnd0", "b6da5b153dd62d8b5e5fbe25242db1fc05c068707c365db49abda8c2427c75f8",
     "libGLdispatch.so.0.0.0", "libGLdispatch.so.0"),
    ("libgles2", "07b2f51b8aa3c8d6d928133cd46087bd8793d0d67c203f09fc289d45a2cf5f47",
     "libGLESv2.so.2.1.0", "libGLESv2.so.2"),
    ("libegl1", "fe4d8b39f6e6fe1a32ab1efd85893553eaa9cf3866aa668ccf355f585b37d523",
     "libEGL.so.1.1.0", "libEGL.so.1"),
)


def checked_download(url, expected_hash):
    with urlopen(url, timeout=30) as response:
        content = response.read(20 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != expected_hash:
        raise RuntimeError(f"Dependency checksum mismatch: {url}")
    return content


def fetch_models():
    directory = Path(__file__).resolve().with_name("models")
    directory.mkdir(exist_ok=True)
    for name, (url, expected_hash) in MODELS.items():
        path = directory / name
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash:
            continue
        path.write_bytes(checked_download(MODEL_ROOT + url, expected_hash))


def debian_data(package):
    # A .deb is an ar archive with one compressed data tarball. Read only that
    # member and copy only the explicitly named libraries below.
    if not package.startswith(b"!<arch>\n"):
        raise ValueError("Invalid Debian package")
    position = 8
    while position < len(package):
        header = package[position:position + 60]
        length = int(header[48:58])
        start = position + 60
        if header[:16].strip().startswith(b"data.tar."):
            return BytesIO(package[start:start + length])
        position = start + length + length % 2
    raise ValueError("Debian package data tarball is missing")


def fetch_linux_runtime(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for package, checksum, member, library in LINUX_LIBS:
        data = checked_download(f"{DEBIAN_POOL}{package}_1.6.0-1_amd64.deb", checksum)
        with tarfile.open(fileobj=debian_data(data)) as archive:
            with archive.extractfile(f"./usr/lib/x86_64-linux-gnu/{member}") as source:
                (directory / library).write_bytes(source.read())
            if package == "libglvnd0":
                with archive.extractfile("./usr/share/doc/libglvnd0/copyright") as source:
                    (directory / "LICENSE.txt").write_bytes(source.read())


if __name__ == "__main__":
    fetch_models()
    if sys.platform == "linux" and platform.machine() == "x86_64":
        fetch_linux_runtime(Path(__file__).resolve().with_name("models") / "native-linux-x86_64")
