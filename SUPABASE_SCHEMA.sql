create extension if not exists pgcrypto;

create or replace function public.aira_reject_append_only_mutation()
returns trigger
language plpgsql
as $$
begin
  if current_setting('aira.allow_mutation', true) = 'on' then
    if tg_op = 'DELETE' then
      return old;
    end if;
    return new;
  end if;

  raise exception '% is append-only; use the controlled migration/backfill path to mutate prior rows.', tg_table_name;
end;
$$;

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
  sample_name text not null,
  sample_version text not null default 'v1',
  attribution_class text not null check (attribution_class in ('explicit_ai', 'suspected_ai', 'human_baseline', 'unknown')),
  source_id text,
  source_kind text check (source_kind in ('repo', 'directory', 'dataset_file', 'dataset_repo', 'ci_run', 'manual')),
  scanner_name text not null default 'aira',
  scanner_version text not null,
  ruleset_version text not null,
  scoring_version text not null default 'fti-v1',
  fti_score numeric(5,2) not null check (fti_score >= 0 and fti_score <= 100),
  risk_level text not null check (risk_level in ('LOW_RISK', 'MODERATE_RISK', 'HIGH_RISK', 'CRITICAL_RISK')),
  record_sha256 text not null,
  parent_record_sha256 text,
  submission_fingerprint text not null unique,
  created_at timestamptz not null default now()
);

create index if not exists aira_submissions_submitted_at_idx on public.aira_submissions (submitted_at desc);
create index if not exists aira_submissions_source_idx on public.aira_submissions (source);
create index if not exists aira_submissions_engine_idx on public.aira_submissions (engine);
create index if not exists aira_submissions_sample_stream_idx
  on public.aira_submissions (sample_name, sample_version, submitted_at desc, created_at desc);
create index if not exists aira_submissions_source_id_idx on public.aira_submissions (source_id);
create unique index if not exists aira_submissions_submission_fingerprint_uidx
  on public.aira_submissions (submission_fingerprint);

create table if not exists public.aira_submission_checks (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null references public.aira_submissions(id) on delete cascade,
  check_id text not null,
  check_name text not null,
  status text not null check (status in ('PASS', 'FAIL', 'UNKNOWN')),
  weight integer not null check (weight >= 1),
  finding_count integer not null default 0,
  high_count integer not null default 0,
  medium_count integer not null default 0,
  low_count integer not null default 0,
  unique(submission_id, check_id)
);

create index if not exists aira_submission_checks_submission_idx on public.aira_submission_checks (submission_id);
create index if not exists aira_submission_checks_check_idx on public.aira_submission_checks (check_id);

create table if not exists public.aira_sample_manifests (
  sample_name text not null,
  sample_version text not null,
  sampling_method text not null,
  sampling_frame text not null,
  inclusion_criteria jsonb not null default '{}'::jsonb,
  exclusion_criteria jsonb not null default '{}'::jsonb,
  attribution_policy text not null,
  random_seed text,
  scanner_version text not null,
  ruleset_version text not null,
  scoring_version text not null,
  manifest_sha256 text not null,
  notes text,
  unique(sample_name, sample_version)
);

create unique index if not exists aira_sample_manifests_sample_version_uidx
  on public.aira_sample_manifests (sample_name, sample_version);

drop trigger if exists aira_submissions_append_only_guard on public.aira_submissions;
create trigger aira_submissions_append_only_guard
before update or delete on public.aira_submissions
for each row execute function public.aira_reject_append_only_mutation();

drop trigger if exists aira_submission_checks_append_only_guard on public.aira_submission_checks;
create trigger aira_submission_checks_append_only_guard
before update or delete on public.aira_submission_checks
for each row execute function public.aira_reject_append_only_mutation();
