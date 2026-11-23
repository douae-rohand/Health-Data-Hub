import psycopg
from quality.config import REGIONS
from quality.rules import RULES


def build_report(conn, regions=None):
    """Calculé à chaque appel. Une ligne par région et par règle."""
    results = []
    for region in (regions or REGIONS):
        for rule in RULES:
            entry = {"region": region, "family": rule["family"],
                     "rule": rule["name"], "table": rule["table"]}
            try:
                total, defects = rule["fn"](conn, region)
                entry.update(total=total, defects=defects)
            except psycopg.errors.UndefinedTable:
                entry.update(total=None, defects=None, error="table absente")
            results.append(entry)
    return results
