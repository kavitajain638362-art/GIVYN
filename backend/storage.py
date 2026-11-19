"""SQLite persistence for a browser-scoped profile and its color history."""

import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS analyses_user_history ON analyses(user_id, id DESC);
CREATE TABLE IF NOT EXISTS palettes (
    analysis_id INTEGER PRIMARY KEY REFERENCES analyses(id) ON DELETE CASCADE,
    colors TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS saved_colors (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    hex TEXT NOT NULL,
    name TEXT NOT NULL,
    PRIMARY KEY (user_id, hex)
);
CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mode TEXT NOT NULL,
    result TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS comparisons_analysis_history ON comparisons(analysis_id, id DESC);
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            yield db

    def save_analysis(self, user, result):
        record = {key: value for key, value in result.items() if key not in {"palette", "drape_anchor"}}
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user,))
            row = db.execute("INSERT INTO analyses (user_id, result) VALUES (?, ?) RETURNING id, created_at",
                             (user, json.dumps(record))).fetchone()
            db.execute("INSERT INTO palettes (analysis_id, colors) VALUES (?, ?)",
                       (row["id"], json.dumps(result["palette"])))
        return {"id": row["id"], "created_at": row["created_at"].replace(" ", "T") + "Z", **result}

    def get_analysis(self, user, analysis_id):
        with self.connection() as db:
            row = db.execute("""
                SELECT analyses.*, palettes.colors FROM analyses JOIN palettes ON palettes.analysis_id = analyses.id
                WHERE analyses.user_id = ? AND analyses.id = ?
            """, (user, analysis_id)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "created_at": row["created_at"].replace(" ", "T") + "Z",
                **json.loads(row["result"]), "palette": json.loads(row["colors"])}

    def history(self, user):
        with self.connection() as db:
            analyses = db.execute("SELECT id, created_at, result FROM analyses WHERE user_id = ? ORDER BY id DESC",
                                  (user,)).fetchall()
            colors = db.execute("SELECT hex, name FROM saved_colors WHERE user_id = ? ORDER BY name, hex",
                                (user,)).fetchall()
        return {
            "analyses": [{"id": row["id"], "created_at": row["created_at"].replace(" ", "T") + "Z",
                          "season": json.loads(row["result"])["season"]["name"]} for row in analyses],
            "favorites": [dict(row) for row in colors], "comparisons": self.comparisons(user),
        }

    def save_comparison(self, user, analysis_id, mode, result):
        with self.connection() as db:
            cursor = db.execute("""
                INSERT INTO comparisons (analysis_id, mode, result)
                SELECT id, ?, ? FROM analyses WHERE id = ? AND user_id = ?
            """, (mode, json.dumps(result), analysis_id, user))
            return cursor.rowcount > 0

    def comparisons(self, user, analysis_id=None):
        query = """
            SELECT comparisons.* FROM comparisons JOIN analyses ON analyses.id = comparisons.analysis_id
            WHERE analyses.user_id = ?
        """
        args = (user,)
        if analysis_id is not None:
            query += " AND analyses.id = ?"
            args += (analysis_id,)
        with self.connection() as db:
            rows = db.execute(query + " ORDER BY comparisons.id DESC LIMIT 30", args).fetchall()
        return [{"id": row["id"], "analysis_id": row["analysis_id"],
                 "created_at": row["created_at"].replace(" ", "T") + "Z", "mode": row["mode"],
                 "result": json.loads(row["result"])} for row in rows]

    def save_color(self, user, hex_value, name):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO users (id) VALUES (?)", (user,))
            db.execute("""
                INSERT INTO saved_colors (user_id, hex, name) VALUES (?, ?, ?)
                ON CONFLICT(user_id, hex) DO UPDATE SET name = excluded.name
            """, (user, hex_value, name))

    def delete_color(self, user, hex_value):
        with self.connection() as db:
            db.execute("DELETE FROM saved_colors WHERE user_id = ? AND hex = ?", (user, hex_value))

    def delete_analysis(self, user, analysis_id):
        with self.connection() as db:
            return db.execute("DELETE FROM analyses WHERE user_id = ? AND id = ?", (user, analysis_id)).rowcount > 0

    def delete_profile(self, user):
        with self.connection() as db:
            db.execute("DELETE FROM users WHERE id = ?", (user,))
