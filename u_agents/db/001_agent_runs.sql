CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_full_name text NOT NULL,
    github_issue_number integer NOT NULL,
    parent_branch text NOT NULL,
    branch_name text NOT NULL,
    phase text NOT NULL DEFAULT 'claimed',
    runner_id text NOT NULL,
    machine_id text NOT NULL,
    locked_by text,
    lease_until timestamptz,
    worktree_basename text NOT NULL,
    tmux_window text NOT NULL,
    pm_pane text,
    engineer_pane text,
    reviewer_pane text,
    review_result_relative_path text NOT NULL DEFAULT 'tmp/review-result.json',
    pr_number integer,
    pr_review_fix_rounds integer NOT NULL DEFAULT 0,
    block_reason text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT agent_runs_repository_full_name_check
        CHECK (repository_full_name ~ '^[^/[:space:]]+/[^/[:space:]]+$'),
    CONSTRAINT agent_runs_github_issue_number_check
        CHECK (github_issue_number > 0),
    CONSTRAINT agent_runs_parent_branch_check
        CHECK (btrim(parent_branch) <> '' AND parent_branch !~ '[[:space:]]'),
    CONSTRAINT agent_runs_branch_name_check
        CHECK (btrim(branch_name) <> '' AND branch_name !~ '[[:space:]]'),
    CONSTRAINT agent_runs_phase_check
        CHECK (phase IN (
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
    CONSTRAINT agent_runs_runner_id_check
        CHECK (btrim(runner_id) <> ''),
    CONSTRAINT agent_runs_machine_id_check
        CHECK (btrim(machine_id) <> ''),
    CONSTRAINT agent_runs_locked_by_check
        CHECK (locked_by IS NULL OR btrim(locked_by) <> ''),
    CONSTRAINT agent_runs_lease_pair_check
        CHECK ((locked_by IS NULL) = (lease_until IS NULL)),
    CONSTRAINT agent_runs_worktree_basename_check
        CHECK (
            btrim(worktree_basename) <> ''
            AND worktree_basename NOT IN ('.', '..')
            AND worktree_basename !~ '[[:space:]]'
            AND worktree_basename !~ '[/\\]'
        ),
    CONSTRAINT agent_runs_tmux_window_check
        CHECK (btrim(tmux_window) <> ''),
    CONSTRAINT agent_runs_pm_pane_check
        CHECK (pm_pane IS NULL OR btrim(pm_pane) <> ''),
    CONSTRAINT agent_runs_engineer_pane_check
        CHECK (engineer_pane IS NULL OR btrim(engineer_pane) <> ''),
    CONSTRAINT agent_runs_reviewer_pane_check
        CHECK (reviewer_pane IS NULL OR btrim(reviewer_pane) <> ''),
    CONSTRAINT agent_runs_review_result_relative_path_check
        CHECK (review_result_relative_path = 'tmp/review-result.json'),
    CONSTRAINT agent_runs_pr_number_check
        CHECK (pr_number IS NULL OR pr_number > 0),
    CONSTRAINT agent_runs_pr_phase_number_check
        CHECK (
            phase NOT IN ('pr_open', 'pr_watching', 'ready_to_merge')
            OR pr_number IS NOT NULL
        ),
    CONSTRAINT agent_runs_pr_review_fix_rounds_check
        CHECK (pr_review_fix_rounds >= 0),
    CONSTRAINT agent_runs_metadata_object_check
        CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT agent_runs_block_reason_check
        CHECK (
            (phase <> 'blocked' AND (block_reason IS NULL OR btrim(block_reason) <> ''))
            OR (phase = 'blocked' AND block_reason IS NOT NULL AND btrim(block_reason) <> '')
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_runs_repository_issue_key
    ON agent_runs (repository_full_name, github_issue_number);

CREATE INDEX IF NOT EXISTS agent_runs_phase_lease_idx
    ON agent_runs (phase, lease_until);

CREATE INDEX IF NOT EXISTS agent_runs_runner_machine_idx
    ON agent_runs (runner_id, machine_id);

CREATE OR REPLACE FUNCTION set_agent_runs_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS agent_runs_set_updated_at ON agent_runs;

CREATE TRIGGER agent_runs_set_updated_at
BEFORE UPDATE ON agent_runs
FOR EACH ROW
EXECUTE FUNCTION set_agent_runs_updated_at();
