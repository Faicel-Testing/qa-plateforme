-- Open this file in pgAdmin's Query Tool, connected to the dedicated test database.
SELECT case_key, kind, active, version, payload
FROM qa_test_data.data_sets ORDER BY id;

SELECT run_id, environment, status, created_at, finished_at
FROM qa_test_data.test_runs ORDER BY created_at DESC;

SELECT a.id, a.run_id, a.scenario_id, d.case_key, a.status,
       a.application_state, a.reserved_at, a.released_at, a.outcome
FROM qa_test_data.data_allocations a
JOIN qa_test_data.data_sets d ON d.id = a.dataset_id
ORDER BY a.reserved_at DESC;

-- Do not automatically reuse reservations from an interrupted run.
-- First ensure its runner is stopped; then: npm.cmd run data:complete -- --run-id <id>
