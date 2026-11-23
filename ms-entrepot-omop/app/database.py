"""
Connexion PostgreSQL via psycopg3 (psycopg).

La variable d'environnement DATABASE_URL est lue à l'import.
En tests unitaires (sans DB), cette variable peut être absente ;
les fonctions d'insertion ne seront pas appelées.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import psycopg

_DATABASE_URL: str | None = None


def get_database_url() -> str:
    global _DATABASE_URL
    if _DATABASE_URL is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "La variable d'environnement DATABASE_URL est absente ou vide."
            )
        _DATABASE_URL = url
    return _DATABASE_URL


@contextmanager
def get_connection() -> Generator[psycopg.Connection, None, None]:
    """Ouvre une connexion PostgreSQL et la ferme à la sortie du contexte."""
    conn = psycopg.connect(get_database_url())
    try:
        yield conn
    finally:
        conn.close()
