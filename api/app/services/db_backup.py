"""
Database backup helpers shared by the admin backup router (download a migration
ZIP) and the Celery scheduler (write periodic pg_dump snapshots to disk).

Dumps are `pg_dump --data-only` custom-format archives, matching the migration
export: the restore target supplies the schema via `alembic upgrade head`, so a
data-only dump is sufficient and avoids PostGIS extension/schema drops.
"""
import os
import subprocess
from datetime import datetime
from urllib.parse import unquote, urlparse

from app.services.media_storage import BACKUPS_PATH

# Same exclusions as the migration export — these tables are owned by the
# target's own migrations/extensions, not by application data.
_EXCLUDE_TABLES = ("spatial_ref_sys", "alembic_version")
_DUMP_PREFIX = "postmarked-"
_DUMP_SUFFIX = ".dump"


def pg_conn_args() -> tuple[list[str], dict[str, str]]:
    """Derive pg_dump/pg_restore connection flags + env from DATABASE_URL.

    Password is passed via PGPASSWORD (env) so special characters never need
    shell/URL escaping.
    """
    raw = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/postmarked")
    scheme, _, rest = raw.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    parsed = urlparse(f"{base_scheme}://{rest}")
    args = [
        "-h", parsed.hostname or "db",
        "-p", str(parsed.port or 5432),
        "-U", unquote(parsed.username or "postgres"),
        "-d", (parsed.path.lstrip("/") or "postmarked"),
    ]
    env = {**os.environ, "PGPASSWORD": unquote(parsed.password or "")}
    return args, env


def _dump_args() -> list[str]:
    args = ["--data-only", "--format=custom"]
    for table in _EXCLUDE_TABLES:
        args.append(f"--exclude-table={table}")
    return args


def create_db_dump(dest_dir: str = BACKUPS_PATH) -> str:
    """Write a timestamped pg_dump archive into dest_dir; return its path."""
    os.makedirs(dest_dir, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(dest_dir, f"{_DUMP_PREFIX}{stamp}{_DUMP_SUFFIX}")
    conn_args, env = pg_conn_args()
    result = subprocess.run(
        ["pg_dump", *conn_args, *_dump_args(), "-f", dest],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Don't leave a partial/empty file behind.
        if os.path.exists(dest):
            os.remove(dest)
        raise RuntimeError(f"pg_dump failed (exit {result.returncode}): {result.stderr[:1000]}")
    return dest


def prune_old_dumps(dest_dir: str = BACKUPS_PATH, keep: int = 7) -> int:
    """Keep the newest `keep` dumps in dest_dir, delete older ones. Returns count removed."""
    if not os.path.isdir(dest_dir):
        return 0
    dumps = sorted(
        (
            entry.path
            for entry in os.scandir(dest_dir)
            if entry.is_file()
            and entry.name.startswith(_DUMP_PREFIX)
            and entry.name.endswith(_DUMP_SUFFIX)
        ),
        reverse=True,  # timestamped names sort chronologically; newest first
    )
    removed = 0
    for stale in dumps[max(keep, 0):]:
        os.remove(stale)
        removed += 1
    return removed
