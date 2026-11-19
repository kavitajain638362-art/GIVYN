"""A transient garment mask for recoloring clothes while preserving other regions."""

from base64 import b64encode
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from .vision_runtime import load_mediapipe


class GarmentSegmenter:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None
        self._lock = Lock()

    def segment(self, image):
        if not self.model_path.is_file():
            return None
        mp = load_mediapipe()

        height, width = image.shape[:2]
        scale = min(1, 1024 / max(height, width))
        photo = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        with self._lock:
            if self._model is None:
                options = mp.tasks.vision.ImageSegmenterOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
                    output_category_mask=False,
                    output_confidence_masks=True,
                )
                self._model = mp.tasks.vision.ImageSegmenter.create_from_options(options)
            result = self._model.segment(mp.Image(image_format=mp.ImageFormat.SRGB, data=photo))
            # Google model classes are background, hair, body-skin, face-skin, clothes, others.
            probabilities = np.stack([mask.numpy_view().copy() for mask in result.confidence_masks])
        return probabilities

    def mask(self, image, chin, probabilities=None):
        if probabilities is None:
            probabilities = self.segment(image)
        if probabilities is None:
            return None
        cloth = (probabilities[4] >= .75) & (np.argmax(probabilities, axis=0) == 4)
        cloth[:int(np.ceil(chin * cloth.shape[0])), :] = False
        mask = cv2.erode(cloth.astype(np.uint8) * 255, np.ones((3, 3), dtype=np.uint8))
        if np.mean(mask > 0) < .005:
            return None
        success, encoded = cv2.imencode(".png", mask)
        if not success:
            return None
        return "data:image/png;base64," + b64encode(encoded).decode("ascii")
