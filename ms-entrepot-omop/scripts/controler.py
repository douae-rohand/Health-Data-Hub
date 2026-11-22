import glob, json, sys, collections

dossier = sys.argv[1]
fichiers = sorted(glob.glob(dossier + r"\*.json"))
ins_vus, regions, diab = [], collections.Counter(), 0
sans_ins = sans_org = 0
for f in fichiers:
    texte = open(f, encoding="utf-8").read()
    b = json.loads(texte)
    p = next(e["resource"] for e in b["entry"] if e["resource"]["resourceType"] == "Patient")
    ins = [i["value"] for i in p["identifier"] if i.get("system") == "urn:ma:ins"]
    if not ins: sans_ins += 1
    ins_vus += ins
    if not p.get("managingOrganization"): sans_org += 1
    for t in p.get("meta", {}).get("tag", []):
        regions[t["code"]] += 1
    if "Diabetes mellitus" in texte: diab += 1
print("fichiers          :", len(fichiers))
print("sans INS          :", sans_ins)
print("INS uniques       :", len(set(ins_vus)) == len(ins_vus))
print("sans etablissement:", sans_org)
print("regions           :", dict(regions))
print("diabetiques       :", diab)
print("restes US         :", sum('"country": "US"' in open(f, encoding="utf-8").read() for f in fichiers))