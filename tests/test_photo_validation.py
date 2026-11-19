from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from backend.app import create_app
from backend.images import decode_photo
from backend.validation import validate_photo


def encoded_photo(image_format="PNG", size=(400, 400), mode="RGB"):
    stream = BytesIO()
    Image.new(mode, size).save(stream, format=image_format)
    stream.seek(0)
    return stream


class UploadValidationTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def upload(self, stream, filename="portrait.png", consent="true"):
        return self.client.post("/api/images/validate", data={"image": (stream, filename), "consent": consent})

    def test_consent_required_before_decoding(self):
        with patch("backend.app.decode_photo") as decode:
            response = self.upload(encoded_photo(), consent="false")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"]["code"], "consent_required")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        decode.assert_not_called()

    def test_rejects_unsupported_and_mismatched_file_types(self):
        for filename, code in (("photo.gif", "unsupported_type"), ("photo.jpg", "type_mismatch")):
            with self.subTest(filename=filename):
                response = self.upload(encoded_photo(), filename)
                self.assertEqual(response.status_code, 415)
                self.assertEqual(response.json["error"]["code"], code)

    def test_rejects_corrupt_images(self):
        response = self.upload(BytesIO(b"not an image"))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json["error"]["code"], "invalid_image")

    def test_small_and_transparent_images_reach_face_validation(self):
        for stream, shape in ((encoded_photo(size=(180, 240)), (240, 180, 3)),
                              (encoded_photo(mode="RGBA"), (400, 400, 3))):
            with self.subTest(shape=shape):
                photo = decode_photo(stream, "photo.png")
                self.assertEqual(photo.shape, shape)

    def test_rejects_over_limit_request(self):
        response = self.upload(BytesIO(b"x" * (11 * 1024 * 1024)))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json["error"]["code"], "upload_limit")

    def test_reports_missing_model(self):
        model = Path(__file__).with_name("missing-face-landmarker.task")
        with patch.dict("os.environ", {"GIVYN_FACE_MODEL": str(model)}):
            client = create_app().test_client()
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"]["code"], "model_missing")


class PhotoQualityTests(unittest.TestCase):
    def setUp(self):
        self.landmarks = np.full((478, 2), 0.5)
        self.landmarks[[10, 152, 33, 263]] = [[0.5, 0.15], [0.5, 0.85], [0.22, 0.4], [0.78, 0.4]]
        self.landmarker = Mock()
        self.landmarker.detect.return_value = [self.landmarks]
        regions = {
            "forehead": np.array([[.4, .2], [.6, .2], [.6, .28], [.4, .28]]),
            "cheek_left": np.array([[.25, .45], [.34, .45], [.34, .55], [.25, .55]]),
            "cheek_right": np.array([[.65, .45], [.74, .45], [.74, .55], [.65, .55]]),
        }
        self.region_patch = patch("backend.validation.sampling_regions", return_value=regions)
        self.region_patch.start()
        self.addCleanup(self.region_patch.stop)

    def test_no_face_yields_retake(self):
        self.landmarker.detect.return_value = []
        result = validate_photo(np.zeros((400, 400, 3), dtype=np.uint8), self.landmarker)
        self.assertEqual(result["status"], "retake")
        self.assertEqual(result["issues"][0]["code"], "no_face")

    def test_exposure_issues_are_advisory_when_focus_is_usable(self):
        with patch("backend.validation._face_sharpness", return_value=100):
            for value, warning in ((8, "underexposed"), (252, "overexposed")):
                with self.subTest(warning=warning):
                    result = validate_photo(np.full((400, 400, 3), value, dtype=np.uint8), self.landmarker)
                    self.assertEqual(result["status"], "valid")
                    self.assertEqual(result["issues"], [])
                    self.assertIn(warning, {item["code"] for item in result["warnings"]})

    def test_largest_face_is_selected_in_a_group_photo(self):
        smaller = .5 + (self.landmarks - .5) * .5
        self.landmarker.detect.return_value = [smaller, self.landmarks]
        with patch("backend.validation._face_sharpness", return_value=100):
            result = validate_photo(np.full((400, 400, 3), 120, dtype=np.uint8), self.landmarker)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["face_count"], 2)
        self.assertEqual(result["measurements"]["face_width_px"], 224)
        self.assertIn("multiple_faces", {item["code"] for item in result["warnings"]})

    def test_group_photo_uses_a_smaller_face_when_the_largest_is_unusable(self):
        smaller = .5 + (self.landmarks - .5) * .5
        turned = self.landmarks.copy()
        turned[1] = [1., .5]
        self.landmarker.detect.return_value = [turned, smaller]
        with patch("backend.validation._face_sharpness", return_value=100):
            result = validate_photo(np.full((400, 400, 3), 120, dtype=np.uint8), self.landmarker)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["face_index"], 1)
        self.assertEqual(result["measurements"]["face_width_px"], 112)

    def test_unfocused_face_yields_retake(self):
        result = validate_photo(np.zeros((400, 400, 3), dtype=np.uint8), self.landmarker)
        self.assertEqual(result["status"], "retake")
        self.assertEqual({issue["code"] for issue in result["issues"]}, {"blurred"})
        self.assertIn("underexposed", {item["code"] for item in result["warnings"]})
