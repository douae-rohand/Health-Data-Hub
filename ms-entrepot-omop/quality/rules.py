from psycopg import sql
from quality import config as c


def _scalar(conn, query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchone()[0]


def _count(conn, schema, table, where=None, params=None):
    q = sql.SQL("SELECT COUNT(*) FROM {t}").format(t=sql.Identifier(schema, table))
    if where is not None:
        q = sql.SQL("{q} WHERE {w}").format(q=q, w=where)
    return _scalar(conn, q, params)


def _col(name):
    return sql.Identifier(name)


# ---------- Complétude ----------
def completude_person(conn, schema):
    where = sql.SQL("COALESCE(TRIM({p}::text), '') = '' OR {s} IS NULL").format(
        p=_col(c.PERSON_PSEUDO), s=_col(c.PERSON_SEX))
    return _count(conn, schema, "person"), _count(conn, schema, "person", where)


def completude_visit(conn, schema):
    where = sql.SQL("{d} IS NULL").format(d=_col(c.VISIT_START))
    return (_count(conn, schema, "visit_occurrence"),
            _count(conn, schema, "visit_occurrence", where))


# ---------- Cohérence ----------
def coherence_visit_dates(conn, schema):
    where = sql.SQL(
        "({e} IS NOT NULL AND {s} IS NOT NULL AND {e} < {s}) OR {s} > CURRENT_DATE"
    ).format(s=_col(c.VISIT_START), e=_col(c.VISIT_END))
    return (_count(conn, schema, "visit_occurrence"),
            _count(conn, schema, "visit_occurrence", where))


def coherence_hba1c(conn, schema):
    base = sql.SQL("{m} = %s").format(m=_col(c.MEASURE_CONCEPT))
    bad = sql.SQL("{m} = %s AND {v} IS NOT NULL AND ({v} < %s OR {v} > %s)").format(
        m=_col(c.MEASURE_CONCEPT), v=_col(c.MEASURE_VALUE))
    total = _count(conn, schema, "measurement", base, [c.HBA1C_CONCEPT_ID])
    defects = _count(conn, schema, "measurement", bad,
                     [c.HBA1C_CONCEPT_ID, c.HBA1C_MIN, c.HBA1C_MAX])
    return total, defects


# ---------- Codage ----------
def codage_sexe(conn, schema):
    where = sql.SQL("{s} IS NOT NULL AND NOT ({s} = ANY(%s))").format(s=_col(c.PERSON_SEX))
    return (_count(conn, schema, "person"),
            _count(conn, schema, "person", where, [c.VALID_SEX_CODES]))


def codage_condition(conn, schema):
    where = sql.SQL("{k} IS NULL OR {k} = 0").format(k=_col(c.CONDITION_CONCEPT))
    return (_count(conn, schema, "condition_occurrence"),
            _count(conn, schema, "condition_occurrence", where))


RULES = [
    {"name": "completude_person", "family": "completude", "table": "person", "fn": completude_person},
    {"name": "completude_visit", "family": "completude", "table": "visit_occurrence", "fn": completude_visit},
    {"name": "coherence_visit_dates", "family": "coherence", "table": "visit_occurrence", "fn": coherence_visit_dates},
    {"name": "coherence_hba1c", "family": "coherence", "table": "measurement", "fn": coherence_hba1c},
    {"name": "codage_sexe", "family": "codage", "table": "person", "fn": codage_sexe},
    {"name": "codage_condition", "family": "codage", "table": "condition_occurrence", "fn": codage_condition},
]
