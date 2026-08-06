"""
Guard against collation drift breaking text indexes.

Postgres btree indexes on text columns are physically ordered by the sort order
the system collation library supplies. When a rebuilt container image ships a
different glibc, that order can change and existing indexes silently return
wrong results: a lookup walks to the wrong page and reports no rows. Published
content then disappears from the public site with no error in any log.

Postgres only detects this when the database carries a recorded collation
version in `pg_database.datcollversion`. A database that predates version
tracking has NULL there and is never checked, so this seeds the value on first
run and rebuilds indexes whose ordering cannot be vouched for.
"""
import asyncio
import os
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db import DATABASE_URL

_FALSEY = frozenset({"false", "0", "no", "off"})

REINDEX_ON_COLLATION_CHANGE = (
    os.getenv("REINDEX_ON_COLLATION_CHANGE", "true").strip().lower() not in _FALSEY
)

# The api, worker, and beat containers share this entrypoint and start together,
# so they serialize on an advisory lock and only the first one does the work.
_ADVISORY_LOCK_KEY = 8090411


def _log(msg: str) -> None:
    print(f"[collation] {msg}", file=sys.stderr)


def _manual_instructions(db_ident: str, seed_version: bool) -> None:
    record = (
        "UPDATE pg_database SET datcollversion = pg_database_collation_actual_version(oid)"
        " WHERE datname = current_database();"
        if seed_version
        else f"ALTER DATABASE {db_ident} REFRESH COLLATION VERSION;"
    )
    _log("Automatic repair is disabled by REINDEX_ON_COLLATION_CHANGE.")
    _log("Text lookups may silently return no rows until you run:")
    _log(f"  REINDEX DATABASE {db_ident};")
    _log(f"  {record}")


async def _record_version(conn, db_ident: str, seed: bool) -> None:
    # REFRESH COLLATION VERSION rejects a NULL-to-value transition, so a
    # database that never tracked a version has to be seeded through the
    # catalog. That write needs superuser, which a managed Postgres may withhold.
    try:
        if seed:
            await conn.execute(
                text(
                    "UPDATE pg_database SET datcollversion = "
                    "pg_database_collation_actual_version(oid) "
                    "WHERE datname = current_database()"
                )
            )
        else:
            await conn.execute(text(f"ALTER DATABASE {db_ident} REFRESH COLLATION VERSION"))
    except Exception as exc:
        _log(f"Indexes were rebuilt, but recording the collation version failed: {exc}")
        _log("Drift will not be detected automatically until that version is recorded.")
        return
    _log("Collation version recorded; future drift is detected automatically.")


async def _repair(conn, db_ident: str, seed_version: bool) -> None:
    _log(f"Rebuilding indexes in {db_ident} — this may take a while on a large database.")
    await conn.execute(text(f"REINDEX DATABASE {db_ident}"))
    _log("Indexes rebuilt.")
    await _record_version(conn, db_ident, seed_version)


async def check_collation() -> None:
    # REINDEX DATABASE and ALTER DATABASE cannot run inside a transaction block.
    engine = create_async_engine(DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            # Read the version only once the lock is held, so a container that
            # waited here sees the repair the first one already made.
            await conn.execute(
                text("SELECT pg_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}
            )
            row = (
                await conn.execute(
                    text(
                        "SELECT quote_ident(datname) AS ident, datcollversion AS recorded, "
                        "pg_database_collation_actual_version(oid) AS actual "
                        "FROM pg_database WHERE datname = current_database()"
                    )
                )
            ).first()

            if row is None or row.actual is None:
                # No versioned provider for this locale; nothing to compare against.
                return

            db_ident = row.ident

            if row.recorded is None:
                _log(
                    f"{db_ident} has no recorded collation version, so index ordering "
                    "cannot be verified against the current system library."
                )
                if REINDEX_ON_COLLATION_CHANGE:
                    await _repair(conn, db_ident, seed_version=True)
                else:
                    _manual_instructions(db_ident, seed_version=True)
                return

            if row.recorded == row.actual:
                return

            _log(
                f"Collation version changed for {db_ident}: recorded {row.recorded}, "
                f"system now {row.actual}. Text indexes may return wrong results."
            )
            if REINDEX_ON_COLLATION_CHANGE:
                await _repair(conn, db_ident, seed_version=False)
            else:
                _manual_instructions(db_ident, seed_version=False)
    finally:
        await engine.dispose()


async def main() -> None:
    try:
        await check_collation()
    except Exception as exc:
        # A failed check must not keep the app from starting; a warning here is
        # better than a container that will not boot.
        _log(f"WARNING: collation check failed: {exc}")
        _log("Run scripts/check-collation.sh to verify index integrity by hand.")


if __name__ == "__main__":
    asyncio.run(main())
