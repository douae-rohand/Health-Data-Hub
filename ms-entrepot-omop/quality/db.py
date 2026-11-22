import os
import psycopg


def get_connection():
    """Connexion en lecture. DATABASE_URL vient de .env.g3 (hôte 'postgres' dans Docker)."""
    return psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
