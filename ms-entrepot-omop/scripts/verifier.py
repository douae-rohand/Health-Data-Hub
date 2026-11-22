import glob
import json
import collections

for f in sorted(glob.glob(r"ms-entrepot-omop\data\samples\*.json")):
    texte = open(f, encoding="utf-8").read()
    bundle = json.loads(texte)
    types = collections.Counter(e["resource"]["resourceType"] for e in bundle["entry"])
    patient = next(e["resource"] for e in bundle["entry"]
                   if e["resource"]["resourceType"] == "Patient")
    ins = [i["value"] for i in patient["identifier"] if i.get("system") == "urn:ma:ins"]
    print("=====", f)
    print("pays US restant :", '"country": "US"' in texte)
    print("etat MA restant :", '"state": "MA"' in texte)
    print("INS             :", ins)
    print("nom             :", patient["name"])
    print("adresse         :", patient["address"][0]["city"], patient["address"][0]["country"])
    print("types           :", dict(types))