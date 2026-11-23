"""
Correspondance minimale codes source → concept_id OMOP pour la démo diabète.

Basée sur les codes RÉELLEMENT présents dans les Bundles d'exemple + les codes
diabète classiques pour la démo.

Règle : code inconnu → concept_id = 0, code d'origine conservé dans *_source_value.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# LOINC → measurement_concept_id (OMOP standard)
# Source : OMOP CDM Vocabulary, domaine Measurement
# ---------------------------------------------------------------------------
LOINC_TO_CONCEPT: dict[str, int] = {
    # --- Diabète démo (présents dans les Bundles) ---
    "4548-4":  3004410,   # Hemoglobin A1c/Hemoglobin.total in Blood
    "2339-0":  3000483,   # Glucose [Mass/volume] in Blood
    # --- Lipides / rénaux (présents dans les Bundles) ---
    "2093-3":  3027114,   # Cholesterol [Mass/volume] in Serum or Plasma
    "2571-8":  3022038,   # Triglyceride [Mass/volume] in Serum or Plasma
    "18262-6": 3028288,   # Cholesterol in LDL
    "2085-9":  3007070,   # Cholesterol in HDL
    "6299-2":  3013682,   # Urea nitrogen (BUN)
    "38483-4": 3016723,   # Creatinine in Blood
    "49765-1": 3006906,   # Calcium in Blood
    "14959-1": 3016908,   # Microalbumin/Creatinine
    "33914-3": 3053283,   # eGFR (MDRD)
    # --- Signes vitaux ---
    "8302-2":  3023540,   # Body Height
    "29463-7": 3025315,   # Body Weight
    "39156-5": 3038553,   # BMI
    "85354-9": 3004249,   # Blood pressure panel
    "8462-4":  3012888,   # Diastolic Blood Pressure
    "8480-6":  3004249,   # Systolic Blood Pressure (concept panel; composant individuel)
    "8867-4":  3027018,   # Heart rate
    "9279-1":  3024171,   # Respiratory rate
    "8310-5":  3020891,   # Body temperature
    # --- Hémogramme ---
    "6690-2":  3000905,   # Leukocytes
    "789-8":   3000291,   # Erythrocytes
    "718-7":   3000963,   # Hemoglobin in Blood
    "4544-3":  3009542,   # Hematocrit
    "777-3":   3007461,   # Platelets
}

# ---------------------------------------------------------------------------
# SNOMED → condition_concept_id (OMOP standard)
# Source : OMOP CDM Vocabulary, domaine Condition
# ---------------------------------------------------------------------------
SNOMED_CONDITION_TO_CONCEPT: dict[str, int] = {
    # --- Diabète et métabolisme (présents dans les Bundles) ---
    "44054006":  201826,  # Diabetes mellitus type 2
    "714628002": 4192640, # Prediabetes
    "80394007":  443727,  # Hyperglycemia
    "302870006": 437827,  # Hypertriglyceridemia
    "237602007": 439790,  # Metabolic syndrome X
    # --- Autres conditions présentes dans les Bundles ---
    "271737000": 439777,  # Anemia
    "162864005": 433736,  # Obesity (BMI 30+)
    "195662009": 4112343, # Acute viral pharyngitis
    "444814009": 4152648, # Viral sinusitis
    "66383009":  4059882, # Gingivitis
    "72892002":  4196406, # Normal pregnancy
    "73595000":  4178076, # Stress
}

# ---------------------------------------------------------------------------
# RxNorm → drug_concept_id (OMOP standard)
# Source : OMOP CDM Vocabulary, domaine Drug
# ---------------------------------------------------------------------------
RXNORM_TO_CONCEPT: dict[str, int] = {
    # --- Médicaments présents dans les Bundles ---
    "1535362": 0,         # sodium fluoride 0.0272 MG/MG Oral Gel  (pas de mapping OMOP direct)
    "389221":  1518254,   # Etonogestrel 68 MG Drug Implant
    "1605257": 1589505,   # levonorgestrel IUS [Liletta]
    "1000126": 1234870,   # medroxyprogesterone acetate 150 MG/ML Injection
    # --- Médicaments diabète pour la démo (hors Bundles actuels) ---
    "860975":  1503297,   # Metformin 500 MG Oral Tablet
    "860999":  1503297,   # Metformin 850 MG Oral Tablet
    "311040":  1516766,   # Insulin isophane, Human 70 UNT/ML / Insulin Regular, Human 30 UNT/ML
    "274783":  1516766,   # Insulin Regular, Human 100 UNT/ML Injection
    "372926":  1516766,   # Insulin Lispro 100 UNT/ML Injection
}


def concept_loinc(code: str) -> int:
    """Retourne le concept_id OMOP pour un code LOINC, 0 si inconnu."""
    return LOINC_TO_CONCEPT.get(code, 0)


def concept_snomed_condition(code: str) -> int:
    """Retourne le concept_id OMOP pour un code SNOMED Condition, 0 si inconnu."""
    return SNOMED_CONDITION_TO_CONCEPT.get(code, 0)


def concept_rxnorm(code: str) -> int:
    """Retourne le concept_id OMOP pour un code RxNorm, 0 si inconnu."""
    return RXNORM_TO_CONCEPT.get(code, 0)
