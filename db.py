"""Database helpers: one MySQL connection per request, closed automatically."""
import pymysql
from flask import g

import config


def connect():
    """Open a new MySQL connection that returns rows as dictionaries."""
    return pymysql.connect(**config.mysql_kwargs(), cursorclass=pymysql.cursors.DictCursor, autocommit=False)


def get_db():
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = connect()
    return g.db


def close_db(_exc=None):
    """Close the request's connection (registered as a teardown handler)."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_all(sql, params=()):
    """Run a SELECT and return every row as a list of dicts."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql, params=()):
    """Run a SELECT and return the first row, or None."""
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql, params=()):
    """Run an INSERT, UPDATE or DELETE, commit it and return the new row id."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        new_id = cur.lastrowid
    conn.commit()
    return new_id
