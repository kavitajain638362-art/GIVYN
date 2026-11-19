"""Decode a bounded, color-managed photograph in memory."""

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError


MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 24_000_000
SUPPORTED_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG"}


class ImageError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


def decode_photo(stream, filename: str) -> np.ndarray:
    expected_format = SUPPORTED_FORMATS.get(Path(filename).suffix.lower())
    if expected_format is None:
        raise ImageError("unsupported_type", "Choose a JPG, JPEG, or PNG photo.", 415)

    data = stream.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageError("file_too_large", "Choose a photo that is 10 MB or smaller.", 413)
    try:
        with Image.open(BytesIO(data), formats=["JPEG", "PNG"]) as image:
            if image.format != expected_format:
                raise ImageError("type_mismatch", "Use a filename that matches the photo format.", 415)
            if image.width * image.height > MAX_PIXELS:
                raise ImageError("too_many_pixels", "Choose a photo under 24 megapixels.", 413)
            if getattr(image, "is_animated", False):
                raise ImageError("animated_image", "Choose a single still photo.", 415)
            image.verify()

        with Image.open(BytesIO(data), formats=[expected_format]) as image:
            oriented = ImageOps.exif_transpose(image)
            alpha = (oriented.convert("RGBA").getchannel("A")
                     if "A" in oriented.getbands() or "transparency" in oriented.info else None)

            profile = oriented.info.get("icc_profile")
            if profile:
                if oriented.mode in {"P", "RGBA"}:
                    oriented = oriented.convert("RGB")
                try:
                    oriented = ImageCms.profileToProfile(
                        oriented, BytesIO(profile), ImageCms.createProfile("sRGB"), outputMode="RGB"
                    )
                except (OSError, ValueError, ImageCms.PyCMSError) as error:
                    raise ImageError("invalid_profile", "Export the photo in sRGB and try again.") from error
            photo = oriented.convert("RGB")
            if alpha is not None:
                photo = Image.composite(photo, Image.new("RGB", photo.size, (128, 128, 128)), alpha)
            return np.array(photo)
    except Image.DecompressionBombError as error:
        raise ImageError("too_many_pixels", "Choose a photo under 24 megapixels.", 413) from error
    except ImageError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise ImageError("invalid_image", "The photo could not be read. Try a fresh JPG or PNG.") from error
