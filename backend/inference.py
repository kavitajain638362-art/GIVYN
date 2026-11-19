"""Knowledge-base driven estimates and the color comparison rules."""

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from skimage.color import deltaE_ciede2000

from .colors import describe_hex, iris_sample, measure_skin, sample_hair
from .seasonal_model import estimate_season


@lru_cache(maxsize=1)
def knowledge():
    return json.loads(Path(__file__).with_name("knowledge_base.json").read_text(encoding="utf-8"))


LIMITATIONS = [
    "A single photo measures appearance under its lighting, camera processing and white balance.",
    "Skin depth is an approximate lightness match to a Monk reference swatch.",
    "Undertone and contrast classes are heuristic estimates. Seasonal matches use an experimental research model when available.",
    "Model support is not a guarantee or validated personal accuracy. A photo cannot establish a definitive seasonal identity.",
]


def estimate_undertone(skin, observation):
    lab = [patch["lab"] for patch in skin["patches"]]
    balance = [float(np.clip((patch["b"] - 1.25 * patch["a"] - 4) / 16, -1, 1)) for patch in lab]
    hues = [float(np.clip((patch["hsv"]["h"] - 22) / 14, -1, 1)) for patch in skin["patches"]]
    signals = [.7 * color_balance + .3 * hue for color_balance, hue in zip(balance, hues)]
    image_signal = float(np.median(signals))
    # Correlated hue and red/yellow signals are combined, then checked for patch agreement.
    spread = float(np.ptp(signals))
    warmth = image_signal
    if observation in {"warm", "cool", "mixed"}:
        cue = {"warm": 1., "cool": -1., "mixed": 0.}[observation]
        warmth = .55 * image_signal + .45 * cue
    cutoff = knowledge()["thresholds"]["warmth_direction"]
    undertone = "Warm" if warmth > cutoff else "Cool" if warmth < -cutoff else "Neutral"
    confidence = "Moderate" if abs(warmth) >= .48 and spread < .34 else "Low"
    if observation in {"warm", "cool"} and spread < .34 and abs(warmth) >= .65:
        confidence = "Higher"
    reason = (
        f"Visible skin samples show an sRGB hue of {skin['hsv']['h']}° and a CIE Lab "
        f"red/yellow balance of a* {skin['lab']['a']} and b* {skin['lab']['b']}. "
        f"The patch signal varies by {spread:.2f} on a −1 to +1 scale."
    )
    if observation:
        reason += f" Your drape observation ({observation}) contributed to the estimate."
    if undertone == "Neutral":
        reason += " The warm and cool evidence stays near the decision boundary."
    return {"category": undertone, "confidence": confidence, "warmth": round(warmth, 3), "reason": reason}


def evaluate_contrast(skin, hair, eyes, eye_source):
    features = {"skin": skin, "hair": hair, "eyes": eyes}
    lightness = {name: sample["lab"]["l"] for name, sample in features.items() if sample}
    if len(lightness) == 1:
        return {"level": "Uncertain", "spread": None, "lightness": lightness, "eye_source": None,
                "reason": "Add your natural hair and eye colors to estimate facial contrast."}
    spread = round(max(lightness.values()) - min(lightness.values()), 1)
    thresholds = knowledge()["thresholds"]
    level = "Low" if spread < thresholds["contrast_medium"] else "Medium" if spread < thresholds["contrast_high"] else "High"
    reason = f"The available colors span {spread} CIE L* points across " + ", ".join(lightness) + "."
    if len(lightness) < 3:
        reason += " This is a partial estimate. Add the missing natural color for a fuller comparison."
    if eye_source == "photo":
        reason += " Eye color comes from a small iris sample and can be overridden."
    return {"level": level, "spread": spread, "lightness": lightness, "eye_source": eye_source, "reason": reason}


