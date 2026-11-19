"""Data leakage, model-collapse and measurement regression checks.

These verify implementation and the recorded feature benchmark, not real-world
photo accuracy. The latter needs an independent, expert-labeled image set.
"""

import csv
import hashlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import numpy as np

from backend.colors import color_features, pixel_statistics, sample_hair
from backend.seasonal_model import estimate_season, load_model, predict

ROOT = Path(__file__).resolve().parents[1]


class LearnedModelTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = load_model()
        cls.manifest = json.loads((ROOT / "training/split_manifest.json").read_text())
        with (ROOT / "training/data/features_30_per_region.csv").open(encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        cls.rows = {hashlib.sha256(r["path_rgb_masked"].encode()).hexdigest(): r for r in rows}

    def test_supplied_identities_and_images_do_not_cross_splits(self):
        for key in ("row", "identity"):
            sets = {s: {r[key] for r in self.manifest if r["split"] == s} for s in ("train", "validation", "test")}
            self.assertFalse(sets["train"] & sets["test"])
            self.assertFalse(sets["train"] & sets["validation"])
            self.assertFalse(sets["validation"] & sets["test"])

    def test_runtime_reproduces_held_out_confusion_matrix_without_collapsing(self):
        records = [r for r in self.manifest if r["split"] == "test"]
        for variant, model in self.artifact["variants"].items():
            with self.subTest(variant=variant):
                x = [[float(self.rows[r["row"]][c]) for c in model["columns"]] for r in records]
                p = predict(model, x)
                np.testing.assert_allclose(p.sum(axis=1), 1)
                predicted = p.argmax(axis=1)
                matrix = np.zeros((4, 4), int)
                labels = [self.artifact["classes"].index(r["season"]) for r in records]
                np.add.at(matrix, (labels, predicted), 1)
                self.assertEqual(matrix.tolist(), self.artifact["evaluation"]["models"][variant]["test"]["confusion_matrix"])
                self.assertEqual(len(set(predicted)), 4)

    def test_inference_exposes_sources_uncertainty_and_weak_skin_only_evidence(self):
        sample = color_features([170, 121, 94])
        hair = {**color_features([50, 34, 28]), "source": "manual"}
        answer = estimate_season(sample, hair, [])
        self.assertTrue(answer["tentative"])
        self.assertEqual(answer["confidence"], "Low")
        self.assertEqual(answer["method"], "trained_model")
        self.assertTrue(answer["alternative"])
        self.assertEqual(answer["stability"]["checks"], 13)
        self.assertTrue(any("swatch" in c for c in answer["cautions"]))
        missing = estimate_season(sample, None, [])
        self.assertEqual(missing["variant"], "skin")
        self.assertEqual(missing["confidence"], "Low")
        self.assertTrue(any("skin alone" in c.lower() for c in missing["cautions"]))

    def test_missing_artifact_is_explicit_and_nonfinite_inputs_fail(self):
        with patch("backend.seasonal_model.load_model", return_value=None):
            self.assertIsNone(estimate_season(color_features([120, 100, 90]), None, []))
        with self.assertRaises(ValueError):
            predict(self.artifact["variants"]["skin"], [float("nan"), 2, 3])


class MeasurementTests(TestCase):
    def test_float_lab_has_physical_lightness_range(self):
        black = pixel_statistics(np.zeros((100, 3), np.uint8))
        white = pixel_statistics(np.full((100, 3), 255, np.uint8))
        self.assertAlmostEqual(black["L_mean"], 0, places=2)
        self.assertAlmostEqual(white["L_mean"], 100, places=2)
        self.assertLess(abs(white["a_mean"]), .1)
        self.assertLess(abs(white["b_mean"]), .1)

    def test_hair_sampler_excludes_background_and_unconfident_predictions(self):
        image = np.full((200, 200, 3), [240, 30, 30], np.uint8)
        image[20:70, 60:140] = [45, 35, 28]
        probs = np.zeros((6, 200, 200), np.float32)
        probs[0] = 1
        probs[0, 20:70, 60:140] = .03
        probs[1, 20:70, 60:140] = .97
        mesh = np.tile([.5, .5], (478, 1))
        mesh[0], mesh[1], mesh[152] = [.3, .3], [.7, .7], [.5, .7]
        hair = sample_hair(image, mesh, probs)
        self.assertEqual(hair["rgb"], [45, 35, 28])
        self.assertEqual(hair["source"], "photo")
        probs[1] *= .5
        self.assertIsNone(sample_hair(image, mesh, probs))
