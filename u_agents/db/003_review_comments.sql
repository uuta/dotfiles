-- Durable per-comment PR review state.
--
-- `metadata.pr_review_comments` (JSONB on agent_runs) is no longer the source of
-- truth for PR review comment workflow state: shallow JSONB merges from multiple
-- writers corrupt shared top-level keys, and DB constraints (e.g. "addressed
-- requires a commit + verification summary") cannot be enforced on it. PR review
-- comment state therefore lives in this normalized table instead. The watcher
-- records what it observed (`watcher_verdict`); the PM records the resolution
-- (`pm_decision`, `resolution_status`, commit, verification). `mark_pr_open`
-- only re-arms the watcher and must not touch review comment resolution.

CREATE TABLE IF NOT EXISTS public.review_comments (
    agent_run_id uuid NOT NULL
        REFERENCES public.agent_runs(run_id)
        ON DELETE CASCADE,

    github_comment_id int8 NOT NULL,
    body_hash text NOT NULL,
    comment_key text GENERATED ALWAYS AS (
        github_comment_id::text || ':' || body_hash
    ) STORED,

    pr_number int4 NOT NULL,
    source text NOT NULL DEFAULT 'unknown',

    watcher_verdict text NOT NULL,
    pm_decision text NULL,
    resolution_status text NOT NULL DEFAULT 'unresolved',

    original_body text NULL,
    original_path text NULL,
    original_line int4 NULL,
    original_commit_sha text NULL,

    handed_off_at timestamptz NULL,
    resolved_at timestamptz NULL,
    addressed_by_commit_sha text NULL,

    verification_summary text NULL,
    verification_refs jsonb DEFAULT '[]'::jsonb NOT NULL,

    first_seen_at timestamptz DEFAULT now() NOT NULL,
    last_seen_at timestamptz DEFAULT now() NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,

    CONSTRAINT review_comments_pkey
        PRIMARY KEY (agent_run_id, comment_key),

    CONSTRAINT review_comments_pr_number_check
        CHECK (pr_number > 0),

    CONSTRAINT review_comments_body_hash_check
        CHECK (btrim(body_hash) <> ''),

    CONSTRAINT review_comments_source_check
        CHECK (source = ANY (ARRAY[
            'top_level',
            'review_body',
            'inline_review',
            'unknown'
        ])),

    CONSTRAINT review_comments_watcher_verdict_check
        CHECK (watcher_verdict = ANY (ARRAY[
            'valid_must_fix',
            'valid_optional',
            'invalid',
            'needs_user_judgment'
        ])),

    CONSTRAINT review_comments_pm_decision_check
        CHECK (
            pm_decision IS NULL OR
            pm_decision = ANY (ARRAY[
                'valid_must_fix',
                'valid_optional',
                'invalid',
                'needs_user_judgment'
            ])
        ),

    CONSTRAINT review_comments_resolution_status_check
        CHECK (resolution_status = ANY (ARRAY[
            'unresolved',
            'addressed',
            'rejected',
            'needs_user_judgment'
        ])),

    CONSTRAINT review_comments_verification_refs_array_check
        CHECK (jsonb_typeof(verification_refs) = 'array'),

    CONSTRAINT review_comments_resolved_at_check
        CHECK (
            (resolution_status = 'unresolved' AND resolved_at IS NULL)
            OR
            (resolution_status <> 'unresolved' AND resolved_at IS NOT NULL)
        ),

    CONSTRAINT review_comments_addressed_requires_commit_check
        CHECK (
            resolution_status <> 'addressed'
            OR (
                addressed_by_commit_sha IS NOT NULL
                AND btrim(addressed_by_commit_sha) <> ''
            )
        ),

    CONSTRAINT review_comments_addressed_requires_verification_check
        CHECK (
            resolution_status <> 'addressed'
            OR (
                verification_summary IS NOT NULL
                AND btrim(verification_summary) <> ''
            )
        ),

    CONSTRAINT review_comments_terminal_reason_check
        CHECK (
            resolution_status NOT IN ('rejected', 'needs_user_judgment')
            OR (
                verification_summary IS NOT NULL
                AND btrim(verification_summary) <> ''
            )
        )
);

CREATE INDEX IF NOT EXISTS review_comments_run_resolution_idx
    ON public.review_comments (agent_run_id, resolution_status);

CREATE INDEX IF NOT EXISTS review_comments_pr_idx
    ON public.review_comments (pr_number);

CREATE INDEX IF NOT EXISTS review_comments_last_seen_idx
    ON public.review_comments (last_seen_at);

DROP TRIGGER IF EXISTS review_comments_set_updated_at ON public.review_comments;

CREATE TRIGGER review_comments_set_updated_at
BEFORE UPDATE ON public.review_comments
FOR EACH ROW
EXECUTE FUNCTION set_agent_runs_updated_at();
