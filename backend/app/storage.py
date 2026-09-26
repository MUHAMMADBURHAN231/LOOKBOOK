"""Local persistence: image files on disk plus a small SQLite database."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Look, OutfitSpec


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.media_dir = root / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = root / "lookbook.db"
        with self._conn() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS generations (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    spec TEXT NOT NULL,
                    image_file TEXT NOT NULL,
                    source_file TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS looks (
                    id TEXT PRIMARY KEY,
                    generation_id TEXT NOT NULL REFERENCES generations(id),
                    title TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- files -----------------------------------------------------------

    def save_image(self, data: bytes, suffix: str = ".png") -> str:
        name = f"{uuid.uuid4().hex}{suffix}"
        (self.media_dir / name).write_bytes(data)
        return name

    def read_image(self, name: str) -> bytes:
        return (self.media_dir / name).read_bytes()

    def purge_older_than(self, days: int) -> int:
        """Delete media and unsaved generations older than `days`. Returns files removed."""
        cutoff = time.time() - days * 86400
        removed = 0
        for path in self.media_dir.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        cutoff_iso = datetime.fromtimestamp(cutoff, timezone.utc).isoformat()
        with self._conn() as db:
            db.execute("DELETE FROM looks WHERE created_at < ?", (cutoff_iso,))
            db.execute("DELETE FROM generations WHERE created_at < ?", (cutoff_iso,))
        return removed

    def wipe(self) -> None:
        for path in self.media_dir.iterdir():
            if path.is_file():
                path.unlink()
        with self._conn() as db:
            db.execute("DELETE FROM looks")
            db.execute("DELETE FROM generations")

    # --- generations -----------------------------------------------------

    def add_generation(
        self, description: str, spec: OutfitSpec, image_file: str, source_file: str
    ) -> str:
        gen_id = uuid.uuid4().hex
        with self._conn() as db:
            db.execute(
                "INSERT INTO generations VALUES (?, ?, ?, ?, ?, ?)",
                (gen_id, description, spec.model_dump_json(), image_file, source_file, _now()),
            )
        return gen_id

    def get_generation(self, gen_id: str) -> sqlite3.Row | None:
        with self._conn() as db:
            return db.execute("SELECT * FROM generations WHERE id = ?", (gen_id,)).fetchone()

    # --- wardrobe --------------------------------------------------------

    def add_look(self, generation_id: str, title: str, collection: str) -> str:
        look_id = uuid.uuid4().hex
        with self._conn() as db:
            db.execute(
                "INSERT INTO looks VALUES (?, ?, ?, ?, ?)",
                (look_id, generation_id, title, collection, _now()),
            )
        return look_id

    def list_looks(self, collection: str | None = None) -> list[Look]:
        query = (
            "SELECT l.*, g.description, g.spec, g.image_file FROM looks l "
            "JOIN generations g ON g.id = l.generation_id"
        )
        params: tuple = ()
        if collection:
            query += " WHERE l.collection = ?"
            params = (collection,)
        query += " ORDER BY l.created_at DESC"
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [
            Look(
                id=r["id"],
                title=r["title"],
                collection=r["collection"],
                description=r["description"],
                image_url=f"/media/{r['image_file']}",
                spec=OutfitSpec.model_validate(json.loads(r["spec"])),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def delete_look(self, look_id: str) -> bool:
        with self._conn() as db:
            cur = db.execute("DELETE FROM looks WHERE id = ?", (look_id,))
            return cur.rowcount > 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
