-- Synthetic reusable profiles. Credentials and application tokens are never stored.
INSERT INTO qa_test_data.data_sets(case_key, kind, payload)
SELECT 'user-' || n, 'user', jsonb_build_object(
  'firstName', (ARRAY['Anne','Luca','Mia','Noah'])[1 + (n % 4)],
  'lastName', 'QA' || n)
FROM generate_series(1, 200) AS n
ON CONFLICT (case_key) DO NOTHING;

INSERT INTO qa_test_data.data_sets(case_key,kind,payload) VALUES
 ('invalid-email','negative','{"email":"invalid-email"}'),
 ('empty-email','negative','{"email":""}'),
 ('weak-password','negative','{"password":"123"}')
ON CONFLICT (case_key) DO NOTHING;
