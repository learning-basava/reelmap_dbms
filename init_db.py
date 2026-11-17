"""Create the tables and load the idea bank.

Usage:
    python init_db.py               # drop + create all tables, then seed
    python init_db.py --export-sql  # also write sql/seed.sql (for the report)
"""
import sys

import pymysql

import config
from seed_data import FORMATS, IDEA_TEMPLATES, NICHES, SCENE_TEMPLATES

SCHEMA_FILE = config.BASE_DIR / "sql" / "schema.sql"
SEED_FILE = config.BASE_DIR / "sql" / "seed.sql"


def split_statements(sql_text):
    """Split a .sql file into single statements (comments removed)."""
    lines = [ln for ln in sql_text.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def seed(cur):
    """Insert the starter niches, formats, idea templates and scene templates."""
    cur.executemany("INSERT INTO niches (niche_id, name, description) VALUES (%s, %s, %s)", NICHES)
    cur.executemany(
        "INSERT INTO content_formats (format_id, name, style, description, icon_pose, default_duration) "
        "VALUES (%s, %s, %s, %s, %s, %s)", FORMATS)
    cur.executemany(
        "INSERT INTO idea_templates (format_id, niche_id, title_template, hook_template, "
        "description_template, difficulty) VALUES (%s, %s, %s, %s, %s, %s)", IDEA_TEMPLATES)
    cur.executemany(
        "INSERT INTO scene_templates (format_id, scene_order, shot_type, pose, prop, action_template, "
        "dialogue_template, text_template, duration_sec) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        SCENE_TEMPLATES)


def sql_literal(value):
    """Turn a Python value into a safe SQL literal for the exported seed file."""
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def export_seed_sql():
    """Write the seed rows as plain INSERT statements to sql/seed.sql."""
    def rows(table, cols, data):
        values = ",\n".join("(" + ", ".join(sql_literal(v) for v in row) + ")" for row in data)
        return f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{values};\n"

    parts = [
        "-- Reelmap idea bank seed data (generated from seed_data.py)\n",
        rows("niches", ["niche_id", "name", "description"], NICHES),
        rows("content_formats", ["format_id", "name", "style", "description", "icon_pose", "default_duration"], FORMATS),
        rows("idea_templates", ["format_id", "niche_id", "title_template", "hook_template",
                                "description_template", "difficulty"], IDEA_TEMPLATES),
        rows("scene_templates", ["format_id", "scene_order", "shot_type", "pose", "prop", "action_template",
                                 "dialogue_template", "text_template", "duration_sec"], SCENE_TEMPLATES),
    ]
    SEED_FILE.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {SEED_FILE}")


def create_database_if_missing():
    """Create the database itself (needed on fresh cloud servers)."""
    conn = pymysql.connect(**config.mysql_kwargs(with_database=False))
    try:
        with conn.cursor() as cur:
            name = config.MYSQL_DB.replace("`", "")
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.commit()
    except pymysql.err.OperationalError:
        pass  # no permission to create databases (e.g. shared hosting); it must already exist
    finally:
        conn.close()


def build(log=print):
    """Drop and recreate every table, then load the idea bank."""
    create_database_if_missing()
    conn = pymysql.connect(**config.mysql_kwargs())
    try:
        with conn.cursor() as cur:
            for statement in split_statements(SCHEMA_FILE.read_text(encoding="utf-8")):
                cur.execute(statement)
            seed(cur)
        conn.commit()
        log(f"Database '{config.MYSQL_DB}' is ready: {len(NICHES)} niches, {len(FORMATS)} formats, "
            f"{len(IDEA_TEMPLATES)} idea templates, {len(SCENE_TEMPLATES)} scene templates.")
    finally:
        conn.close()


def ensure_schema(log=print):
    """Build the database only if the tables don't exist yet (safe to call on every start)."""
    try:
        create_database_if_missing()
        conn = pymysql.connect(**config.mysql_kwargs())
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW TABLES LIKE 'users'")
                exists = cur.fetchone() is not None
        finally:
            conn.close()
        if not exists:
            log("No tables found. Creating them now...")
            build(log)
    except pymysql.MySQLError as e:
        log(f"Could not check the database: {e}")


def main():
    build()
    if "--export-sql" in sys.argv:
        export_seed_sql()


if __name__ == "__main__":
    main()
