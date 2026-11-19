"""sRGB measurements, skin-depth references and facial feature sampling."""

import re
from colorsys import rgb_to_hsv

import cv2
import numpy as np

from .validation import region_pixels

HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")


def normalize_hex(value):
    if not isinstance(value, str) or not HEX.fullmatch(value.strip()):
        raise ValueError("Enter a six-digit HEX color such as #A84E68.")
    return value.strip().upper()


def rgb_from_hex(value):
    value = normalize_hex(value)
    return [int(value[index:index + 2], 16) for index in (1, 3, 5)]


def color_features(rgb):
    rgb = np.asarray(rgb, dtype=np.uint8)
    normalized = rgb.astype(np.float32) / 255
    lab = cv2.cvtColor(normalized.reshape(1, 1, 3), cv2.COLOR_RGB2Lab)[0, 0]
    hue, saturation, value = rgb_to_hsv(*(float(channel) for channel in normalized))
    return {
        "hex": "#" + "".join(f"{value:02X}" for value in rgb),
        "rgb": rgb.tolist(),
        "lab": dict(zip(("l", "a", "b"), (round(float(value), 2) for value in lab))),
        "hsv": {"h": round(hue * 360, 1), "s": round(saturation * 100, 1), "v": round(value * 100, 1)},
    }


def describe_hex(value):
    return color_features(rgb_from_hex(value))


def pixel_statistics(pixels):
    """CIE Lab statistics use float sRGB, never OpenCV's encoded uint8 Lab."""
    lab = cv2.cvtColor(np.asarray(pixels, np.float32).reshape(-1, 1, 3) / 255,
                       cv2.COLOR_RGB2Lab).reshape(-1, 3).astype(float)
    l, a, b = lab.T
    ita = np.degrees(np.arctan(np.divide(l - 50, b, out=np.zeros_like(b), where=np.abs(b) > 1e-6)))
    values = {"L": l, "a": a, "b": b, "ITA": ita, "Chroma": np.hypot(a, b)}
    return {f"{key}_{stat}": round(float(fn(value)), 5)
            for key, value in values.items() for stat, fn in (("mean", np.mean), ("std", np.std))}


def sample_hair(image, mesh, probabilities):
    if probabilities is None:
        return None
    height, width = image.shape[:2]
    confidence = cv2.resize(probabilities[1], (width, height), interpolation=cv2.INTER_LINEAR)
    labels = cv2.resize(np.argmax(probabilities, axis=0).astype(np.uint8), (width, height), interpolation=cv2.INTER_NEAREST)
    left, top = mesh.min(axis=0)
    right, bottom = mesh.max(axis=0)
    fw, fh = right - left, bottom - top
    bounds = np.zeros((height, width), np.uint8)
    x0, x1 = np.clip([left - .5 * fw, right + .5 * fw], 0, 1)
    y0, y1 = np.clip([top - .9 * fh, mesh[152, 1]], 0, 1)
    bounds[int(y0 * height):int(y1 * height), int(x0 * width):int(x1 * width)] = 1
    mask = (confidence >= .85) & (labels == 1) & (bounds == 1)
    mask = cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    # Isolate the component nearest this head; another person's hair must not
    # be pooled into the selected face in a group photo.
    count, components, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    if count > 1:
        target = np.array([(left + right) * width / 2, top * height])
        selected = min(range(1, count), key=lambda i: np.linalg.norm((centroids[i] - target) / [max(fw * width, 1), max(fh * height, 1)]))
        mask &= components == selected
    pixels = image[mask]
    if len(pixels) < max(80, .015 * fw * fh * width * height):
        return None
    return {**color_features(np.rint(np.median(pixels, axis=0))), "source": "photo",
            "sample_count": len(pixels), "statistics": pixel_statistics(pixels),
            "note": "Visible segmented hair; dyed hair, highlights and lighting can change its apparent color."}


def measure_skin(image, regions, references, labels, probabilities=None):
    patches = []
    all_pixels = []
    skin_mask = None
    if probabilities is not None:
        skin_mask = cv2.resize(probabilities[3], (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    for region, polygon in regions.items():
        pixels = region_pixels(image, np.array(polygon))
        coverage = None
        if skin_mask is not None:
            confidence = region_pixels(skin_mask[:, :, None], np.array(polygon)).ravel()
            filtered = pixels[confidence >= .75]
            coverage = round(len(filtered) / len(pixels), 3)
            if len(filtered) >= max(20, len(pixels) * .25):
                pixels = filtered
        luma = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_RGB2GRAY).ravel()
        low, high = np.percentile(luma, [15, 85])
        trimmed = pixels[(luma >= low) & (luma <= high)]
        all_pixels.append(trimmed)
        patches.append({"region": region, "sample_count": len(trimmed),
                        "confirmed_skin_fraction": coverage,
                        **color_features(np.rint(np.median(trimmed, axis=0)))})
    skin = color_features(np.rint(np.median([patch["rgb"] for patch in patches], axis=0)))
    # Depth is a lightness-only comparison. Reference chroma does not determine undertone.
    index = min(range(len(references)), key=lambda i: abs(describe_hex(references[i])["lab"]["l"] - skin["lab"]["l"]))
    spread = np.ptp([patch["lab"]["l"] for patch in patches])
    return {**skin, "patches": patches, "depth": labels[index], "monk_index": index + 1,
            "reference_hex": references[index], "patch_lightness_spread": round(float(spread), 1),
            "statistics": pixel_statistics(np.concatenate(all_pixels)), "source": "photo",
            "sample_count": sum(len(pixels) for pixels in all_pixels)}


def iris_sample(image, mesh):
    if len(mesh) < 478:
        return None
    height, width = image.shape[:2]
    points = mesh * [width - 1, height - 1]
    samples = []
    for center_index in (468, 473):
        center = points[center_index]
        radius = np.median(np.linalg.norm(points[center_index + 1:center_index + 5] - center, axis=1))
        if radius < 6:
            return None
        x, y = np.rint(center).astype(int)
        edge = int(np.ceil(radius))
        if x < edge or y < edge or x + edge >= width or y + edge >= height:
            return None
        grid_y, grid_x = np.ogrid[-edge:edge + 1, -edge:edge + 1]
        distance = np.hypot(grid_x, grid_y) / radius
        # Exclude the pupil, outer edge and upper reflections or eyelid.
        ring = (distance >= .55) & (distance <= .84) & (grid_y >= 0)
        pixels = image[y - edge:y + edge + 1, x - edge:x + edge + 1][ring]
        pixels = pixels[(pixels.max(axis=1) < 235) & (pixels.max(axis=1) > 15)]
        if len(pixels) < 10:
            return None
        samples.append(np.median(pixels, axis=0))
    lab = [color_features(np.rint(sample))["lab"] for sample in samples]
    if np.linalg.norm(np.array(list(lab[0].values())) - np.array(list(lab[1].values()))) > 14:
        return None
    return color_features(np.rint(np.median(samples, axis=0)))
