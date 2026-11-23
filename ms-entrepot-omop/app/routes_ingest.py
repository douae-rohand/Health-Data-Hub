"""
Route POST /ingest/fhir

Reçoit un Bundle FHIR transaction, détermine la région, convertit les
ressources et insère en une seule transaction SQL (tout ou rien).

Règles de sécurité :
- L'INS n'est jamais loggé ni retourné.
- Le nom du schéma est validé contre une liste blanche fixe.
- Toutes les requêtes SQL sont paramétrées (pas de concaténation de valeurs).
- La réponse ne contient aucune donnée nominative.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pseudonymisation import RegionInconnue, trouver_region

from app.conversion import convertir_bundle
from app.database import get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])

# Liste blanche des schémas autorisés
SCHEMAS_AUTORISES: frozenset[str] = frozenset(
    {"region_fes", "region_rabat", "region_tanger"}
)


# ---------------------------------------------------------------------------
# Modèle de réponse
# ---------------------------------------------------------------------------

class IngestResponse(BaseModel):
    region: str
    person_id: int
    lignes_inserees: dict[str, int]


# ---------------------------------------------------------------------------
# Route principale
# ---------------------------------------------------------------------------

@router.post("/fhir", response_model=IngestResponse, status_code=201)
def ingest_fhir(bundle: dict[str, Any]) -> IngestResponse:
    """
    Reçoit un Bundle FHIR, le convertit en OMOP et l'insère dans le bon schéma.

    - 422 si l'établissement est inconnu (RegionInconnue).
    - 422 si l'INS est absent ou le Patient manquant.
    - 500 si la DB est indisponible.
    - En cas d'erreur mid-insertion, tout est rollbacké (transaction atomique).
    """
    # --- 1. Identifier la région (peut lever RegionInconnue) ---
    try:
        region = trouver_region(bundle)
    except RegionInconnue as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if region not in SCHEMAS_AUTORISES:
        # Défense en profondeur : ne devrait jamais arriver car trouver_region
        # retourne uniquement des valeurs du CSV qui sont dans la liste blanche.
        raise HTTPException(
            status_code=422,
            detail=f"Schéma régional non autorisé : {region}",
        )

    # --- 2. Conversion FHIR → OMOP (en mémoire, sans DB) ---
    try:
        result = convertir_bundle(bundle)
    except ValueError as exc:
        # INS absent, Patient manquant, sexe invalide, etc.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # --- 3. Insertion en base dans une seule transaction ---
    person_id, counts = _inserer(region, result)

    return IngestResponse(region=region, person_id=person_id, lignes_inserees=counts)


# ---------------------------------------------------------------------------
# Insertion SQL
# ---------------------------------------------------------------------------

def _inserer(region: str, result: dict) -> tuple[int, dict[str, int]]:
    """
    Insère toutes les lignes OMOP dans le schéma `region` en une transaction.

    - Le schéma est substitué via `psycopg.sql.Identifier` (safe, pas de concaténation).
    - person : UPSERT sur person_source_value pour qu'un même INS donne toujours
      le même person_id (idempotent si le Bundle est renvoyé).
    - Toutes les autres tables : INSERT simple.
    - En cas d'exception, la transaction est rollbackée automatiquement.
    """
    from psycopg import sql as psql

    counts: dict[str, int] = {
        "person": 0,
        "visit_occurrence": 0,
        "condition_occurrence": 0,
        "measurement": 0,
        "drug_exposure": 0,
    }

    with get_connection() as conn:
        with conn.transaction():

            # --- person (UPSERT) ---
            p = result["person"]
            row = conn.execute(
                psql.SQL("""
                    INSERT INTO {schema}.person
                        (person_source_value, gender_concept_id, tranche_age,
                         race_concept_id, ethnicity_concept_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (person_source_value) DO UPDATE
                        SET gender_concept_id = EXCLUDED.gender_concept_id,
                            tranche_age = EXCLUDED.tranche_age
                    RETURNING person_id
                """).format(schema=psql.Identifier(region)),
                (
                    p["person_source_value"],
                    p["gender_concept_id"],
                    p["tranche_age"],
                    p["race_concept_id"],
                    p["ethnicity_concept_id"],
                ),
            ).fetchone()
            person_id: int = row[0]
            counts["person"] = 1

            # --- visit_occurrences ---
            # On garde un map index_local → visit_occurrence_id DB pour les FK
            visit_db_ids: dict[int, int] = {}

            for idx, v in enumerate(result["visit_occurrences"]):
                row = conn.execute(
                    psql.SQL("""
                        INSERT INTO {schema}.visit_occurrence
                            (person_id, visit_concept_id, visit_start_datetime,
                             visit_end_datetime, visit_type_concept_id,
                             visit_source_value, care_site_source_value)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING visit_occurrence_id
                    """).format(schema=psql.Identifier(region)),
                    (
                        person_id,
                        v["visit_concept_id"],
                        v["visit_start_datetime"],
                        v["visit_end_datetime"],
                        v["visit_type_concept_id"],
                        v["visit_source_value"],
                        v["care_site_source_value"],
                    ),
                ).fetchone()
                visit_db_ids[idx] = row[0]
                counts["visit_occurrence"] += 1

            # Fonction utilitaire : résoudre l'index local → id DB
            def resolve_visit(local_idx: int | None) -> int | None:
                if local_idx is None:
                    return None
                return visit_db_ids.get(local_idx)

            # --- condition_occurrences ---
            for c in result["condition_occurrences"]:
                conn.execute(
                    psql.SQL("""
                        INSERT INTO {schema}.condition_occurrence
                            (person_id, visit_occurrence_id, condition_concept_id,
                             condition_start_datetime, condition_end_datetime,
                             condition_type_concept_id, condition_source_value,
                             condition_source_concept_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """).format(schema=psql.Identifier(region)),
                    (
                        person_id,
                        resolve_visit(c["visit_occurrence_id"]),
                        c["condition_concept_id"],
                        c["condition_start_datetime"],
                        c["condition_end_datetime"],
                        c["condition_type_concept_id"],
                        c["condition_source_value"],
                        c["condition_source_concept_id"],
                    ),
                )
                counts["condition_occurrence"] += 1

            # --- measurements ---
            for m in result["measurements"]:
                conn.execute(
                    psql.SQL("""
                        INSERT INTO {schema}.measurement
                            (person_id, visit_occurrence_id, measurement_concept_id,
                             measurement_datetime, measurement_type_concept_id,
                             value_as_number, unit_concept_id, unit_source_value,
                             measurement_source_value, value_source_value)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """).format(schema=psql.Identifier(region)),
                    (
                        person_id,
                        resolve_visit(m["visit_occurrence_id"]),
                        m["measurement_concept_id"],
                        m["measurement_datetime"],
                        m["measurement_type_concept_id"],
                        m["value_as_number"],
                        m["unit_concept_id"],
                        m["unit_source_value"],
                        m["measurement_source_value"],
                        m["value_source_value"],
                    ),
                )
                counts["measurement"] += 1

            # --- drug_exposures ---
            for d in result["drug_exposures"]:
                conn.execute(
                    psql.SQL("""
                        INSERT INTO {schema}.drug_exposure
                            (person_id, visit_occurrence_id, drug_concept_id,
                             drug_exposure_start_datetime, drug_exposure_end_datetime,
                             drug_type_concept_id, drug_source_value,
                             drug_source_concept_id, quantity)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """).format(schema=psql.Identifier(region)),
                    (
                        person_id,
                        resolve_visit(d["visit_occurrence_id"]),
                        d["drug_concept_id"],
                        d["drug_exposure_start_datetime"],
                        d["drug_exposure_end_datetime"],
                        d["drug_type_concept_id"],
                        d["drug_source_value"],
                        d["drug_source_concept_id"],
                        d["quantity"],
                    ),
                )
                counts["drug_exposure"] += 1

    return person_id, counts
