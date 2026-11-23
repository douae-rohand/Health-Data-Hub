-- =============================================================================
-- Schéma OMOP CDM minimal pour le Health Data Hub G3
-- 3 schémas régionaux × 5 tables chacun
-- Idempotent : CREATE SCHEMA / TABLE IF NOT EXISTS
-- =============================================================================

DO $$
DECLARE
    region TEXT;
    regions TEXT[] := ARRAY['region_fes', 'region_rabat', 'region_tanger'];
BEGIN
    FOREACH region IN ARRAY regions LOOP

        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', region);

        -- -----------------------------------------------------------------
        -- person
        -- Aucune colonne nominative : pas de nom, pas de date de naissance,
        -- pas d'adresse.  person_source_value = pseudonyme (P-XXXXXXXX).
        -- -----------------------------------------------------------------
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.person (
                person_id               BIGSERIAL    PRIMARY KEY,
                person_source_value     TEXT         NOT NULL UNIQUE,  -- pseudonyme
                gender_concept_id       INTEGER      NOT NULL,          -- 8507 | 8532
                tranche_age             TEXT         NOT NULL,          -- "0-4" … "85+"
                race_concept_id         INTEGER      NOT NULL DEFAULT 0,
                ethnicity_concept_id    INTEGER      NOT NULL DEFAULT 0
            )', region);

        -- -----------------------------------------------------------------
        -- visit_occurrence
        -- -----------------------------------------------------------------
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.visit_occurrence (
                visit_occurrence_id         BIGSERIAL   PRIMARY KEY,
                person_id                   BIGINT      NOT NULL REFERENCES %I.person(person_id),
                visit_concept_id            INTEGER     NOT NULL DEFAULT 0,
                visit_start_datetime        TIMESTAMPTZ,
                visit_end_datetime          TIMESTAMPTZ,
                visit_type_concept_id       INTEGER     NOT NULL DEFAULT 32817,
                visit_source_value          TEXT,         -- fullUrl urn:uuid:…
                care_site_source_value      TEXT          -- établissement_id
            )', region, region);

        -- -----------------------------------------------------------------
        -- condition_occurrence
        -- -----------------------------------------------------------------
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.condition_occurrence (
                condition_occurrence_id     BIGSERIAL   PRIMARY KEY,
                person_id                   BIGINT      NOT NULL REFERENCES %I.person(person_id),
                visit_occurrence_id         BIGINT      REFERENCES %I.visit_occurrence(visit_occurrence_id),
                condition_concept_id        INTEGER     NOT NULL DEFAULT 0,
                condition_start_datetime    TIMESTAMPTZ,
                condition_end_datetime      TIMESTAMPTZ,
                condition_type_concept_id   INTEGER     NOT NULL DEFAULT 32020,
                condition_source_value      TEXT,         -- système|code
                condition_source_concept_id INTEGER     NOT NULL DEFAULT 0
            )', region, region, region);

        -- -----------------------------------------------------------------
        -- measurement
        -- -----------------------------------------------------------------
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.measurement (
                measurement_id              BIGSERIAL   PRIMARY KEY,
                person_id                   BIGINT      NOT NULL REFERENCES %I.person(person_id),
                visit_occurrence_id         BIGINT      REFERENCES %I.visit_occurrence(visit_occurrence_id),
                measurement_concept_id      INTEGER     NOT NULL DEFAULT 0,
                measurement_datetime        TIMESTAMPTZ,
                measurement_type_concept_id INTEGER     NOT NULL DEFAULT 32817,
                value_as_number             NUMERIC,
                unit_concept_id             INTEGER     NOT NULL DEFAULT 0,
                unit_source_value           TEXT,
                measurement_source_value    TEXT,         -- système|code
                value_source_value          TEXT
            )', region, region, region);

        -- -----------------------------------------------------------------
        -- drug_exposure
        -- -----------------------------------------------------------------
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I.drug_exposure (
                drug_exposure_id            BIGSERIAL   PRIMARY KEY,
                person_id                   BIGINT      NOT NULL REFERENCES %I.person(person_id),
                visit_occurrence_id         BIGINT      REFERENCES %I.visit_occurrence(visit_occurrence_id),
                drug_concept_id             INTEGER     NOT NULL DEFAULT 0,
                drug_exposure_start_datetime TIMESTAMPTZ,
                drug_exposure_end_datetime  TIMESTAMPTZ,
                drug_type_concept_id        INTEGER     NOT NULL DEFAULT 32817,
                drug_source_value           TEXT,         -- système|code
                drug_source_concept_id      INTEGER     NOT NULL DEFAULT 0,
                quantity                    NUMERIC
            )', region, region, region);

    END LOOP;
END $$;
