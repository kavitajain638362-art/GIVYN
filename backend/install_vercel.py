"""Install the Flask dependencies in Vercel's build virtual environment."""

from subprocess import run
import sys


def install(*args):
    run([sys.executable, "-m", "pip", *args], check=True)


if __name__ == "__main__":
    run([sys.executable, "-m", "ensurepip"], check=True)
    install("install", "-r", "requirements.txt")
    if sys.platform == "linux":
        # MediaPipe declares the GUI wheel. GIVYN uses its vision API and can
        # use the equivalent headless cv2 module on the server without libGL.
        install("uninstall", "-y", "opencv-contrib-python")
        install("install", "--no-deps", "opencv-contrib-python-headless>=4.12,<5")
    run([sys.executable, "-c", "import cv2, mediapipe, psycopg; import backend.app"], check=True)
