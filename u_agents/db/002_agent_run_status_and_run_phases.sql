CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'agent_runs'
          AND column_name = 'phase'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'agent_runs'
          AND column_name = 'status'
    ) THEN
        ALTER TABLE public.agent_runs RENAME COLUMN phase TO status;
    ELSIF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'agent_runs'
          AND column_name = 'phase'
    ) AND EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'agent_runs'
          AND column_name = 'status'
    ) THEN
        UPDATE public.agent_runs
        SET status = phase
        WHERE phase IS NOT NULL
          AND (status IS NULL OR status = 'claimed');

        ALTER TABLE public.agent_runs DROP COLUMN phase;
    END IF;
END
$$;

ALTER TABLE public.agent_runs
    DROP CONSTRAINT IF EXISTS agent_runs_phase_check,
    DROP CONSTRAINT IF EXISTS agent_runs_status_check,
    DROP CONSTRAINT IF EXISTS agent_runs_pr_phase_number_check,
    DROP CONSTRAINT IF EXISTS agent_runs_pr_status_number_check,
    DROP CONSTRAINT IF EXISTS agent_runs_block_reason_check,
    DROP CONSTRAINT IF EXISTS agent_runs_engineer_pane_check,
    DROP CONSTRAINT IF EXISTS agent_runs_reviewer_pane_check;

ALTER TABLE public.agent_runs
    DROP COLUMN IF EXISTS engineer_pane,
    DROP COLUMN IF EXISTS reviewer_pane;

ALTER TABLE public.agent_runs
    ALTER COLUMN status SET DEFAULT 'claimed',
    ALTER COLUMN status SET NOT NULL;

ALTER TABLE public.agent_runs
    ADD CONSTRAINT agent_runs_status_check
        CHECK (status IN (
            'claimed',
            'pm_started',
            'engineering',
            'reviewing',
            'fixing',
            'pr_open',
            'pr_watching',
            'ready_to_merge',
            'blocked',
            'done',
            'cancelled'
        )),
    ADD CONSTRAINT agent_runs_pr_status_number_check
        CHECK (
            status NOT IN ('pr_open', 'pr_watching', 'ready_to_merge')
            OR pr_number IS NOT NULL
        ),
    ADD CONSTRAINT agent_runs_block_reason_check
        CHECK (
            (status <> 'blocked' AND (block_reason IS NULL OR btrim(block_reason) <> ''))
            OR (status = 'blocked' AND block_reason IS NOT NULL AND btrim(block_reason) <> '')
        );

DROP INDEX IF EXISTS public.agent_runs_phase_lease_idx;

CREATE INDEX IF NOT EXISTS agent_runs_status_lease_idx
    ON public.agent_runs (status, lease_until);

CREATE TABLE IF NOT EXISTS public.run_phases (
    run_phase_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_run_id uuid NOT NULL REFERENCES public.agent_runs(run_id) ON DELETE CASCADE,
    phase_index integer NOT NULL,
    phase_key text NOT NULL,
    title text NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    block_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT run_phases_phase_index_check
        CHECK (phase_index > 0),
    CONSTRAINT run_phases_phase_key_check
        CHECK (btrim(phase_key) <> ''),
    CONSTRAINT run_phases_title_check
        CHECK (btrim(title) <> ''),
    CONSTRAINT run_phases_status_check
        CHECK (status IN (
            'pending',
            'in_progress',
            'reviewing',
            'fixing',
            'passed',
            'blocked',
            'cancelled'
        )),
    CONSTRAINT run_phases_metadata_object_check
        CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT run_phases_block_reason_check
        CHECK (
            (status <> 'blocked' AND (block_reason IS NULL OR btrim(block_reason) <> ''))
            OR (status = 'blocked' AND block_reason IS NOT NULL AND btrim(block_reason) <> '')
        ),
    CONSTRAINT run_phases_agent_run_phase_index_key
        UNIQUE (agent_run_id, phase_index),
    CONSTRAINT run_phases_agent_run_phase_key_key
        UNIQUE (agent_run_id, phase_key)
);

CREATE INDEX IF NOT EXISTS run_phases_agent_run_status_idx
    ON public.run_phases (agent_run_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS run_phases_one_active_idx
    ON public.run_phases (agent_run_id)
    WHERE status IN ('in_progress', 'reviewing', 'fixing');

DROP TRIGGER IF EXISTS run_phases_set_updated_at ON public.run_phases;

CREATE TRIGGER run_phases_set_updated_at
BEFORE UPDATE ON public.run_phases
FOR EACH ROW
EXECUTE FUNCTION public.set_agent_runs_updated_at();
