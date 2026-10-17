-- Execute in a database dedicated to test data, never in the application database.
BEGIN;
SELECT pg_advisory_xact_lock(72814001);
CREATE SCHEMA IF NOT EXISTS qa_test_data;
CREATE TABLE IF NOT EXISTS qa_test_data.test_runs (
  run_id text PRIMARY KEY,
  environment text NOT NULL,
  status text NOT NULL DEFAULT 'prepared' CHECK (status IN ('prepared','completed','interrupted')),
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE TABLE IF NOT EXISTS qa_test_data.data_sets (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  case_key text NOT NULL UNIQUE,
  kind text NOT NULL CHECK (kind IN ('user','negative')),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  active boolean NOT NULL DEFAULT true,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0)
);
CREATE TABLE IF NOT EXISTS qa_test_data.data_allocations (
  id uuid PRIMARY KEY,
  run_id text NOT NULL REFERENCES qa_test_data.test_runs(run_id),
  scenario_id text NOT NULL,
  dataset_id bigint NOT NULL REFERENCES qa_test_data.data_sets(id),
  status text NOT NULL DEFAULT 'reserved' CHECK (status IN ('reserved','released')),
  application_state text NOT NULL DEFAULT 'not_created'
    CHECK (application_state IN ('not_created','created','creation_failed','unknown')),
  email text NOT NULL,
  reserved_at timestamptz NOT NULL DEFAULT now(),
  released_at timestamptz,
  outcome text
);
-- A dataset is reserved by only one scenario at a time, across all workers.
CREATE UNIQUE INDEX IF NOT EXISTS data_one_active_reservation
  ON qa_test_data.data_allocations(dataset_id) WHERE status = 'reserved';
CREATE INDEX IF NOT EXISTS data_allocations_run ON qa_test_data.data_allocations(run_id);
COMMIT;
