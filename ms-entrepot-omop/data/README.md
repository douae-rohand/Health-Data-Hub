# Données de test : patients FHIR marocanisés

Ces données sont fictives (Synthea) puis adaptées au contexte marocain.

## Contenu du dossier
- `etablissements.csv` : liste des hôpitaux (`etablissement_id,nom,region`).
- `samples/` : 3 Bundles d'exemple, versionnés dans git.
  - `exemple_diabete_type2_fes.json`
  - `exemple_prediabete_rabat.json`
  - `exemple_sain_tanger.json`
- `generated/` : jeu complet (~1 121 patients), **ignoré par git**, à régénérer.

## Où sont les informations dans un Bundle
- **INS** : `Patient.identifier`, `system = urn:ma:ins`, valeur `INS-MA-2026-XXXXXXXX`.
- **Établissement** : ressource `Organization` (`identifier.system = urn:ma:etablissement`), référencée par `Patient.managingOrganization` et `Encounter.serviceProvider`.
- **Région** : `meta.tag`, `system = urn:ma:region` (`region_fes`, `region_rabat`, `region_tanger`).

## Régénérer le jeu complet
Prérequis : Java 17+, Python 3, Git.

1. Cloner Synthea à la version exacte utilisée :
   ```
   git clone https://github.com/synthetichealth/synthea.git
   cd synthea
   git checkout 5441eef7de9867babcde1551640b78f3e0119594
   ```
2. Générer les patients (graine fixe) :
   ```
   .\run_synthea.bat -p 1000 -s 42 --exporter.baseDirectory=./output_1000
   ```
3. Marocaniser :
   ```
   python <chemin>\ms-entrepot-omop\scripts\marocaniser.py --input output_1000\fhir --output <chemin>\ms-entrepot-omop\data\generated --etablissements <chemin>\ms-entrepot-omop\data\etablissements.csv --seed 42
   ```
4. Contrôler :
   ```
   python <chemin>\ms-entrepot-omop\scripts\controler.py <chemin>\ms-entrepot-omop\data\generated
   ```

## Résultat attendu (graine 42)
- 1 121 fichiers (1 000 vivants + 121 décédés)
- Tous avec INS unique, établissement et région
- Régions : fes 374, rabat 374, tanger 373
- Environ 74 fichiers mentionnant un diabète (« Diabetes mellitus »)

## Remarques
- Le format de l'INS vient du contrat de `ms-identite-ins` (à confirmer avec G1). Les constantes sont en haut de `marocaniser.py`.
- Le script écrit `patient_XXXX.json`. Les 3 exemples de `samples/` ont été renommés à la main : relancer le script vers `samples/` créerait de nouveaux fichiers sans écraser les exemples renommés.
- Les noms de patients, l'INS et les adresses sont entièrement fictifs.