"""Locate faces and map the forehead and cheeks from MediaPipe mesh landmarks."""

from pathlib import Path
from threading import Lock

import cv2
import numpy as np


SAMPLE_LANDMARKS = {
    "forehead": (109, 10, 338, 336, 9, 107),
    "cheek_left": (116, 117, 118, 101, 205, 187),
    "cheek_right": (345, 346, 347, 330, 425, 411),
}


class FaceLandmarkerUnavailable(RuntimeError):
    pass


class FaceLandmarker:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None
        self._lock = Lock()

    def detect(self, rgb: np.ndarray) -> list[np.ndarray]:
        try:
            import mediapipe as mp
        except (ImportError, OSError) as error:
            raise FaceLandmarkerUnavailable("The MediaPipe runtime could not be loaded.") from error

        height, width = rgb.shape[:2]
        if max(height, width) > 1600:
            scale = 1600 / max(height, width)
            rgb = cv2.resize(rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        photo = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # A single task instance serves requests serially within this process.
        with self._lock:
            if self._model is None:
                if not self.model_path.is_file():
                    raise FaceLandmarkerUnavailable("The Face Landmarker model is missing.")
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=5,
                )
                try:
                    self._model = mp.tasks.vision.FaceLandmarker.create_from_options(options)
                except (OSError, RuntimeError, ValueError) as error:
                    raise FaceLandmarkerUnavailable("The Face Landmarker model could not be loaded.") from error
            result = self._model.detect(photo)
        return [np.array([(point.x, point.y) for point in mesh]) for mesh in result.face_landmarks]


def sampling_regions(landmarks: np.ndarray) -> dict[str, np.ndarray]:
    regions = {}
    for name, indices in SAMPLE_LANDMARKS.items():
        outline = landmarks[list(indices)]
        center = outline.mean(axis=0)
        # Inset the outlines to give hairlines, brows and under-eye edges room.
        regions[name] = center + (outline - center) * 0.55
    return regions
