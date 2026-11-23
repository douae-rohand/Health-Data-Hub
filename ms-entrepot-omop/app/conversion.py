"""
Conversion FHIR R4 → OMOP CDM minimal.

Ressources traitées :
  Patient              → person
  Encounter            → visit_occurrence
  Condition            → condition_occurrence
  Observation          → measurement  (y compris panels avec component)
  MedicationRequest    → drug_exposure
  MedicationAdministration → drug_exposure

Toutes les autres ressources sont ignorées sans erreur.

Dépendances Dev 2 importées telles quelles, sans modification.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from pseudonymisation import anonymiser_patient

from app.mapping_codes import (
    concept_loinc,
    concept_rxnorm,
    concept_snomed_condition,
)

# ---------------------------------------------------------------------------
# Paramètre de configuration : system FHIR portant l'INS
# Lisible depuis la variable d'environnement INS_SYSTEM (défaut conforme
# à l'accord d'équipe et à pseudonymisation.py).
# ---------------------------------------------------------------------------
_INS_SYSTEM_DEFAULT = "urn:ma:ins"


def get_ins_system() -> str:
    return os.environ.get("INS_FHIR_SYSTEM", _INS_SYSTEM_DEFAULT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(value: str | None) -> datetime | None:
    """Parse une date ISO 8601 (avec ou sans heure) en datetime UTC."""
    if not value:
        return None
    try:
        # Python 3.11+ gère les offsets "+01:00" via fromisoformat
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _first_coding(codeable: dict | None) -> tuple[str, str]:
    """Retourne (system, code) du premier coding, ou ("", "")."""
    if not codeable:
        return "", ""
    codings = codeable.get("coding", [])
    if not codings:
        return "", ""
    c = codings[0]
    return c.get("system", ""), c.get("code", "")


def _source_value(system: str, code: str) -> str:
    """Construit la valeur source 'système|code' pour les colonnes *_source_value."""
    return f"{system}|{code}" if system or code else ""


def _build_ref_map(entries: list[dict]) -> dict[str, dict]:
    """
    Construit un dictionnaire fullUrl/uuid → ressource FHIR pour résoudre
    les références urn:uuid: dans le Bundle.
    """
    ref_map: dict[str, dict] = {}
    for entry in entries:
        full_url = entry.get("fullUrl", "")
        resource = entry.get("resource", {})
        res_id = resource.get("id", "")
        res_type = resource.get("resourceType", "")

        if full_url:
            ref_map[full_url] = resource
        if res_id:
            ref_map[res_id] = resource
            ref_map[f"urn:uuid:{res_id}"] = resource
            if res_type:
                ref_map[f"{res_type}/{res_id}"] = resource
    return ref_map


# ---------------------------------------------------------------------------
# Conversion Patient → person
# ---------------------------------------------------------------------------

def convertir_patient(
    patient: dict,
) -> dict:
    """
    Convertit une ressource Patient FHIR en ligne OMOP person.

    Retourne un dict avec les colonnes de la table person.
    Lève ValueError si l'INS est absent ou si anonymiser_patient échoue.
    """
    anon = anonymiser_patient(patient)
    return {
        "person_source_value": anon["pseudonyme"],
        "gender_concept_id": anon["sexe"],
        "tranche_age": anon["tranche_age"],
        "race_concept_id": 0,
        "ethnicity_concept_id": 0,
    }


# ---------------------------------------------------------------------------
# Conversion Encounter → visit_occurrence
# ---------------------------------------------------------------------------

def convertir_encounter(
    encounter: dict,
    person_id: int,
    ref_map: dict[str, dict],
) -> dict:
    """Convertit une ressource Encounter en ligne OMOP visit_occurrence."""
    full_url_key = f"urn:uuid:{encounter.get('id', '')}"
    visit_source = encounter.get("id", "")

    period = encounter.get("period", {})
    start_dt = _parse_dt(period.get("start"))
    end_dt = _parse_dt(period.get("end"))

    # Type de visite : AMB→outpatient (9202), IMP→inpatient (9201), sinon 0
    class_code = encounter.get("class", {}).get("code", "")
    visit_concept = {
        "AMB": 9202,
        "IMP": 9201,
        "EMER": 9203,
    }.get(class_code, 0)

    # Établissement via serviceProvider
    care_site_val = None
    sp_ref = encounter.get("serviceProvider", {}).get("reference")
    if sp_ref:
        org = ref_map.get(sp_ref, {})
        for ident in org.get("identifier", []):
            if ident.get("system") == "urn:ma:etablissement":
                care_site_val = ident.get("value")
                break

    return {
        "person_id": person_id,
        "visit_concept_id": visit_concept,
        "visit_start_datetime": start_dt,
        "visit_end_datetime": end_dt,
        "visit_type_concept_id": 32817,
        "visit_source_value": visit_source,
        "care_site_source_value": care_site_val,
    }


# ---------------------------------------------------------------------------
# Conversion Condition → condition_occurrence
# ---------------------------------------------------------------------------

def convertir_condition(
    condition: dict,
    person_id: int,
    visit_id_map: dict[str, int],
) -> dict:
    """Convertit une ressource Condition en ligne OMOP condition_occurrence."""
    system, code = _first_coding(condition.get("code"))
    concept_id = concept_snomed_condition(code) if system == "http://snomed.info/sct" else 0

    start_dt = _parse_dt(condition.get("onsetDateTime") or condition.get("recordedDate"))
    end_dt = _parse_dt(condition.get("abatementDateTime"))

    enc_ref = condition.get("encounter", {}).get("reference", "")
    enc_uuid = enc_ref.replace("urn:uuid:", "") if enc_ref else ""
    visit_occurrence_id = visit_id_map.get(enc_ref) or visit_id_map.get(enc_uuid)

    return {
        "person_id": person_id,
        "visit_occurrence_id": visit_occurrence_id,
        "condition_concept_id": concept_id,
        "condition_start_datetime": start_dt,
        "condition_end_datetime": end_dt,
        "condition_type_concept_id": 32020,
        "condition_source_value": _source_value(system, code),
        "condition_source_concept_id": 0,
    }


# ---------------------------------------------------------------------------
# Conversion Observation → measurement (1 ou N lignes si component)
# ---------------------------------------------------------------------------

def convertir_observation(
    observation: dict,
    person_id: int,
    visit_id_map: dict[str, int],
) -> list[dict]:
    """
    Convertit une Observation FHIR en une ou plusieurs lignes measurement.
    Les panels (ex. tension artérielle) avec `component` produisent une ligne
    par composant.
    """
    enc_ref = observation.get("encounter", {}).get("reference", "")
    enc_uuid = enc_ref.replace("urn:uuid:", "") if enc_ref else ""
    visit_occurrence_id = visit_id_map.get(enc_ref) or visit_id_map.get(enc_uuid)

    obs_dt = _parse_dt(
        observation.get("effectiveDateTime") or observation.get("issued")
    )

    rows: list[dict] = []

    # --- Observation simple avec valueQuantity ---
    if "valueQuantity" in observation:
        system, code = _first_coding(observation.get("code"))
        concept_id = concept_loinc(code) if system == "http://loinc.org" else 0
        vq = observation["valueQuantity"]
        rows.append({
            "person_id": person_id,
            "visit_occurrence_id": visit_occurrence_id,
            "measurement_concept_id": concept_id,
            "measurement_datetime": obs_dt,
            "measurement_type_concept_id": 32817,
            "value_as_number": vq.get("value"),
            "unit_concept_id": 0,
            "unit_source_value": vq.get("unit"),
            "measurement_source_value": _source_value(system, code),
            "value_source_value": str(vq.get("value", "")),
        })

    # --- Panel avec components (ex. Blood pressure) ---
    elif "component" in observation:
        for comp in observation["component"]:
            system, code = _first_coding(comp.get("code"))
            concept_id = concept_loinc(code) if system == "http://loinc.org" else 0
            vq = comp.get("valueQuantity", {})
            rows.append({
                "person_id": person_id,
                "visit_occurrence_id": visit_occurrence_id,
                "measurement_concept_id": concept_id,
                "measurement_datetime": obs_dt,
                "measurement_type_concept_id": 32817,
                "value_as_number": vq.get("value"),
                "unit_concept_id": 0,
                "unit_source_value": vq.get("unit"),
                "measurement_source_value": _source_value(system, code),
                "value_source_value": str(vq.get("value", "")),
            })

    # Observations textuelles / codées uniquement : ignorées (concept_id=0, pas de valeur numérique)
    # On les insère quand même pour garder la traçabilité si le concept est connu.
    elif "valueCodeableConcept" in observation:
        system, code = _first_coding(observation.get("code"))
        concept_id = concept_loinc(code) if system == "http://loinc.org" else 0
        vc_sys, vc_code = _first_coding(observation.get("valueCodeableConcept"))
        rows.append({
            "person_id": person_id,
            "visit_occurrence_id": visit_occurrence_id,
            "measurement_concept_id": concept_id,
            "measurement_datetime": obs_dt,
            "measurement_type_concept_id": 32817,
            "value_as_number": None,
            "unit_concept_id": 0,
            "unit_source_value": None,
            "measurement_source_value": _source_value(system, code),
            "value_source_value": _source_value(vc_sys, vc_code),
        })

    return rows


# ---------------------------------------------------------------------------
# Conversion MedicationRequest / MedicationAdministration → drug_exposure
# ---------------------------------------------------------------------------

def convertir_medication(
    resource: dict,
    person_id: int,
    visit_id_map: dict[str, int],
    ref_map: dict[str, dict],
) -> dict | None:
    """
    Convertit un MedicationRequest ou MedicationAdministration en drug_exposure.
    Retourne None si la ressource est inexploitable.
    """
    res_type = resource.get("resourceType", "")

    # Résoudre la ressource Medication référencée
    med_code_resource: dict | None = None
    if "medicationReference" in resource:
        med_ref = resource["medicationReference"].get("reference", "")
        med_code_resource = ref_map.get(med_ref)
    elif "medicationCodeableConcept" in resource:
        # Pas de ressource Medication séparée : le code est inline
        med_code_resource = {"code": resource["medicationCodeableConcept"]}

    system, code = "", ""
    if med_code_resource:
        system, code = _first_coding(med_code_resource.get("code"))

    concept_id = concept_rxnorm(code) if "rxnorm" in system.lower() else 0

    # Dates
    if res_type == "MedicationRequest":
        start_dt = _parse_dt(resource.get("authoredOn"))
        end_dt = None
        enc_ref = resource.get("encounter", {}).get("reference", "")
        quantity = None
    else:  # MedicationAdministration
        eff = resource.get("effectiveDateTime") or resource.get("effectivePeriod", {}).get("start")
        start_dt = _parse_dt(eff)
        end_dt = _parse_dt(resource.get("effectivePeriod", {}).get("end"))
        enc_ref = resource.get("context", {}).get("reference", "") or \
                  resource.get("encounter", {}).get("reference", "")
        dosage = resource.get("dosage", {})
        quantity = dosage.get("dose", {}).get("value") if dosage else None

    enc_uuid = enc_ref.replace("urn:uuid:", "") if enc_ref else ""
    visit_occurrence_id = visit_id_map.get(enc_ref) or visit_id_map.get(enc_uuid)

    return {
        "person_id": person_id,
        "visit_occurrence_id": visit_occurrence_id,
        "drug_concept_id": concept_id,
        "drug_exposure_start_datetime": start_dt,
        "drug_exposure_end_datetime": end_dt,
        "drug_type_concept_id": 32817,
        "drug_source_value": _source_value(system, code),
        "drug_source_concept_id": 0,
        "quantity": quantity,
    }


# ---------------------------------------------------------------------------
# Conversion d'un Bundle entier
# ---------------------------------------------------------------------------

BundleResult = dict[str, Any]
"""
{
  "person": dict,
  "visit_occurrences": list[dict],
  "condition_occurrences": list[dict],
  "measurements": list[dict],
  "drug_exposures": list[dict],
}
"""


def convertir_bundle(bundle: dict) -> BundleResult:
    """
    Convertit un Bundle FHIR transaction en ensembles de lignes OMOP.

    Ordre de traitement : Patient → Encounter → Condition + Observation +
    Medication*.

    Les références sont résolues via un dictionnaire urn:uuid: → ressource.
    Les ressources non gérées sont ignorées sans lever d'erreur.

    Lève ValueError si aucun Patient n'est trouvé ou si l'INS est absent.
    """
    entries: list[dict] = bundle.get("entry", [])
    ref_map = _build_ref_map(entries)

    # --- Trouver le Patient ---
    patient_resource: dict | None = None
    for entry in entries:
        if entry.get("resource", {}).get("resourceType") == "Patient":
            patient_resource = entry["resource"]
            break
    if patient_resource is None:
        raise ValueError("Aucune ressource Patient dans le Bundle.")

    # --- Convertir le Patient (person_id = 0 ici, sera attribué par la DB) ---
    person_row = convertir_patient(patient_resource)

    # --- Index fullUrl Patient pour résoudre les références subject ---
    patient_full_url = ""
    patient_id = patient_resource.get("id", "")
    for entry in entries:
        if entry.get("resource", {}).get("id") == patient_id and \
                entry.get("resource", {}).get("resourceType") == "Patient":
            patient_full_url = entry.get("fullUrl", "")
            break

    # --- Convertir les Encounters ; on garde un map fullUrl → index de la liste ---
    visit_rows: list[dict] = []
    # visit_id_map : fullUrl/uuid → index (position dans visit_rows, utilisée
    # localement ; en DB, l'id réel sera retourné par RETURNING)
    visit_local_id_map: dict[str, int] = {}

    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") != "Encounter":
            continue
        # Vérifier que cet Encounter appartient bien à notre Patient
        subject_ref = resource.get("subject", {}).get("reference", "")
        if subject_ref not in (patient_full_url, patient_id,
                               f"urn:uuid:{patient_id}",
                               f"Patient/{patient_id}"):
            continue

        visit_row = convertir_encounter(resource, person_id=0, ref_map=ref_map)
        idx = len(visit_rows)
        visit_rows.append(visit_row)

        enc_id = resource.get("id", "")
        enc_full_url = entry.get("fullUrl", "")
        for key in (enc_full_url, enc_id, f"urn:uuid:{enc_id}"):
            if key:
                visit_local_id_map[key] = idx

    # --- Convertir Conditions, Observations, Medications ---
    condition_rows: list[dict] = []
    measurement_rows: list[dict] = []
    drug_rows: list[dict] = []

    for entry in entries:
        resource = entry.get("resource", {})
        res_type = resource.get("resourceType", "")

        if res_type == "Condition":
            subject_ref = resource.get("subject", {}).get("reference", "")
            if subject_ref not in (patient_full_url, patient_id,
                                   f"urn:uuid:{patient_id}",
                                   f"Patient/{patient_id}"):
                continue
            row = convertir_condition(resource, person_id=0,
                                      visit_id_map=visit_local_id_map)
            condition_rows.append(row)

        elif res_type == "Observation":
            subject_ref = resource.get("subject", {}).get("reference", "")
            if subject_ref not in (patient_full_url, patient_id,
                                   f"urn:uuid:{patient_id}",
                                   f"Patient/{patient_id}"):
                continue
            rows = convertir_observation(resource, person_id=0,
                                         visit_id_map=visit_local_id_map)
            measurement_rows.extend(rows)

        elif res_type in ("MedicationRequest", "MedicationAdministration"):
            subject_ref = resource.get("subject", {}).get("reference", "")
            if subject_ref not in (patient_full_url, patient_id,
                                   f"urn:uuid:{patient_id}",
                                   f"Patient/{patient_id}"):
                continue
            row = convertir_medication(resource, person_id=0,
                                       visit_id_map=visit_local_id_map,
                                       ref_map=ref_map)
            if row is not None:
                drug_rows.append(row)

        # Toutes les autres ressources sont ignorées

    return {
        "person": person_row,
        "visit_occurrences": visit_rows,
        "condition_occurrences": condition_rows,
        "measurements": measurement_rows,
        "drug_exposures": drug_rows,
    }