def infer_season(skin, undertone, contrast):
    kb = knowledge()
    features = {"warmth": undertone["warmth"], "contrast": contrast["spread"],
                "saturation": skin["hsv"]["s"], "lightness": skin["lab"]["l"], "brightness": skin["hsv"]["v"]}
    scales = {"warmth": 2, "contrast": 75, "saturation": 75, "lightness": 100, "brightness": 100}
    facts = {"undertone": undertone["category"], "contrast": contrast["level"],
             "saturation": "muted" if features["saturation"] < 35 else "clear"}
    total_weight = sum(weight for name, weight in kb["weights"].items() if features[name] is not None)
    ranked = []
    for name, entry in kb["seasons"].items():
        fit = sum(weight * max(0, 1 - abs(features[key] - entry["target"][key]) / scales[key])
                  for key, weight in kb["weights"].items() if features[key] is not None) / total_weight
        fired = [rule for rule in kb["rules"] if rule["season"] == name
                 and all(facts[key] == value for key, value in rule["when"].items())]
        score = min(100, 100 * (fit + sum(rule["bonus"] for rule in fired)))
        ranked.append({"name": name, "score": round(score, 1),
                       "rules": [rule["explanation"] for rule in fired]})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    best, second = ranked[:2]
    margin = round(best["score"] - second["score"], 1)
    weak = margin < 6 or undertone["confidence"] == "Low" or len(contrast["lightness"]) < 3
    return {**best, "description": kb["seasons"][best["name"]]["description"],
            "confidence": "Low" if weak else "Moderate" if margin < 14 else "Higher",
            "alternative": second["name"] if weak or margin < 10 else None, "margin": margin, "ranked": ranked,
            "reason": f"{best['name']} fits the combined {undertone['category'].lower()} tendency, "
                      f"{contrast['level'].lower()} contrast, photo saturation, brightness and skin lightness most closely."}


def analyze_colors(image, validation, mesh, hair_hex, eye_hex, observation, probabilities=None):
    kb = knowledge()
    skin = measure_skin(image, validation["regions"], kb["monk_hex"], kb["depth_labels"], probabilities)
    undertone = estimate_undertone(skin, observation)
    capture_warnings = list(validation.get("warnings", []))
    if any(p.get("confirmed_skin_fraction") is not None and p["confirmed_skin_fraction"] < .25 for p in skin["patches"]):
        capture_warnings.append({"code": "skin_region_uncertain", "message": "Some forehead or cheek pixels could not be confirmed as skin. Treat the color estimate cautiously."})
    if any(warning["code"] != "multiple_faces" for warning in capture_warnings):
        undertone["confidence"] = "Low"
        undertone["reason"] += " Photo conditions reduce confidence in this estimate."
    hair = {**describe_hex(hair_hex), "source": "manual"} if hair_hex else sample_hair(image, mesh, probabilities)
    eyes = describe_hex(eye_hex) if eye_hex else iris_sample(image, mesh)
    if eyes:
        eyes["source"] = "manual" if eye_hex else "photo"
    contrast = evaluate_contrast(skin, hair, eyes, "manual" if eye_hex else "photo" if eyes else None)
    season = estimate_season(skin, hair, capture_warnings)
    if season is None:
        season = infer_season(skin, undertone, contrast)
        season.update(method="rules_fallback", tentative=True, confidence="Low",
                      score_label="Heuristic fit", cautions=["Trained model unavailable. This is a provisional rule-based palette."])
    else:
        season["description"] = kb["seasons"][season["name"]]["description"]
    if hair:
        contrast["reason"] += f" Hair color source: {hair['source']}."
    left, right = float(mesh[:, 0].min()), float(mesh[:, 0].max())
    return {
        "skin": skin, "undertone": undertone, "contrast": contrast, "season": season,
        "features": {"hair": hair, "eyes": eyes}, "palette": build_palette(season["name"], skin, contrast),
        "limitations": LIMITATIONS, "capture_warnings": capture_warnings, "knowledge_version": kb["version"],
        "drape_anchor": {"chin": mesh[152].clip(0, 1).tolist(), "face_width": right - left},
    }


