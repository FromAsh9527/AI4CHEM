-- TransferBO 2.0 experimental research database
-- SQLite dialect; also documented in docs/01_data_schema.md

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS reactions (
    reaction_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    template      TEXT,          -- e.g. Buchwald-Hartwig, Suzuki
    description   TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS substrates (
    substrate_id  TEXT PRIMARY KEY,
    reaction_id   TEXT NOT NULL REFERENCES reactions(reaction_id),
    name          TEXT,
    smiles        TEXT,
    smiles_elec   TEXT,          -- electrophile
    smiles_nuc    TEXT,          -- nucleophile
    scaffold      TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS plates (
    plate_id      TEXT PRIMARY KEY,
    reaction_id   TEXT NOT NULL REFERENCES reactions(reaction_id),
    date          TEXT,
    instrument_id TEXT,
    operator      TEXT,
    reagent_lot   TEXT,
    notes         TEXT,
    -- optional known bias for synthetic demos / audits
    bias_offset   REAL DEFAULT 0.0,
    bias_scale    REAL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS conditions (
    condition_id  TEXT PRIMARY KEY,
    reaction_id   TEXT NOT NULL REFERENCES reactions(reaction_id),
    -- discrete / continuous factors (nullable; unused factors left NULL)
    catalyst      TEXT,
    ligand        TEXT,
    base          TEXT,
    solvent       TEXT,
    temperature_c REAL,
    time_h        REAL,
    equiv         REAL,
    condition_json TEXT,         -- full vector as JSON if needed
    is_anchor     INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    reaction_id   TEXT NOT NULL REFERENCES reactions(reaction_id),
    substrate_id  TEXT NOT NULL REFERENCES substrates(substrate_id),
    plate_id      TEXT NOT NULL REFERENCES plates(plate_id),
    condition_id  TEXT NOT NULL REFERENCES conditions(condition_id),
    well          TEXT,
    row           INTEGER,
    col           INTEGER,
    date          TEXT,
    yield         REAL NOT NULL,
    selectivity   REAL,
    replicate     INTEGER DEFAULT 1,
    is_anchor     INTEGER DEFAULT 0,
    reagent_lot   TEXT,
    instrument_id TEXT,
    operator      TEXT,
    quality_flag  TEXT DEFAULT 'ok',
    source        TEXT DEFAULT 'demo',  -- demo | public | internal
    UNIQUE (substrate_id, plate_id, condition_id, replicate)
);

CREATE TABLE IF NOT EXISTS descriptors (
    descriptor_id TEXT PRIMARY KEY,
    entity_type   TEXT NOT NULL,  -- substrate | condition | reaction
    entity_id     TEXT NOT NULL,
    name          TEXT NOT NULL,  -- e.g. morgan_r2_n32, physchem_v1
    dim           INTEGER,
    vector_json   TEXT NOT NULL,  -- JSON array of floats
    UNIQUE (entity_type, entity_id, name)
);

CREATE TABLE IF NOT EXISTS anchors (
    anchor_id     TEXT PRIMARY KEY,
    reaction_id   TEXT NOT NULL REFERENCES reactions(reaction_id),
    condition_id  TEXT NOT NULL REFERENCES conditions(condition_id),
    role          TEXT,           -- high | mid | low | bridge
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS literature (
    cite_key      TEXT PRIMARY KEY,
    title         TEXT,
    year          INTEGER,
    doi           TEXT,
    tags          TEXT,           -- comma-separated
    path_note     TEXT,           -- relative path under data/literature/
    priority      INTEGER DEFAULT 2
);

CREATE INDEX IF NOT EXISTS idx_exp_substrate ON experiments(substrate_id);
CREATE INDEX IF NOT EXISTS idx_exp_plate ON experiments(plate_id);
CREATE INDEX IF NOT EXISTS idx_exp_condition ON experiments(condition_id);
CREATE INDEX IF NOT EXISTS idx_exp_reaction ON experiments(reaction_id);
CREATE INDEX IF NOT EXISTS idx_desc_entity ON descriptors(entity_type, entity_id);
