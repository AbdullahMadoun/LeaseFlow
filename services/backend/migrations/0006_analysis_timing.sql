-- LeaseFlow 0006: pipeline timing columns on loans.
--   analysis_started_at   — set when /analyze/start claims the loan
--                           (transitions pending_analysis → analyzing)
--   analysis_completed_at — set when expert synthesis writes the decision

BEGIN;

ALTER TABLE public.loans
  ADD COLUMN IF NOT EXISTS analysis_started_at   timestamptz,
  ADD COLUMN IF NOT EXISTS analysis_completed_at timestamptz;

-- No indexes — these are read per-loan, not scanned.

COMMIT;
