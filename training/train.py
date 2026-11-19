"""Train transparent seasonal classifiers on public research color features.

Run from the repository root: python -m training.train
No user uploads, names, filenames, subtype labels or test features enter training.
"""

import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "training/data/features_30_per_region.csv"
CLASSES = ["Autumn", "Spring", "Summer", "Winter"]
REGIONAL_FEATURES = ["L_mean", "L_std", "a_mean", "a_std", "b_mean", "b_std",
                     "ITA_mean", "ITA_std", "Chroma_mean", "Chroma_std"]


def identity(value):
    ascii_name = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", ascii_name)


def feature_map(values, degree):
    values = np.asarray(values, dtype=float)
    if degree == 1:
        return values
    return np.column_stack([values, *[values[:, i] * values[:, j]
                                     for i in range(values.shape[1]) for j in range(i, values.shape[1])]])


def probabilities(logits):
    exponent = np.exp(logits - logits.max(axis=1, keepdims=True))
    return exponent / exponent.sum(axis=1, keepdims=True)


def metrics(y, probs):
    pred = probs.argmax(axis=1)
    matrix = np.zeros((4, 4), dtype=int)
    np.add.at(matrix, (y, pred), 1)
    recall = np.diag(matrix) / np.maximum(1, matrix.sum(axis=1))
    precision = np.diag(matrix) / np.maximum(1, matrix.sum(axis=0))
    f1 = 2 * precision * recall / np.maximum(1e-12, precision + recall)
    return {"rows": len(y), "accuracy": float(np.mean(pred == y)), "macro_f1": float(f1.mean()),
            "top_two_accuracy": float(np.mean(np.any(np.argsort(probs, axis=1)[:, -2:] == y[:, None], axis=1))),
            "log_loss": float(-np.log(np.maximum(probs[np.arange(len(y)), y], 1e-12)).mean()),
            "confusion_matrix": matrix.tolist(), "per_class_recall": dict(zip(CLASSES, recall.tolist())),
            "prediction_counts": dict(Counter(CLASSES[i] for i in pred))}


def fit(x, y, degree, penalty):
    center, scale = x.mean(axis=0), x.std(axis=0)
    scale = np.maximum(scale, 1e-6)
    expanded = feature_map((x - center) / scale, degree)
    mean, std = expanded.mean(axis=0), np.maximum(expanded.std(axis=0), 1e-6)
    design = np.column_stack([np.ones(len(x)), (expanded - mean) / std])
    targets = np.eye(4)[y]
    weights = len(y) / (4 * np.bincount(y, minlength=4))[y]

    def objective(flat):
        coef = flat.reshape(design.shape[1], 4)
        p = probabilities(design @ coef)
        loss = -(weights * np.log(np.maximum(p[np.arange(len(y)), y], 1e-12))).mean()
        loss += penalty * np.sum(coef[1:] ** 2) / 2
        gradient = design.T @ ((p - targets) * weights[:, None]) / len(y)
        gradient[1:] += penalty * coef[1:]
        return loss, gradient.ravel()

    result = minimize(objective, np.zeros(design.shape[1] * 4), jac=True, method="L-BFGS-B",
                      options={"maxiter": 1000, "ftol": 1e-10})
    if not result.success:
        raise RuntimeError(f"Optimizer did not converge: {result.message}")
    return {"kind": "softmax", "degree": degree, "penalty": penalty, "center": center.tolist(), "scale": scale.tolist(),
            "expanded_mean": mean.tolist(), "expanded_scale": std.tolist(),
            "coefficients": result.x.reshape(design.shape[1], 4).tolist(), "temperature": 1.0}


