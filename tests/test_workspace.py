"""Regression coverage for the read/write boundary between browser profiles."""

import hashlib
from pathlib import Path
from secrets import token_urlsafe
from unittest import TestCase
from uuid import uuid4

from backend.app import create_app
from backend.inference import compare_color, knowledge
from backend.storage import Store
from backend.workspace import COOKIE


class BrowserWorkspaceTests(TestCase):
    def setUp(self):
        self.database = Path(__file__).parent / f"test-{uuid4().hex}.sqlite3"
        self.addCleanup(self.database.unlink, missing_ok=True)
        self.app = create_app({"TESTING": True, "DATABASE": self.database})
        self.owner = self.app.test_client()
        self.visitor = self.app.test_client()
        token = token_urlsafe(32)
        self.owner.set_cookie(COOKIE, token)
        self.user_id = hashlib.sha256(token.encode("ascii")).hexdigest()
        self.store = Store(self.database)
        result = self.store.save_analysis(self.user_id, {
            "season": {"name": "Spring"}, "palette": {"Accents": []},
            "drape_anchor": {"chin": [0.5, 0.6], "face_width": 0.3},
        })
        self.analysis_id = result["id"]
        self.path = f"/api/analyses/{self.analysis_id}"

    def test_history_analysis_and_report_are_scoped_to_owner(self):
        self.assertEqual(self.visitor.get(self.path).status_code, 404)
        self.assertEqual(self.visitor.get(self.path + "/report.pdf").status_code, 404)
        self.assertEqual(self.visitor.delete(self.path).status_code, 404)
        self.assertEqual(self.visitor.get("/api/history").json["analyses"], [])
        saved = self.owner.get(self.path)
        self.assertEqual(saved.status_code, 200)
        self.assertNotIn("drape_anchor", saved.json)

    def test_deleting_analysis_cascades_to_palette_and_comparisons(self):
        self.store.save_comparison(self.user_id, self.analysis_id, "metals", {"colors": []})
        self.assertEqual(len(self.owner.get("/api/history").json["comparisons"]), 1)
        self.assertEqual(self.owner.delete(self.path).status_code, 204)
        result = self.owner.get("/api/history").json
        self.assertEqual(result["comparisons"], [])
        self.assertEqual(result["analyses"], [])
        with self.store.connection() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM palettes").fetchone()[0], 0)

    def test_a_palette_color_matches_itself_in_a_batch_of_candidates(self):
        season = "Spring"
        palette = knowledge()["seasons"][season]["palette"]
        target = palette["Complementary"][0]
        result = compare_color(target["hex"], {"season": {"name": season}, "palette": palette})
        self.assertEqual(result["distance"], 0)
        self.assertEqual(result["nearest"]["hex"], target["hex"])
        self.assertEqual(result["level"], "Highly compatible")