def build_palette(season, skin, contrast):
    entry = knowledge()["seasons"][season]
    preferred_gap = (contrast["spread"] if contrast["spread"] is not None else entry["target"]["contrast"]) * .62
    result = {}
    for group, colors in entry["palette"].items():
        result[group] = []
        for color in colors:
            gap = round(abs(describe_hex(color["hex"])["lab"]["l"] - skin["lab"]["l"]))
            contrast_label = "gentle" if gap < 24 else "moderate" if gap < 47 else "strong"
            context = {
                "Complementary": f"Part of the {season} core palette, with {contrast_label} contrast against your photo sample.",
                "Neutrals": f"A quieter base for {season} colors, with {contrast_label} contrast against your photo sample.",
                "Accents": f"An accent for the {season} palette that gives {contrast_label} contrast against your photo sample.",
                "Use with care": f"This {color['temperature'].lower()} swatch lies outside the {season} core. Compare it with a recommended color.",
            }
            explanation = f"{context[group]} HSV value {color['brightness']}%, saturation {color['saturation']}%."
            result[group].append({**color, "explanation": explanation, "lightness_gap": gap})
        if group != "Use with care":
            group_gap = preferred_gap + (9 if group == "Accents" else 0)
            result[group].sort(key=lambda item: abs(item["lightness_gap"] - group_gap))
    return result


def temperature(features):
    lab, hsv = features["lab"], features["hsv"]
    if hsv["s"] < 12:
        return "Warm" if lab["b"] > 7 else "Cool" if lab["b"] < -6 else "Neutral"
    hue = hsv["h"]
    return "Warm" if (hue < 72 and lab["b"] > 4) or (hue < 105 and lab["b"] > 23) else "Cool"


def compare_color(hex_value, analysis):
    color = describe_hex(hex_value)
    known_colors = [swatch for group in analysis["palette"].values() for swatch in group]
    known_colors += [swatch for preset in knowledge()["comparisons"] for swatch in preset["colors"]]
    name = next((swatch["name"] for swatch in known_colors if swatch["hex"] == color["hex"]), "Custom color")
    swatches = [swatch for group, items in analysis["palette"].items() if group != "Use with care" for swatch in items]
    candidate_labs = [list(describe_hex(item["hex"])["lab"].values()) for item in swatches]
    distances = deltaE_ciede2000(np.array(candidate_labs), np.array([list(color["lab"].values())]))
    index = int(np.argmin(distances))
    nearest = swatches[index]
    distance = float(distances[index])
    temp = temperature(color)
    target = "Warm" if analysis["season"]["name"] in {"Spring", "Autumn"} else "Cool"
    temperature_fit = 100 if temp == target else 75 if temp == "Neutral" else 42
    saturation_fit = max(0, 100 - abs(color["hsv"]["s"] - nearest["saturation"]))
    score = round(.76 * max(0, 100 - 2.6 * distance) + .14 * temperature_fit + .10 * saturation_fit)
    thresholds = knowledge()["thresholds"]
    level = ("Highly compatible" if score >= thresholds["highly_compatible"] else
             "Compatible" if score >= thresholds["compatible"] else "Less harmonious")
    return {**color, "name": name, "temperature": temp, "score": score, "level": level, "nearest": nearest, "distance": round(distance, 1),
            "explanation": f"{nearest['name']} is the closest favorable {analysis['season']['name']} swatch "
                           f"at ΔE00 {distance:.1f}. The score also uses the {temp.lower()} tendency and saturation difference."}


def compare_metals(analysis):
    warmth = analysis["undertone"]["warmth"]
    season_warmth = knowledge()["seasons"][analysis["season"]["name"]]["target"]["warmth"]
    target = .75 * warmth + .25 * season_warmth
    return sorted([
        {**metal, "score": round(100 - 46 * abs(metal["warmth"] - target)),
         "explanation": f"{metal['name']} has a {'warm' if metal['warmth'] > .4 else 'cool' if metal['warmth'] < 0 else 'soft warm'} color cast. "
                        f"It is compared with your {analysis['undertone']['category'].lower()} undertone estimate and {analysis['season']['name']} palette."}
        for metal in knowledge()["metals"]
    ], key=lambda metal: metal["score"], reverse=True)