def logits(model, x):
    if model["kind"] == "forest":
        x = np.asarray(x, dtype=np.float32)
        votes = np.zeros((len(x), 4))
        for tree in model["trees"]:
            for i, sample in enumerate(x):
                node = 0
                while tree["left"][node] != -1:
                    node = tree["left"][node] if sample[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
                votes[i] += tree["value"][node]
        return np.log(np.maximum(votes / len(model["trees"]), 1e-12))
    expanded = feature_map((x - model["center"]) / model["scale"], model["degree"])
    design = np.column_stack([np.ones(len(x)), (expanded - model["expanded_mean"]) / model["expanded_scale"]])
    return design @ model["coefficients"]


def main():
    with DATA.open(encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    labels = defaultdict(set)
    for row in rows:
        if row["person_name"]:
            labels[identity(row["person_name"])].add(row["season"])
    conflict = {key for key, values in labels.items() if len(values) != 1}
    eligible = [r for r in rows if identity(r["person_name"]) and identity(r["person_name"]) not in conflict]
    # Split identities, stratified by label, before selecting any model or preprocessing.
    rng = np.random.default_rng(42)
    split = {}
    for label in CLASSES:
        people = sorted(key for key, values in labels.items() if values == {label})
        rng.shuffle(people)
        n = len(people)
        for i, person in enumerate(people):
            split[person] = "test" if i < round(n * .2) else "validation" if i < round(n * .4) else "train"
    columns = [f"{channel}_mean_{region}" for region in ("skin", "hair") for channel in ("L", "a", "b")]
    complete = [r for r in eligible if all(r[c] and np.isfinite(float(r[c])) for c in columns)]
    partitions = {s: [r for r in complete if split[identity(r["person_name"]) ] == s]
                  for s in ("train", "validation", "test")}
    # Exact duplicate measurements cannot cross the partitions either.
    seen = set()
    duplicate_count = 0
    for s in ("test", "validation", "train"):
        clean = []
        for row in partitions[s]:
            signature = tuple(row[c] for c in columns)
            if signature in seen:
                duplicate_count += 1
                continue
            seen.add(signature)
            if not all(np.isfinite(float(row[c])) for c in columns):
                raise ValueError("Non-finite measurement in eligible data")
            clean.append(row)
        partitions[s] = clean
    report = {"source_rows": len(rows), "excluded_unknown_identity": sum(not r["person_name"] for r in rows),
              "excluded_conflicting_identity_rows": len(rows) - sum(not r["person_name"] for r in rows) - len(eligible),
              "conflicting_identity_groups": len(conflict), "excluded_exact_duplicates": duplicate_count,
              "excluded_missing_regional_measurements": len(eligible) - len(complete),
              "seed": 42, "classes": CLASSES, "splits": {}, "models": {}}
    for s, records in partitions.items():
        report["splits"][s] = {"rows": len(records), "identities": len({identity(r["person_name"]) for r in records}),
                               "class_counts": dict(Counter(r["season"] for r in records))}
    artifact = {"version": "givyn-lab-1", "classes": CLASSES, "research_only": True,
                "source": "https://github.com/nypoclary/armocromia-classical-ml", "variants": {}}
    detailed = [f"{feature}_{region}" for region in ("skin", "hair") for feature in REGIONAL_FEATURES]
    for name, cols in (("skin_hair", columns), ("regional", detailed), ("skin", columns[:3])):
        arrays = {s: np.array([[float(r[c]) for c in cols] for r in records]) for s, records in partitions.items()}
        targets = {s: np.array([CLASSES.index(r["season"]) for r in records]) for s, records in partitions.items()}
        candidates = []
        for degree in (1, 2):
            for penalty in (.001, .01, .1):
                model = fit(arrays["train"], targets["train"], degree, penalty)
                score = metrics(targets["validation"], probabilities(logits(model, arrays["validation"])))
                candidates.append((score["macro_f1"], model, score))
        forest = RandomForestClassifier(n_estimators=180, max_depth=10, min_samples_leaf=5,
                                        class_weight="balanced", random_state=42, n_jobs=1)
        forest.fit(arrays["train"], targets["train"])
        exported = {"kind": "forest", "degree": None, "penalty": None, "temperature": 1.,
                    "center": arrays["train"].mean(axis=0).tolist(),
                    "scale": arrays["train"].std(axis=0).tolist(), "trees": []}
        for estimator in forest.estimators_:
            t = estimator.tree_
            value = t.value[:, 0, :]
            value = value / value.sum(axis=1, keepdims=True)
            exported["trees"].append({"left": t.children_left.tolist(), "right": t.children_right.tolist(),
                                      "feature": t.feature.tolist(), "threshold": t.threshold.tolist(), "value": value.tolist()})
        # Verify the portable predictor agrees with the fitted estimator before export.
        np.testing.assert_allclose(probabilities(logits(exported, arrays["validation"])),
                                   forest.predict_proba(arrays["validation"]), atol=1e-7)
        forest_score = metrics(targets["validation"], forest.predict_proba(arrays["validation"]))
        candidates.append((forest_score["macro_f1"], exported, forest_score))
        _, model, _ = max(candidates, key=lambda value: value[0])
        val_logits = logits(model, arrays["validation"])
        def loss(t):
            p = probabilities(val_logits / t)
            return -np.log(np.maximum(p[np.arange(len(p)), targets["validation"]], 1e-12)).mean()
        model["temperature"] = float(minimize_scalar(loss, bounds=(.7, 4), method="bounded").x)
        model["columns"] = cols
        model["min"] = np.percentile(arrays["train"], 1, axis=0).tolist()
        model["max"] = np.percentile(arrays["train"], 99, axis=0).tolist()
        report["models"][name] = {
            "candidates_validation": [{"kind": m["kind"], "degree": m["degree"], "penalty": m["penalty"], "macro_f1": score["macro_f1"]}
                                       for _, m, score in candidates],
            "selected_kind": model["kind"], "selected_degree": model["degree"], "selected_penalty": model["penalty"],
            "temperature": model["temperature"],
            "validation": metrics(targets["validation"], probabilities(val_logits / model["temperature"])),
            "test": metrics(targets["test"], probabilities(logits(model, arrays["test"]) / model["temperature"])),
        }
        artifact["variants"][name] = model
    report["test_majority_baseline"] = max(Counter(targets["test"]).values()) / len(targets["test"])
    majority = Counter(targets["train"]).most_common(1)[0][0]
    report["train_majority_baseline"] = {"class": CLASSES[majority], "test_accuracy": float(np.mean(targets["test"] == majority))}
    report["csv_sha256"] = hashlib.sha256(DATA.read_bytes()).hexdigest()
    report["limitations"] = [
        "Evaluation is on supplied regional feature rows, not the GIVYN photo extraction pipeline.",
        "Disjoint normalized supplied names reduce identity leakage; aliases and annotation errors may remain.",
        "Unknown identities are excluded. Demographic, gender and skin-depth coverage is unverified.",
        "Source skin and hair masks differ from GIVYN masks. Manual swatches also introduce domain shift.",
        "Research-use experiment; this is not professional validation or a guarantee for any individual.",
    ]
    artifact["evaluation"] = report
    (ROOT / "backend/models/seasonal_model.json").write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    (ROOT / "training/evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    manifest = [{"row": hashlib.sha256(r["path_rgb_masked"].encode()).hexdigest(),
                 "identity": hashlib.sha256(identity(r["person_name"]).encode()).hexdigest(),
                 "split": s, "season": r["season"]} for s, records in partitions.items() for r in records]
    (ROOT / "training/split_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"splits": report["splits"], "test": {name: m["test"] for name, m in report["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
