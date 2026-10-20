import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_existing_database_upgrade_seeds_revision(tmp_path):
    root = Path(__file__).resolve().parents[2]
    path = tmp_path / "migrate.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{path.as_posix()}", PYTHONPATH=str(root / "backend"))

    def migrate(target):
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", target],
                                cwd=root / "backend", env=env, capture_output=True, timeout=30)
        assert result.returncode == 0, result.stderr

    migrate("0002_create_visitor_events")
    migrate("head")
    with sqlite3.connect(path) as connection:
        assert connection.execute("select id, revision from knowledge_revision").fetchall() == [(1, 0)]
        assert connection.execute("select version_num from alembic_version").fetchone()[0] == "0003_knowledge_revision"
