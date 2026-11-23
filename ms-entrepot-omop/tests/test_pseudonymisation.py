import json
import re
from datetime import date
from pathlib import Path

import pytest

from pseudonymisation import (
    INS_SYSTEM,
    RegionInconnue,
    anonymiser_patient,
    pseudonymiser,
    trouver_region,
)

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"
GENERATED_DIR = Path(__file__).resolve().parent.parent / "data" / "generated"


@pytest.fixture(autouse=True)
def definir_cle_par_defaut(monkeypatch):
    """Définit une clé de test par défaut pour les tests nécessitant le chiffrement."""
    monkeypatch.setenv("PSEUDONYM_KEY", "cle-de-test-unitaire-pour-pytest")


def test_meme_ins_donne_meme_pseudonyme():
    """Vérifie que la pseudonymisation est déterministe pour un même INS."""
    ins = "INS-MA-2026-12345678"
    p1 = pseudonymiser(ins)
    p2 = pseudonymiser(ins)
    assert p1 == p2


def test_cle_differente_donne_pseudonyme_different(monkeypatch):
    """Vérifie qu'un changement de PSEUDONYM_KEY produit un pseudonyme différent pour un même INS."""
    ins = "INS-MA-2026-12345678"
    monkeypatch.setenv("PSEUDONYM_KEY", "cle-alpha")
    p1 = pseudonymiser(ins)
    monkeypatch.setenv("PSEUDONYM_KEY", "cle-beta")
    p2 = pseudonymiser(ins)
    assert p1 != p2


def test_format_pseudonyme():
    """Vérifie le respect du format attendu : ^P-[0-9A-F]{8}$."""
    ins = "INS-MA-2026-99999999"
    pseudo = pseudonymiser(ins)
    assert re.match(r"^P-[0-9A-F]{8}$", pseudo) is not None


def test_pseudonym_key_absente_leve_erreur(monkeypatch):
    """Vérifie qu'une erreur claire est levée lorsque PSEUDONYM_KEY est absente ou vide."""
    monkeypatch.delenv("PSEUDONYM_KEY", raising=False)
    with pytest.raises(ValueError, match="PSEUDONYM_KEY est absente ou vide"):
        pseudonymiser("INS-MA-2026-12345678")

    monkeypatch.setenv("PSEUDONYM_KEY", "")
    with pytest.raises(ValueError, match="PSEUDONYM_KEY est absente ou vide"):
        pseudonymiser("INS-MA-2026-12345678")


@pytest.mark.parametrize(
    "nom_fichier",
    [
        "exemple_diabete_type2_fes.json",
        "exemple_prediabete_rabat.json",
        "exemple_sain_tanger.json",
    ],
)
def test_anonymiser_patient_samples_cles_et_absence_donnees_nominatives(nom_fichier):
    """Vérifie le format de sortie et l'absence totale de données nominatives sur les 3 Bundles réels."""
    chemin = SAMPLES_DIR / nom_fichier
    with open(chemin, encoding="utf-8") as f:
        bundle = json.load(f)

    patient_res = next(
        e["resource"] for e in bundle["entry"] if e["resource"].get("resourceType") == "Patient"
    )

    # Récupération des valeurs sensibles en clair pour vérification
    ins_en_clair = next(
        i["value"] for i in patient_res["identifier"] if i.get("system") == INS_SYSTEM
    )
    nom_famille = patient_res["name"][0].get("family", "")
    prenom = patient_res["name"][0]["given"][0]
    ville = patient_res["address"][0].get("city", "")
    telephone = patient_res["telecom"][0].get("value", "")
    birth_date = patient_res.get("birthDate", "")

    resultat = anonymiser_patient(patient_res)

    # Clés exactes retournées
    assert set(resultat.keys()) == {"pseudonyme", "sexe", "tranche_age"}

    # Sérialisation JSON pour vérifier qu'aucune valeur nominative n'est présente
    json_sortie = json.dumps(resultat, ensure_ascii=False)
    assert ins_en_clair not in json_sortie
    assert nom_famille not in json_sortie
    assert prenom not in json_sortie
    assert ville not in json_sortie
    assert telephone not in json_sortie
    assert birth_date not in json_sortie


