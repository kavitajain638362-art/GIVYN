"""Evaluate capture quality before any personal color measurements are made."""

import cv2
import numpy as np

from .face import sampling_regions


MIN_SHARPNESS = 12.0

PHOTO_GUIDANCE = [
    "Face a window or another soft light source and avoid harsh shadows.",
    "Keep the forehead and cheeks visible and look straight at the camera.",
    "Use an original photo without beauty filters or heavy makeup. These cannot be reliably verified from the photo.",
]


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _result(status: str, image_size: dict, issues: list, **details) -> dict:
    return {"status": status, "image": image_size, "issues": issues, "warnings": [],
            "guidance": PHOTO_GUIDANCE, **details}


def region_pixels(image: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    points = np.rint(np.clip(polygon, 0, 1) * [width - 1, height - 1]).astype(np.int32)
    hull = cv2.convexHull(points)
    x, y, w, h = cv2.boundingRect(hull)
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, hull - np.array([x, y], dtype=np.int32), 1)
    return image[y:y + h, x:x + w][mask != 0]


def _face_sharpness(gray: np.ndarray, landmarks: np.ndarray) -> float:
    height, width = gray.shape
    points = np.rint(np.clip(landmarks, 0, 1) * [width - 1, height - 1]).astype(np.int32)
    hull = cv2.convexHull(points)
    x, y, w, h = cv2.boundingRect(hull)
    # Compare faces at the same width. Exclude the silhouette and background.
    scale = 256 / w
    size = (256, round(h * scale))
    face = cv2.resize(gray[y:y + h, x:x + w], size, interpolation=cv2.INTER_LINEAR)
    low, high = np.percentile(face, [5, 95])
    if high - low > 12:
        # Assess focus independently of moderate exposure differences.
        face = np.clip((face.astype(np.float32) - low) * 180 / (high - low) + 35, 0, 255).astype(np.uint8)
    face_hull = np.rint((hull - [x, y]) * scale).astype(np.int32)
    mask = np.zeros(face.shape, dtype=np.uint8)
    cv2.fillConvexPoly(mask, face_hull, 1)
    mask = cv2.erode(mask, np.ones((19, 19), dtype=np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
    edges = cv2.Laplacian(face, cv2.CV_32F)[mask != 0]
    return float(edges.var()) if edges.size else 0.0


def validate_photo(rgb: np.ndarray, landmarker) -> dict:
    return validate_faces(rgb, landmarker.detect(rgb))


def validate_faces(rgb: np.ndarray, faces: list[np.ndarray]) -> dict:
    if not faces:
        height, width = rgb.shape[:2]
        image_size = {"width": width, "height": height}
        return _result("retake", image_size, [_issue("no_face", "Show one clear face in the photo.")], face_count=0)
    ordered = sorted(enumerate(faces), key=lambda pair: float(np.prod(np.ptp(pair[1], axis=0))), reverse=True)
    fallback = None
    for index, mesh in ordered:
        result = _validate_face(rgb, mesh)
        result.update(face_count=len(faces), face_index=index)
        if fallback is None:
            fallback = result
        if result["status"] == "valid":
            if len(faces) > 1:
                result["warnings"].append(_issue("multiple_faces", "More than one face was detected. GIVYN analyzed the largest usable detected face."))
            return result
    return fallback


def _validate_face(rgb: np.ndarray, landmarks: np.ndarray) -> dict:
    height, width = rgb.shape[:2]
    image_size = {"width": width, "height": height}
    if not np.isfinite(landmarks).all():
        return _result("retake", image_size, [_issue("face_not_visible", "The face could not be located clearly.")])
    left, top = landmarks.min(axis=0)
    right, bottom = landmarks.max(axis=0)
    face_width = (right - left) * width
    face_height = (bottom - top) * height
    issues = []
    warnings = []
    if face_width < 28 or face_height < 32:
        return _result("retake", image_size, [_issue("face_not_visible", "The face is too small to identify usable facial details.")])
    if face_width < 160 or face_height < 180:
        warnings.append(_issue("small_face", "The face occupies a small part of this image, so the color estimate is less certain."))
    if min(left, top, 1 - right, 1 - bottom) < 0.015:
        warnings.append(_issue("partial_framing", "Some facial edges are cropped. The estimate uses the visible regions."))

    left_eye, right_eye, nose = landmarks[[33, 263, 1]] * [width, height]
    eye_vector = right_eye - left_eye
    eye_span_squared = float(eye_vector @ eye_vector)
    nose_position = float((nose - left_eye) @ eye_vector) / max(eye_span_squared, 1.0)
    roll = abs(float(np.degrees(np.arctan2(eye_vector[1], eye_vector[0]))))
    if eye_span_squared < 64 or not 0.10 <= nose_position <= 0.90 or roll > 55:
        issues.append(_issue("face_angle", "Keep your head upright and face the camera directly."))
    elif not 0.27 <= nose_position <= 0.73 or roll > 18:
        warnings.append(_issue("face_angle", "The face is angled. The estimate uses the visible skin patches."))
    if issues:
        return _result("retake", image_size, issues, face_count=1)

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    regions = sampling_regions(landmarks)
    samples = {name: region_pixels(gray, polygon) for name, polygon in regions.items()}
    regions = {name: polygon for name, polygon in regions.items() if len(samples[name]) >= 4}
    if not regions:
        return _result("retake", image_size, [_issue("face_not_visible", "The forehead and cheeks do not show enough usable facial detail.")])
    if len(regions) < 3:
        warnings.append(_issue("limited_skin", "Only some skin regions are usable. The color estimate is less certain."))
    samples = {name: samples[name] for name in regions}
    pixels = np.concatenate(list(samples.values()))
    dark_fraction = float(np.mean(pixels <= 12))
    bright_fraction = float(np.mean(pixels >= 245))
    cheek_gap = (abs(float(np.median(samples["cheek_left"])) - float(np.median(samples["cheek_right"])))
                 if "cheek_left" in samples and "cheek_right" in samples else None)
    sharpness = _face_sharpness(gray, landmarks)

    if dark_fraction > 0.25 or np.percentile(pixels, 90) < 35:
        warnings.append(_issue("underexposed", "Low light may shift the measured skin color. This result has lower confidence."))
    if bright_fraction > 0.18:
        warnings.append(_issue("overexposed", "Bright highlights may hide some skin color. This result has lower confidence."))
    if cheek_gap is not None and cheek_gap > 42:
        warnings.append(_issue("uneven_lighting", "Lighting differs across the cheeks. This result has lower confidence."))
    if sharpness < MIN_SHARPNESS:
        issues.append(_issue("blurred", "Hold the camera steady and focus on your face before taking the photo."))

    return _result(
        "retake" if issues else "valid",
        image_size,
        issues,
        face_count=1,
        warnings=warnings,
        measurements={
            "face_width_px": round(face_width),
            "face_height_px": round(face_height),
            "sharpness_laplacian_variance": round(sharpness, 2),
            "dark_pixel_fraction": round(dark_fraction, 3),
            "bright_pixel_fraction": round(bright_fraction, 3),
            "cheek_brightness_gap": round(cheek_gap, 2) if cheek_gap is not None else None,
        },
        regions={name: np.round(np.clip(polygon, 0, 1), 5).tolist() for name, polygon in regions.items()},
    )
