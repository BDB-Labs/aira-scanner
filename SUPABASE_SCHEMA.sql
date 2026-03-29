create extension if not exists pgcrypto;

create table if not exists public.aira_submissions (
  id uuid primary key default gen_random_uuid(),
  submitted_at timestamptz not null,
  source text not null,
  language text,
  engine text not null,
  scan_mode text,
  provider text,
  model text,
  target_kind text,
  files_scanned integer not null default 0,
  high_count integer not null default 0,
  medium_count integer not null default 0,
  low_count integer not null default 0,
  total_findings integer not null default 0,
  checks_failed integer not null default 0,
  checks_passed integer not null default 0,
  checks_unknown integer not null default 0,
  checks_json jsonb not null default '{}'::jsonb,
  check_count_json jsonb not null default '{}'::jsonb,
  check_severity_json jsonb not null default '{}'::jsonb,
  ci_workflow text,
  ci_run_id text,
  ci_ref text,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists aira_submissions_submitted_at_idx on public.aira_submissions (submitted_at desc);
create index if not exists aira_submissions_source_idx on public.aira_submissions (source);
create index if not exists aira_submissions_engine_idx on public.aira_submissions (engine);
