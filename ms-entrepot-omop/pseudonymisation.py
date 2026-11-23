import csv
import hashlib
import hmac
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

INS_SYSTEM = "urn:ma:ins"
ETAB_SYSTEM = "urn:ma:etablissement"
CSV_PATH = Path(__file__).resolve().parent / "data" / "etablissements.csv"


class RegionInconnue(Exception):
    """Exception levée lorsqu'une région ou un établissement ne peut être identifié."""


def pseudonymiser(ins: str) -> str:
    """Génère un pseudonyme déterministe HMAC-SHA256 à partir de l'INS."""
    cle = os.environ.get("PSEUDONYM_KEY")
    if not cle:
        raise ValueError("La variable d'environnement PSEUDONYM_KEY est absente ou vide.")
    h = hmac.new(cle.encode("utf-8"), ins.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"P-{h[:8].upper()}"


@lru_cache(maxsize=8)
def _charger_etablissements(chemin_str: str) -> dict[str, str]:
    """Charge le fichier CSV des établissements et retourne le dictionnaire {etablissement_id: region}."""
    chemin = Path(chemin_str)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier établissements introuvable : {chemin}")
    mapping: dict[str, str] = {}
    with open(chemin, mode="r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            etab_id = row.get("etablissement_id", "").strip()
            region = row.get("region", "").strip()
            if etab_id and region:
                mapping[etab_id] = region
    return mapping


def _obtenir_chemin_csv(csv_path: str | Path | None = None) -> str:
    """Résout le chemin absolu du fichier CSV des établissements sous forme de chaîne."""
    if csv_path is not None:
        return str(Path(csv_path).resolve())
    env_path = os.environ.get("ETABLISSEMENTS_CSV")
    if env_path:
        return str(Path(env_path).resolve())
    return str(CSV_PATH.resolve())


def anonymiser_patient(patient: dict, aujourd_hui: date | None = None) -> dict:
    """Anonymise la ressource Patient en retournant uniquement le pseudonyme, le sexe OMOP et la tranche d'âge."""
    ins = None
    for ident in patient.get("identifier", []):
        if ident.get("system") == INS_SYSTEM:
            ins = ident.get("value")
            break
    if not ins:
        raise ValueError("Identifiant INS (urn:ma:ins) absent ou invalide.")

    gender = patient.get("gender")
    if gender == "male":
        sexe = 8507
    elif gender == "female":
        sexe = 8532
    else:
        raise ValueError(f"Sexe absent ou non reconnu : {gender}")

    birth_str = patient.get("birthDate")
    if not birth_str:
        raise ValueError("birthDate absent de la ressource Patient.")
    birth_date = date.fromisoformat(birth_str)
    ref_date = aujourd_hui if aujourd_hui is not None else date.today()

    age = ref_date.year - birth_date.year - ((ref_date.month, ref_date.day) < (birth_date.month, birth_date.day))
    if age < 0:
        raise ValueError(f"Date de naissance postérieure à la date de référence : {birth_str}")

    if age >= 85:
        tranche_age = "85+"
    else:
        lower = (age // 5) * 5
        tranche_age = f"{lower}-{lower + 4}"

    return {
        "pseudonyme": pseudonymiser(ins),
        "sexe": sexe,
        "tranche_age": tranche_age,
    }


def trouver_region(bundle: dict, csv_path: str | Path | None = None) -> str:
    """Identifie le schéma régional correspondant à un Bundle FHIR à partir de son établissement."""
    entries = bundle.get("entry", [])
    patient = None
    for entry in entries:
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            patient = resource
            break

    ref_org = None
    if patient:
        ref_org = patient.get("managingOrganization", {}).get("reference")

    if not ref_org:
        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Encounter":
                service_provider = resource.get("serviceProvider", {})
                if service_provider.get("reference"):
                    ref_org = service_provider["reference"]
                    break

    if not ref_org:
        raise RegionInconnue("Aucune référence d'organisation trouvée (managingOrganization ou serviceProvider).")

    org_resource = None
    for entry in entries:
        full_url = entry.get("fullUrl")
        res = entry.get("resource", {})
        if res.get("resourceType") == "Organization":
            res_id = res.get("id")
            if (
                full_url == ref_org
                or res_id == ref_org
                or f"urn:uuid:{res_id}" == ref_org
                or f"Organization/{res_id}" == ref_org
                or (res_id and ref_org.endswith(res_id))
            ):
                org_resource = res
                break

    if not org_resource:
        raise RegionInconnue(f"Ressource Organization introuvable pour la référence : {ref_org}")

    etab_id = None
    for ident in org_resource.get("identifier", []):
        if ident.get("system") == ETAB_SYSTEM:
            etab_id = ident.get("value")
            break

    if not etab_id:
        raise RegionInconnue("Identifiant d'établissement (urn:ma:etablissement) absent de l'Organization.")

    chemin_csv = _obtenir_chemin_csv(csv_path)
    etablissements = _charger_etablissements(chemin_csv)

    if etab_id not in etablissements:
        raise RegionInconnue(f"Établissement non répertorié dans le référentiel : {etab_id}")

    return etablissements[etab_id]
