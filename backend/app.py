"""Expose the health check and consent-gated photo validation API."""

from io import BytesIO
from pathlib import Path
import os

from flask import Flask, Request, jsonify, request
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from .face import FaceLandmarker, FaceLandmarkerUnavailable
from .images import MAX_IMAGE_BYTES, ImageError, decode_photo
from .validation import validate_photo
from .storage import Store
from .workspace import create_workspace
from .draping import GarmentSegmenter


class InMemoryUploadRequest(Request):
    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        # The request size limit bounds memory use and uploads never spool to disk.
        return BytesIO()


def _error(code: str, message: str, status: int):
    return jsonify(status="error", error={"code": code, "message": message}), status


def read_photo():
    if request.mimetype != "multipart/form-data":
        raise ImageError("invalid_content_type", "Send the photo as multipart form data.", 415)
    if request.form.getlist("consent") != ["true"]:
        raise ImageError("consent_required", "Consent is required to process your photo.", 400)
    images = request.files.getlist("image")
    if len(images) != 1 or len(request.files) != 1 or not images[0].filename:
        raise ImageError("one_image_required", "Choose one JPG, JPEG, or PNG photo.", 400)
    return decode_photo(images[0].stream, images[0].filename)


def create_app(config=None) -> Flask:
    app = Flask(__name__)
    app.request_class = InMemoryUploadRequest
    app.config.update(MAX_CONTENT_LENGTH=MAX_IMAGE_BYTES + 64 * 1024, MAX_FORM_PARTS=6,
                      DATABASE=os.getenv("GIVYN_DATABASE") or Path(app.instance_path) / "givyn.sqlite3")
    app.config.update(config or {})
    model_path = os.getenv("GIVYN_FACE_MODEL") or Path(__file__).parent / "models" / "face_landmarker.task"
    landmarker = FaceLandmarker(Path(model_path))
    garment_model = os.getenv("GIVYN_GARMENT_MODEL") or Path(__file__).parent / "models" / "selfie_multiclass_256x256.tflite"
    segmenter = GarmentSegmenter(Path(garment_model))
    app.register_blueprint(create_workspace(Store(app.config["DATABASE"]), landmarker, segmenter, read_photo))

    @app.after_request
    def prevent_caching(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def upload_too_large(_error_detail):
        return _error("upload_limit", "Upload one photo that is 10 MB or smaller.", 413)

    @app.errorhandler(BadRequest)
    def invalid_request(_error_detail):
        return _error("invalid_request", "Send the photo and consent as multipart form data.", 400)

    @app.get("/api/health")
    def health():
        if not landmarker.model_path.is_file():
            return _error("model_missing", "Install the GIVYN Face Landmarker model.", 503)
        return jsonify(status="ok")

    @app.post("/api/images/validate")
    def validate_image():
        try:
            rgb = read_photo()
            result = validate_photo(rgb, landmarker)
        except ImageError as error:
            return _error(error.code, str(error), error.status)
        except FaceLandmarkerUnavailable as error:
            app.logger.error("Face Landmarker unavailable: %s", error)
            return _error("model_unavailable", "Photo validation is temporarily unavailable.", 503)
        return jsonify(result), 200 if result["status"] == "valid" else 422

    return app
