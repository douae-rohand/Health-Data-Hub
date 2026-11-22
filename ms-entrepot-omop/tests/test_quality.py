import os
import psycopg
import pytest
from quality import rules
from quality.report import build_report
from quality.stats import build_stats

TEST_DB = os.environ.get("TEST_DATABASE_URL",
                         "postgresql://hdh:change_me@localhost:5432/hdh")
S = "pg_temp"


@pytest.fixture
def conn():
    c = psycopg.connect(TEST_DB, autocommit=True)
    c.execute("CREATE TEMP TABLE person (person_id int, pseudonyme text, gender_concept_id int)")
    c.execute("CREATE TEMP TABLE visit_occurrence (visit_occurrence_id int, visit_start_date date, visit_end_date date)")
    c.execute("CREATE TEMP TABLE condition_occurrence (condition_occurrence_id int, condition_concept_id int)")
    c.execute("CREATE TEMP TABLE measurement (measurement_id int, measurement_concept_id int, value_as_number numeric)")
    yield c
    c.close()


def test_completude_person(conn):
    conn.execute("""INSERT INTO person VALUES
        (1,'P-8F3A2C91',8507),(2,'P-1A2B3C4D',8532),(3,NULL,8507)""")
    assert rules.completude_person(conn, S) == (3, 1)


def test_completude_visit(conn):
    conn.execute("INSERT INTO visit_occurrence VALUES (1,'2024-01-01','2024-01-02'),(2,NULL,NULL)")
    assert rules.completude_visit(conn, S) == (2, 1)


def test_coherence_visit_dates(conn):
    conn.execute("""INSERT INTO visit_occurrence VALUES
        (1,'2024-01-01','2024-01-05'),
        (2,'2024-03-10','2024-03-01'),
        (3,'2999-01-01',NULL)""")
    assert rules.coherence_visit_dates(conn, S) == (3, 2)


def test_coherence_hba1c(conn):
    conn.execute("""INSERT INTO measurement VALUES
        (1,3004410,7.2),(2,3004410,45),(3,3004410,1.0),(4,999,500)""")
    assert rules.coherence_hba1c(conn, S) == (3, 2)


def test_codage_sexe(conn):
    conn.execute("INSERT INTO person VALUES (1,'P-1',8507),(2,'P-2',123),(3,'P-3',NULL)")
    assert rules.codage_sexe(conn, S) == (3, 1)


def test_codage_condition(conn):
    conn.execute("INSERT INTO condition_occurrence VALUES (1,201826),(2,0),(3,NULL)")
    assert rules.codage_condition(conn, S) == (3, 2)


def test_report_signale_un_defaut_introduit(conn):
    """Critère de fin du guide : un défaut volontaire apparaît dans le rapport."""
    conn.execute("INSERT INTO visit_occurrence VALUES (1,'2024-03-10','2024-03-01')")
    report = build_report(conn, regions=[S])
    entry = next(e for e in report if e["rule"] == "coherence_visit_dates")
    assert entry["total"] == 1 and entry["defects"] == 1


def test_stats_compte_les_lignes(conn):
    conn.execute("INSERT INTO person VALUES (1,'P-1',8507),(2,'P-2',8532)")
    stats = build_stats(conn, regions=[S])
    assert stats[S]["person"] == 2
