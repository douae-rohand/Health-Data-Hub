REGIONS = ["region_fes", "region_rabat", "region_tanger"]
OMOP_TABLES = ["person", "visit_occurrence", "condition_occurrence",
               "measurement", "drug_exposure"]

# --- Noms de colonnes confirmés par db/init/00_schema_omop.sql ---
PERSON_PSEUDO = "person_source_value"
PERSON_SEX = "gender_concept_id"
VISIT_START = "visit_start_datetime"
VISIT_END = "visit_end_datetime"
CONDITION_CONCEPT = "condition_concept_id"
MEASURE_CONCEPT = "measurement_concept_id"
MEASURE_VALUE = "value_as_number"
HBA1C_CONCEPT_ID = 3004410  # confirmé par app/mapping_codes.py (LOINC 4548-4)

# Codes de sexe : valeurs communes du guide (section 4)
VALID_SEX_CODES = [8507, 8532]

# Plage plausible de l'HbA1c : choix de Dev 4, pas du guide
HBA1C_MIN = 3.0
HBA1C_MAX = 20.0
