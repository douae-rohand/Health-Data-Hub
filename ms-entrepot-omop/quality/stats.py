import psycopg
from psycopg import sql
from quality.config import REGIONS, OMOP_TABLES


def build_stats(conn, regions=None):
    """Volumes par région : {"region_fes": {"person": 340, ...}, ...}"""
    stats = {}
    for region in (regions or REGIONS):
        stats[region] = {}
        for table in OMOP_TABLES:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("SELECT COUNT(*) FROM {t}")
                                .format(t=sql.Identifier(region, table)))
                    stats[region][table] = cur.fetchone()[0]
            except psycopg.errors.UndefinedTable:
                stats[region][table] = None
    return stats
