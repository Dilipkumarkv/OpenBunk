"""Native, verified backup/restore.

Postgres: `pg_dump -Fc` custom-format archive.
SQLite:   online-backup API snapshot.

Every backup writes a sidecar manifest with the Alembic revision, per-table row
counts and the SHA-256 of the dump. Restore verifies the checksum and revision,
requires `--force`, and always takes a pre-restore snapshot first. Postgres
audit events are additionally archived to JSONL before a destructive restore.

CLI:
  python -m app.backup create  backup.dump
  python -m app.backup restore backup.dump --force [--allow-revision-mismatch]
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine, inspect, text

from .config import get_settings

FORMAT = "openbunk-native@2"


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(target: Path, producer) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    os.close(fd)
    temp = Path(temp_name)
    try:
        producer(temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def _atomical_write_json(target: Path, payload: dict) -> None:
    _atomic_write_bytes(
        target, lambda temp: temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    )


def _sqlite_path(url: str) -> Path:
    raw = url.removeprefix("sqlite:///").removeprefix("sqlite://")
    if raw in (":memory:", ""):
        raise RuntimeError("in-memory SQLite cannot be backed up")
    return Path(raw).resolve()


def _pg_env(url: str) -> tuple[str, dict[str, str]]:
    """Return a libpq URL without the SQLAlchemy driver suffix and env secrets."""
    plain = url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )
    parts = urlsplit(plain)
    env = dict(os.environ)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
        host = parts.hostname or "localhost"
        port = f":{parts.port}" if parts.port else ""
        database = (parts.path or "/").lstrip("/")
        plain = f"postgresql://{parts.username or 'postgres'}@{host}{port}/{database}"
    return plain, env


def _revision(conn) -> str | None:
    try:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:
        return None


def _row_counts(engine) -> dict[str, int]:
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in inspect(engine).get_table_names():
            quoted = '"' + table.replace('"', '""') + '"'
            counts[table] = int(conn.execute(text(f"SELECT COUNT(*) FROM {quoted}")).scalar() or 0)
    return counts


def create_backup(engine, path: Path) -> dict:
    path = Path(path)
    url = str(engine.url)
    is_postgres = url.startswith("postgresql")
    _atomic_write_bytes(
        path,
        lambda temp: _write_dump(engine, url, temp) if is_postgres else _write_sqlite(url, temp),
    )
    with engine.connect() as conn:
        revision = _revision(conn)
    manifest = {
        "format": FORMAT,
        "engine": "postgresql" if is_postgres else "sqlite",
        "dump": path.name,
        "created_at": _now(),
        "revision": revision,
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        "row_counts": _row_counts(engine),
    }
    _atomical_write_json(Path(f"{path}.manifest.json"), manifest)
    return manifest


def _write_sqlite(url: str, target: Path) -> None:
    import sqlite3

    source = sqlite3.connect(str(_sqlite_path(url)))
    try:
        dest = sqlite3.connect(str(target))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def _write_dump(engine, url: str, target: Path) -> None:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is not installed — install the PostgreSQL client tools")
    pg_url, env = _pg_env(url)
    subprocess.run(
        ["pg_dump", "-Fc", "--no-owner", "--no-privileges", "-f", str(target), "--dbname", pg_url],
        check=True,
        env=env,
    )


def _read_manifest(path: Path) -> dict:
    manifest_path = Path(f"{path}.manifest.json")
    if not manifest_path.exists():
        raise ValueError(f"missing backup manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError(f"unsupported backup format (expected {FORMAT})")
    if not path.exists():
        raise ValueError(f"backup dump not found: {path}")
    actual = _sha256(path)
    if actual != manifest.get("sha256"):
        raise ValueError("backup checksum mismatch — refusing to restore a corrupted file")
    return manifest


def _head_revision() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()


def _archive_audit(engine, path: Path) -> None:
    with engine.connect() as conn:
        if "audit_events" not in inspect(engine).get_table_names():
            return
        rows = conn.execute(text("SELECT * FROM audit_events")).mappings().all()
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), default=str) + "\n")


def restore_backup(engine, path: Path, *, force: bool = False, allow_revision_mismatch: bool = False) -> dict:
    path = Path(path)
    if not force:
        raise ValueError("restore is destructive: pass --force after confirming the target")
    manifest = _read_manifest(path)

    head = _head_revision()
    recorded = manifest.get("revision")
    if recorded and head and recorded != head and not allow_revision_mismatch:
        raise ValueError(
            f"backup revision {recorded} does not match current head {head}; "
            "migrate first or pass --allow-revision-mismatch"
        )

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pre = path.with_name(f"{path.name}.pre-restore-{stamp}")
    create_backup(engine, pre)
    print(f"Pre-restore snapshot: {pre} (+ {pre}.manifest.json)")

    url = str(engine.url)
    if url.startswith("postgresql"):
        archive = path.with_name(f"{path.name}.audit-{stamp}.jsonl")
        _archive_audit(engine, archive)
        print(f"Audit events archived before restore: {archive}")
        if shutil.which("pg_restore") is None:
            raise RuntimeError("pg_restore is not installed — install the PostgreSQL client tools")
        pg_url, env = _pg_env(url)
        subprocess.run(
            [
                "pg_restore",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
                "--dbname",
                pg_url,
                str(path),
            ],
            check=True,
            env=env,
        )
    else:
        import sqlite3

        source = sqlite3.connect(str(path))
        dest = sqlite3.connect(str(_sqlite_path(url)))
        try:
            source.backup(dest)
        finally:
            dest.close()
            source.close()

    expected = manifest.get("row_counts") or {}
    actual = _row_counts(engine)
    mismatches = {table: (expected.get(table), actual.get(table)) for table in expected if expected.get(table) != actual.get(table)}
    if mismatches:
        raise ValueError(f"post-restore row counts do not match the manifest: {mismatches}")
    return {"manifest": manifest, "pre_restore": str(pre), "row_counts": actual}


def _engine():
    settings = get_settings()
    kwargs = {"connect_args": {"check_same_thread": False}} if settings.DATABASE_URL.startswith("sqlite") else {}
    return create_engine(settings.DATABASE_URL, **kwargs)


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("create", "restore") or len(argv) < 2:
        print(__doc__)
        return 2
    command, raw_path = argv[0], argv[1]
    force = "--force" in argv[2:]
    allow = "--allow-revision-mismatch" in argv[2:]
    engine = _engine()
    if command == "create":
        manifest = create_backup(engine, Path(raw_path))
        total = sum(manifest["row_counts"].values())
        print(
            f"Backup written to {raw_path}: {len(manifest['row_counts'])} tables, {total} rows, "
            f"sha256 {manifest['sha256']}."
        )
        return 0

    result = restore_backup(engine, Path(raw_path), force=force, allow_revision_mismatch=allow)
    print(
        f"Restored {sum(result['row_counts'].values())} rows across "
        f"{len(result['row_counts'])} tables from {raw_path}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
