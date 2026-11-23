#!/usr/bin/env python3
"""Marocanise des Bundles FHIR générés par Synthea.

Usage :
  python marocaniser.py --input DOSSIER_SYNTHEA --output DOSSIER_SORTIE \
      --etablissements ms-entrepot-omop/data/etablissements.csv --seed 42
"""
import argparse
import csv
import json
import random
import uuid
from pathlib import Path

# ---------- CONFIGURATION (à modifier ici si G1 change son format) ----------
INS_PREFIX = "INS-MA-2026-"
INS_DIGITS = 8
INS_SYSTEM = "urn:ma:ins"
ETAB_SYSTEM = "urn:ma:etablissement"
REGION_SYSTEM = "urn:ma:region"
SKIP_PREFIXES = ("hospitalInformation", "practitionerInformation")
US_ID_CODES = {"SS", "DL", "PPN"}  # SSN, permis, passeport
US_EXT_URLS = (
    "us-core-race", "us-core-ethnicity",
    "patient-mothersMaidenName", "patient-birthPlace",
)
# -----------------------------------------------------------------------------

PRENOMS_H = [("Youssef", "يوسف"), ("Mohamed", "محمد"), ("Omar", "عمر"),
             ("Karim", "كريم"), ("Hamza", "حمزة"), ("Mehdi", "مهدي"),
             ("Anas", "أنس"), ("Rachid", "رشيد"), ("Said", "سعيد"),
             ("Ayoub", "أيوب")]
PRENOMS_F = [("Fatima", "فاطمة"), ("Khadija", "خديجة"), ("Salma", "سلمى"),
             ("Imane", "إيمان"), ("Zineb", "زينب"), ("Meryem", "مريم"),
             ("Aicha", "عائشة"), ("Sara", "سارة"), ("Houda", "هدى"),
             ("Nadia", "نادية")]
NOMS = [("Alami", "العلمي"), ("Benani", "بناني"), ("El Idrissi", "الإدريسي"),
        ("Tazi", "التازي"), ("Berrada", "برادة"), ("Fassi", "الفاسي"),
        ("Bennis", "بنيس"), ("Chraibi", "الشرايبي"), ("Lahlou", "لحلو"),
        ("Amrani", "العمراني"), ("Ouazzani", "الوزاني"), ("Mansouri", "المنصوري")]
VILLES = {"region_fes": "Fès", "region_rabat": "Rabat", "region_tanger": "Tanger"}
RUES = ["Rue Allal Ben Abdellah", "Avenue Hassan II", "Rue de la Liberté",
        "Boulevard Mohammed V", "Rue Ibn Khaldoun"]


def charger_etablissements(chemin):
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    regions = sorted({l["region"] for l in lignes})
    return lignes, regions


def faux_ins(rng, deja_utilises):
    while True:
        ins = INS_PREFIX + "".join(rng.choice("0123456789") for _ in range(INS_DIGITS))
        if ins not in deja_utilises:
            deja_utilises.add(ins)
            return ins


def tirer_nom(rng, sexe):
    prenoms = PRENOMS_F if sexe == "female" else PRENOMS_H
    prenom, nom = rng.choice(prenoms), rng.choice(NOMS)
    idx = rng.choice([0, 1])  # 0 = latin, 1 = arabe
    return prenom[idx], nom[idx]


