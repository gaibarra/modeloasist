BEGIN;

ALTER TABLE public.employee_credentials OWNER TO gaibarra;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.employee_credentials TO gaibarra;
GRANT USAGE ON SCHEMA public TO gaibarra;

ALTER TABLE public.employee_credentials
  ADD COLUMN IF NOT EXISTS employee_id BIGINT,
  ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
  ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT TRUE;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'employee_credentials_pkey'
  ) THEN
    ALTER TABLE public.employee_credentials
      ADD CONSTRAINT employee_credentials_pkey PRIMARY KEY (employee_id);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'employee_credentials_employee_id_fkey'
  ) THEN
    ALTER TABLE public.employee_credentials
      ADD CONSTRAINT employee_credentials_employee_id_fkey
      FOREIGN KEY (employee_id)
      REFERENCES public.employees(id)
      ON DELETE CASCADE;
  END IF;
END $$;

INSERT INTO public.employee_credentials (employee_id, password_hash, must_change_password)
SELECT
  e.id,
  'pbkdf2_sha256$120000$9e52f61e1d8f6a6e0ab7de27a8d4e0d1$23a71b5d1256b1e9c71120342e22554e6cd8e44777fd192abcd2bf3104ea63d2',
  TRUE
FROM public.employees e
LEFT JOIN public.employee_credentials ec ON ec.employee_id = e.id
WHERE ec.employee_id IS NULL
  AND e.email IS NOT NULL
  AND btrim(e.email) <> '';

COMMIT;