def test_sexe_selon_gender():
    """Vérifie le mapping OMOP du sexe : male -> 8507, female -> 8532."""
    patient_male = {
        "resourceType": "Patient",
        "identifier": [{"system": INS_SYSTEM, "value": "INS-MA-2026-11111111"}],
        "gender": "male",
        "birthDate": "1990-01-01",
    }
    patient_female = {
        "resourceType": "Patient",
        "identifier": [{"system": INS_SYSTEM, "value": "INS-MA-2026-22222222"}],
        "gender": "female",
        "birthDate": "1990-01-01",
    }
    patient_invalide = {
        "resourceType": "Patient",
        "identifier": [{"system": INS_SYSTEM, "value": "INS-MA-2026-33333333"}],
        "gender": "unknown",
        "birthDate": "1990-01-01",
    }

    assert anonymiser_patient(patient_male)["sexe"] == 8507
    assert anonymiser_patient(patient_female)["sexe"] == 8532
    with pytest.raises(ValueError, match="Sexe absent ou non reconnu"):
        anonymiser_patient(patient_invalide)


def test_tranches_age_aux_bornes():
    """Vérifie le calcul exact des tranches d'âge aux bornes (4, 5, 84, 85 ans)."""
    date_ref = date(2026, 11, 22)

    def creer_patient(birth_date_str: str) -> dict:
        return {
            "resourceType": "Patient",
            "identifier": [{"system": INS_SYSTEM, "value": "INS-MA-2026-00000000"}],
            "gender": "female",
            "birthDate": birth_date_str,
        }

    # Âge 4 ans (né le 22/11/2022) => "0-4"
    res_4 = anonymiser_patient(creer_patient("2022-11-22"), aujourd_hui=date_ref)
    assert res_4["tranche_age"] == "0-4"

    # Âge 5 ans (né le 22/11/2021) => "5-9"
    res_5 = anonymiser_patient(creer_patient("2021-11-22"), aujourd_hui=date_ref)
    assert res_5["tranche_age"] == "5-9"

    # Âge 84 ans (né le 22/11/1942) => "80-84"
    res_84 = anonymiser_patient(creer_patient("1942-11-22"), aujourd_hui=date_ref)
    assert res_84["tranche_age"] == "80-84"

    # Âge 85 ans (né le 22/11/1941) => "85+"
    res_85 = anonymiser_patient(creer_patient("1941-11-22"), aujourd_hui=date_ref)
    assert res_85["tranche_age"] == "85+"


@pytest.mark.parametrize(
    "nom_fichier, region_attendue",
    [
        ("exemple_diabete_type2_fes.json", "region_fes"),
        ("exemple_prediabete_rabat.json", "region_rabat"),
        ("exemple_sain_tanger.json", "region_tanger"),
    ],
)
def test_trouver_region_samples(nom_fichier, region_attendue):
    """Vérifie que la région résolue correspond exactement à la région attendue pour les 3 Bundles."""
    chemin = SAMPLES_DIR / nom_fichier
    with open(chemin, encoding="utf-8") as f:
        bundle = json.load(f)
    assert trouver_region(bundle) == region_attendue


def test_trouver_region_etablissement_absent_du_csv():
    """Vérifie que RegionInconnue est levée si l'identifiant d'établissement n'existe pas dans le CSV."""
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "managingOrganization": {"reference": "urn:uuid:fake-org"},
                }
            },
            {
                "fullUrl": "urn:uuid:fake-org",
                "resource": {
                    "resourceType": "Organization",
                    "id": "fake-org",
                    "identifier": [{"system": "urn:ma:etablissement", "value": "HOP-INCONNU-99"}],
                },
            },
        ],
    }
    with pytest.raises(RegionInconnue, match="Établissement non répertorié"):
        trouver_region(bundle)


def test_trouver_region_sans_reference_organisation():
    """Vérifie que RegionInconnue est levée si aucune référence d'organisation n'est trouvée."""
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                }
            }
        ],
    }
    with pytest.raises(RegionInconnue, match="Aucune référence d'organisation trouvée"):
        trouver_region(bundle)


def test_donnees_generated_si_presentes():
    """Teste l'ensemble des Bundles de data/generated s'ils ont été générés."""
    if not GENERATED_DIR.exists():
        pytest.skip("Le dossier data/generated n'existe pas.")

    fichiers = list(GENERATED_DIR.glob("*.json"))
    if not fichiers:
        pytest.skip("Aucun fichier présent dans data/generated.")

    for f in fichiers:
        with open(f, encoding="utf-8") as fp:
            bundle = json.load(fp)
        region = trouver_region(bundle)
        assert region in {"region_fes", "region_rabat", "region_tanger"}

        patient = next(
            e["resource"] for e in bundle["entry"] if e["resource"].get("resourceType") == "Patient"
        )
        res = anonymiser_patient(patient)
        assert res["sexe"] in {8507, 8532}
        assert res["pseudonyme"].startswith("P-")