def marocaniser(bundle, rng, region, etab, ins_utilises):
    entries = bundle["entry"]
    patient = next(e["resource"] for e in entries
                   if e["resource"]["resourceType"] == "Patient")

    # --- anciens noms, pour les retrouver ailleurs dans le Bundle ---
    anciens = []
    for n in patient.get("name", []):
        anciens += n.get("given", []) + [n.get("family", "")]
    for ext in patient.get("extension", []):
        if ext["url"].endswith("mothersMaidenName"):
            anciens += ext["valueString"].split()
    anciens = sorted({a for a in anciens if a}, key=len, reverse=True)

    # --- nouveau nom ---
    prenom, nom = tirer_nom(rng, patient.get("gender"))
    patient["name"] = [{"use": "official", "family": nom, "given": [prenom]}]

    # --- identifiants : on retire les US, on ajoute l'INS ---
    patient["identifier"] = [
        i for i in patient.get("identifier", [])
        if not any(c.get("code") in US_ID_CODES
                   for c in i.get("type", {}).get("coding", []))
    ]
    patient["identifier"].append({
        "system": INS_SYSTEM,
        "value": faux_ins(rng, ins_utilises),
    })

    # --- contact, adresse ---
    ville = VILLES[region]
    patient["telecom"] = [{
        "system": "phone", "use": "home",
        "value": "+212 6" + "".join(rng.choice("0123456789") for _ in range(8)),
    }]
    patient["address"] = [{
        "line": [f"{rng.randint(1, 200)} {rng.choice(RUES)}"],
        "city": ville,
        "state": region,
        "postalCode": "".join(rng.choice("0123456789") for _ in range(5)),
        "country": "MA",
    }]

    # --- extensions US supprimées, lieu de naissance marocain ---
    patient["extension"] = [
        e for e in patient.get("extension", [])
        if not any(u in e["url"] for u in US_EXT_URLS)
    ]
    patient["extension"].append({
        "url": "http://hl7.org/fhir/StructureDefinition/patient-birthPlace",
        "valueAddress": {"city": ville, "country": "MA"},
    })
    patient["communication"] = [{"language": {
        "coding": [{"system": "urn:ietf:bcp:47", "code": "ar",
                    "display": "Arabic"}],
        "text": "Arabic"}}]
    patient["meta"] = {"tag": [{"system": REGION_SYSTEM, "code": region}]}

    # --- établissement : Organization + Encounter.serviceProvider ---
    org_url = "urn:uuid:" + str(uuid.UUID(int=rng.getrandbits(128), version=4))
    org = {
        "resourceType": "Organization",
        "id": org_url.replace("urn:uuid:", ""),
        "identifier": [{"system": ETAB_SYSTEM, "value": etab["etablissement_id"]}],
        "name": etab["nom"],
        "address": [{"city": ville, "country": "MA"}],
        "meta": {"tag": [{"system": REGION_SYSTEM, "code": region}]},
    }
    entries.insert(0, {"fullUrl": org_url, "resource": org,
                       "request": {"method": "POST", "url": "Organization"}})
    patient["managingOrganization"] = {"reference": org_url, "display": etab["nom"]}
    for e in entries:
        if e["resource"]["resourceType"] == "Encounter":
            e["resource"]["serviceProvider"] = {
                "reference": org_url, "display": etab["nom"]}

    # --- remplacement des anciens noms partout dans le fichier ---
    texte = json.dumps(bundle, ensure_ascii=False)
    for ancien in anciens:
        texte = texte.replace(ancien, nom)
    return json.loads(texte), anciens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--etablissements", required=True)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    lignes, regions = charger_etablissements(args.etablissements)
    rng = random.Random(args.seed)
    ins_utilises = set()
    sortie = Path(args.output)
    sortie.mkdir(parents=True, exist_ok=True)

    fichiers = sorted(p for p in Path(args.input).glob("*.json")
                      if not p.name.startswith(SKIP_PREFIXES))
    for i, chemin in enumerate(fichiers):
        with open(chemin, encoding="utf-8") as f:
            bundle = json.load(f)
        region = regions[i % len(regions)]  # répartition équilibrée
        etab = rng.choice([l for l in lignes if l["region"] == region])
        resultat, anciens = marocaniser(bundle, rng, region, etab, ins_utilises)

        nom_sortie = sortie / f"patient_{i + 1:04d}.json"
        with open(nom_sortie, "w", encoding="utf-8") as f:
            json.dump(resultat, f, ensure_ascii=False, indent=2)

        texte = json.dumps(resultat, ensure_ascii=False)
        alertes = [a for a in anciens if a in texte]
        if "Massachusetts" in texte:
            alertes.append("Massachusetts")
        print(f"{nom_sortie.name}  {region}  {etab['etablissement_id']}"
              + (f"  ATTENTION reste: {alertes}" if alertes else ""))
    print(f"{len(fichiers)} fichiers écrits dans {sortie}")


if __name__ == "__main__":
    main()