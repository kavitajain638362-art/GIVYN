"""Portable, locally trained seasonal model with uncertainty diagnostics.

Only a JSON artifact is loaded; no downloaded pickle or executable model code.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).with_name("models") / "seasonal_model.json"


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.is_file():
        return None
    try:
        artifact = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        logging.getLogger(__name__).error("Seasonal model unavailable: %s", error)
        return None
    if artifact.get("version") != "givyn-lab-1":
        logging.getLogger(__name__).error("Unsupported seasonal model version")
        return None
    return artifact


def predict(model, values):
    x = np.atleast_2d(np.asarray(values, float))
    if not np.isfinite(x).all():
        raise ValueError("Seasonal input contains non-finite measurements")
    if model["kind"] == "forest":
        x = x.astype(np.float32)
        votes = np.zeros((len(x), 4))
        for tree in model["trees"]:
            for i, sample in enumerate(x):
                node = 0
                while tree["left"][node] != -1:
                    node = tree["left"][node] if sample[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
                votes[i] += tree["value"][node]
        logits = np.log(np.maximum(votes / len(model["trees"]), 1e-12))
    else:
        x = (x - model["center"]) / model["scale"]
        if model["degree"] == 2:
            x = np.column_stack([x, *[x[:, i] * x[:, j] for i in range(x.shape[1]) for j in range(i, x.shape[1])]])
        x = (x - model["expanded_mean"]) / model["expanded_scale"]
        logits = np.column_stack([np.ones(len(x)), x]) @ model["coefficients"]
    logits /= model["temperature"]
    exponent = np.exp(logits - logits.max(axis=1, keepdims=True))
    return exponent / exponent.sum(axis=1, keepdims=True)


def means(sample):
    stats = sample.get("statistics")
    return [stats[f"{c}_mean"] for c in ("L", "a", "b")] if stats else [sample["lab"][c] for c in ("l", "a", "b")]


def estimate_season(skin, hair, warnings):
    artifact = load_model()
    if artifact is None:
        return None
    # Mean-only model has the closest shared definition for a manual color and a
    # segmented color. Eye-region training means are NOT iris-color measurements.
    variant = "skin_hair" if hair else "skin"
    model = artifact["variants"][variant]
    values = np.array(means(skin) + (means(hair) if hair else []))
    probs = predict(model, values)[0]
    order = np.argsort(-probs)
    best, second = (int(i) for i in order[:2])
    # Deterministic sensitivity checks, not extra training samples or accuracy.
    perturbations = [values]
    for i in range(len(values)):
        delta = np.zeros(len(values))
        delta[i] = 2 if i % 3 == 0 else 1
        perturbations.extend([values + delta, values - delta])
    stress = predict(model, perturbations)
    stability = float(np.mean(np.argmax(stress, axis=1) == best))
    lower, upper = np.array(model["min"]), np.array(model["max"])
    cushion = .15 * (upper - lower)
    unusual = [model["columns"][i] for i in range(len(values))
               if values[i] < lower[i] - cushion[i] or values[i] > upper[i] + cushion[i]]
    caution = ["Research model: the photo extraction pipeline has not been independently validated."]
    if not hair:
        caution.append("Hair could not be measured reliably. Add a natural hair color; skin alone has weak seasonal evidence.")
    elif hair.get("source") == "manual":
        caution.append("Hair uses your chosen color swatch; it may differ from the hair measurements in the training data.")
    if unusual:
        caution.append("Some measured values fall outside the model's usual training range.")
    if stability < .85:
        caution.append("Small changes to the measurements change the leading season.")
    if any(w.get("code") != "multiple_faces" for w in warnings):
        caution.append("Photo conditions reduce the reliability of color measurements.")
    margin = float(probs[best] - probs[second])
    weak = not hair or probs[best] < .7 or margin < .2 or unusual or stability < .85 or len(caution) > 1
    result = {
        "name": artifact["classes"][best], "score": round(float(probs[best]) * 100, 1),
        "ranked": [{"name": artifact["classes"][i], "score": round(float(probs[i]) * 100, 1), "rules": []} for i in order],
        "confidence": "Low" if weak else "Moderate", "tentative": True,
        "alternative": artifact["classes"][second], "margin": round(margin * 100, 1),
        "method": "trained_model", "version": artifact["version"], "variant": variant,
        "score_label": "Model support (%)", "cautions": caution,
        "stability": {"agreement": round(stability * 100, 1), "checks": len(perturbations),
                      "description": "Leading season agreement after ±2 L* or ±1 a*/b* measurement changes; this is not accuracy."},
        "evaluation": {"test": artifact["evaluation"]["models"][variant]["test"],
                       "training_rows": artifact["evaluation"]["splits"]["train"]["rows"],
                       "test_identities": artifact["evaluation"]["splits"]["test"]["identities"],
                       "source": artifact["source"], "scope": "Held-out source feature rows; GIVYN photo accuracy is unverified."},
        "reason": f"{artifact['classes'][best]} has the most support from the trained skin"
                  f"{' and hair' if hair else ''} CIE Lab model. {artifact['classes'][second]} is the next closest possibility. "
                  "This is a tentative palette to compare with real drapes.",
        "rules": [],
    }
    # Regional ablation exposes which input changes support. It is a model
    # diagnostic against the training mean, not a causal claim about appearance.
    contributions = []
    for label, start in (("Skin", 0), ("Hair", 3)):
        if start >= len(values):
            continue
        replaced = values.copy()
        replaced[start:start + 3] = np.array(model["center"])[start:start + 3]
        change = float(probs[best] - predict(model, replaced)[0, best]) * 100
        contributions.append(f"{label} measurement changes support for {result['name']} by {change:+.1f} percentage points "
                             "compared with replacing that region by the training average; this is model sensitivity, not a causal explanation.")
    result["rules"] = contributions
    return result
