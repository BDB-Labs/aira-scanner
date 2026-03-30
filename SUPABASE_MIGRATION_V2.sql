begin;

select set_config('aira.allow_mutation', 'on', true);

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

alter table public.aira_submissions add column if not exists sample_name text;
alter table public.aira_submissions add column if not exists sample_version text;
alter table public.aira_submissions add column if not exists attribution_class text;
alter table public.aira_submissions add column if not exists source_id text;
alter table public.aira_submissions add column if not exists source_kind text;
alter table public.aira_submissions add column if not exists scanner_name text;
alter table public.aira_submissions add column if not exists scanner_version text;
alter table public.aira_submissions add column if not exists ruleset_version text;
alter table public.aira_submissions add column if not exists scoring_version text;
alter table public.aira_submissions add column if not exists fti_score numeric(5,2);
alter table public.aira_submissions add column if not exists risk_level text;
alter table public.aira_submissions add column if not exists record_sha256 text;
alter table public.aira_submissions add column if not exists parent_record_sha256 text;
alter table public.aira_submissions add column if not exists submission_fingerprint text;

alter table public.aira_submissions alter column sample_version set default 'v1';
alter table public.aira_submissions alter column scanner_name set default 'aira';
alter table public.aira_submissions alter column scoring_version set default 'fti-v1';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'aira_submissions_attribution_class_check'
  ) then
    alter table public.aira_submissions
      add constraint aira_submissions_attribution_class_check
      check (attribution_class in ('explicit_ai', 'suspected_ai', 'human_baseline', 'unknown'));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'aira_submissions_source_kind_check'
  ) then
    alter table public.aira_submissions
      add constraint aira_submissions_source_kind_check
      check (source_kind in ('repo', 'directory', 'dataset_file', 'dataset_repo', 'ci_run', 'manual'));
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'aira_submissions_fti_score_check'
  ) then
    alter table public.aira_submissions
      add constraint aira_submissions_fti_score_check
      check (fti_score >= 0 and fti_score <= 100);
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'aira_submissions_risk_level_check'
  ) then
    alter table public.aira_submissions
      add constraint aira_submissions_risk_level_check
      check (risk_level in ('LOW_RISK', 'MODERATE_RISK', 'HIGH_RISK', 'CRITICAL_RISK'));
  end if;
end;
$$;

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

create index if not exists aira_submissions_sample_stream_idx
  on public.aira_submissions (sample_name, sample_version, submitted_at desc, created_at desc);
create index if not exists aira_submissions_source_id_idx on public.aira_submissions (source_id);
create unique index if not exists aira_submissions_submission_fingerprint_uidx
  on public.aira_submissions (submission_fingerprint);
create index if not exists aira_submission_checks_submission_idx on public.aira_submission_checks (submission_id);
create index if not exists aira_submission_checks_check_idx on public.aira_submission_checks (check_id);
create unique index if not exists aira_sample_manifests_sample_version_uidx
  on public.aira_sample_manifests (sample_name, sample_version);

update public.aira_submissions
set
  sample_name = coalesce(
    nullif(sample_name, ''),
    nullif(source_id, ''),
    case
      when source like 'github:%' then split_part(source, 'github:', 2)
      when source in ('aira-cli', 'aira.bageltech.net', 'ci') then 'legacy:' || id::text
      when nullif(source, '') is not null then source
      else 'legacy:' || id::text
    end
  ),
  sample_version = coalesce(nullif(sample_version, ''), 'v1'),
  attribution_class = coalesce(nullif(attribution_class, ''), 'unknown'),
  source_kind = coalesce(
    nullif(source_kind, ''),
    case
      when coalesce(ci_run_id, '') <> '' or coalesce(ci_workflow, '') <> '' then 'ci_run'
      when source like 'github:%' then 'repo'
      when target_kind = 'directory' then 'directory'
      when target_kind = 'file' then 'dataset_file'
      else 'manual'
    end
  ),
  scanner_name = coalesce(nullif(scanner_name, ''), 'aira'),
  scanner_version = coalesce(nullif(scanner_version, ''), nullif(metadata_json ->> 'scanner_version', ''), '1.2.0'),
  ruleset_version = coalesce(
    nullif(ruleset_version, ''),
    nullif(metadata_json ->> 'ruleset_version', ''),
    nullif(metadata_json ->> 'scanner_version', ''),
    '1.2.0'
  ),
  scoring_version = coalesce(nullif(scoring_version, ''), 'fti-v1');

with check_defs as (
  select *
  from (
    values
      ('C01', 'success_integrity', 'SUCCESS INTEGRITY', 3),
      ('C02', 'audit_integrity', 'AUDIT / EVIDENCE INTEGRITY', 3),
      ('C03', 'exception_handling', 'BROAD EXCEPTION SUPPRESSION', 3),
      ('C04', 'fallback_control', 'DISTRIBUTED FALLBACK / DEGRADED EXECUTION', 2),
      ('C05', 'bypass_controls', 'BYPASS / OVERRIDE PATHS', 2),
      ('C06', 'return_contracts', 'AMBIGUOUS RETURN CONTRACTS', 2),
      ('C07', 'logic_consistency', 'PARALLEL LOGIC DRIFT', 1),
      ('C08', 'background_tasks', 'UNSUPERVISED BACKGROUND TASKS', 1),
      ('C09', 'environment_safety', 'ENVIRONMENT-DEPENDENT SAFETY', 1),
      ('C10', 'startup_integrity', 'STARTUP INTEGRITY', 1),
      ('C11', 'determinism', 'DETERMINISTIC REASONING DRIFT', 2),
      ('C12', 'lineage', 'SOURCE-TO-OUTPUT LINEAGE', 1),
      ('C13', 'confidence_representation', 'CONFIDENCE MISREPRESENTATION', 3),
      ('C14', 'test_coverage_symmetry', 'TEST COVERAGE ASYMMETRY', 1),
      ('C15', 'idempotency_safety', 'RETRY / IDEMPOTENCY ASSUMPTION DRIFT', 2)
  ) as defs(check_id, check_key, check_name, weight)
),
expanded as (
  select
    s.id as submission_id,
    d.check_id,
    d.check_name,
    coalesce(upper(s.checks_json ->> d.check_key), 'UNKNOWN') as status,
    d.weight,
    coalesce((s.check_count_json ->> d.check_id)::integer, 0) as finding_count,
    coalesce((s.check_severity_json -> d.check_id ->> 'HIGH')::integer, 0) as high_count,
    coalesce((s.check_severity_json -> d.check_id ->> 'MEDIUM')::integer, 0) as medium_count,
    coalesce((s.check_severity_json -> d.check_id ->> 'LOW')::integer, 0) as low_count
  from public.aira_submissions s
  cross join check_defs d
)
insert into public.aira_submission_checks (
  submission_id,
  check_id,
  check_name,
  status,
  weight,
  finding_count,
  high_count,
  medium_count,
  low_count
)
select
  submission_id,
  check_id,
  check_name,
  case when status in ('PASS', 'FAIL', 'UNKNOWN') then status else 'UNKNOWN' end,
  weight,
  finding_count,
  high_count,
  medium_count,
  low_count
from expanded
on conflict (submission_id, check_id) do update
set
  check_name = excluded.check_name,
  status = excluded.status,
  weight = excluded.weight,
  finding_count = excluded.finding_count,
  high_count = excluded.high_count,
  medium_count = excluded.medium_count,
  low_count = excluded.low_count;

with scored as (
  select
    submission_id,
    round((100 - ((sum(case when status = 'FAIL' then weight else 0 end)::numeric / 28::numeric) * 100))::numeric, 2) as fti_score
  from public.aira_submission_checks
  group by submission_id
)
update public.aira_submissions s
set
  fti_score = scored.fti_score,
  risk_level = case
    when scored.fti_score >= 85.00 then 'LOW_RISK'
    when scored.fti_score >= 65.00 then 'MODERATE_RISK'
    when scored.fti_score >= 40.00 then 'HIGH_RISK'
    else 'CRITICAL_RISK'
  end
from scored
where s.id = scored.submission_id;

with checks_payload as (
  select
    c.submission_id,
    jsonb_agg(
      jsonb_build_object(
        'check_id', c.check_id,
        'check_name', c.check_name,
        'status', c.status,
        'weight', c.weight,
        'finding_count', c.finding_count,
        'high_count', c.high_count,
        'medium_count', c.medium_count,
        'low_count', c.low_count
      )
      order by c.check_id
    ) as submission_checks
  from public.aira_submission_checks c
  group by c.submission_id
),
fingerprints as (
  select
    s.id,
    encode(
      digest(
        (
          jsonb_build_object(
            'attribution_class', s.attribution_class,
            'checks_failed', s.checks_failed,
            'checks_json', s.checks_json,
            'checks_passed', s.checks_passed,
            'checks_unknown', s.checks_unknown,
            'ci_ref', s.ci_ref,
            'ci_run_id', s.ci_run_id,
            'ci_workflow', s.ci_workflow,
            'engine', s.engine,
            'files_scanned', s.files_scanned,
            'high_count', s.high_count,
            'language', s.language,
            'low_count', s.low_count,
            'medium_count', s.medium_count,
            'metadata_json', s.metadata_json,
            'model', s.model,
            'provider', s.provider,
            'ruleset_version', s.ruleset_version,
            'sample_name', s.sample_name,
            'sample_version', s.sample_version,
            'scanner_name', s.scanner_name,
            'scanner_version', s.scanner_version,
            'scan_mode', s.scan_mode,
            'scoring_version', s.scoring_version,
            'source', s.source,
            'source_id', s.source_id,
            'source_kind', s.source_kind,
            'submission_checks', coalesce(cp.submission_checks, '[]'::jsonb),
            'submitted_at', s.submitted_at,
            'target_kind', s.target_kind,
            'total_findings', s.total_findings
          )::text
        ),
        'sha256'
      ),
      'hex'
    ) as base_fingerprint
  from public.aira_submissions s
  left join checks_payload cp on cp.submission_id = s.id
),
deduped as (
  select
    id,
    case
      when count(*) over (partition by base_fingerprint) = 1 then base_fingerprint
      else base_fingerprint || ':' || row_number() over (partition by base_fingerprint order by id)
    end as submission_fingerprint
  from fingerprints
)
update public.aira_submissions s
set submission_fingerprint = d.submission_fingerprint
from deduped d
where s.id = d.id;

with checks_payload as (
  select
    c.submission_id,
    jsonb_agg(
      jsonb_build_object(
        'check_id', c.check_id,
        'check_name', c.check_name,
        'status', c.status,
        'weight', c.weight,
        'finding_count', c.finding_count,
        'high_count', c.high_count,
        'medium_count', c.medium_count,
        'low_count', c.low_count
      )
      order by c.check_id
    ) as submission_checks
  from public.aira_submission_checks c
  group by c.submission_id
),
record_hashes as (
  select
    s.id,
    encode(
      digest(
        (
          jsonb_build_object(
            'attribution_class', s.attribution_class,
            'check_count_json', s.check_count_json,
            'check_severity_json', s.check_severity_json,
            'checks_failed', s.checks_failed,
            'checks_json', s.checks_json,
            'checks_passed', s.checks_passed,
            'checks_unknown', s.checks_unknown,
            'ci_ref', s.ci_ref,
            'ci_run_id', s.ci_run_id,
            'ci_workflow', s.ci_workflow,
            'engine', s.engine,
            'files_scanned', s.files_scanned,
            'fti_score', s.fti_score,
            'high_count', s.high_count,
            'language', s.language,
            'low_count', s.low_count,
            'medium_count', s.medium_count,
            'metadata_json', s.metadata_json,
            'model', s.model,
            'provider', s.provider,
            'risk_level', s.risk_level,
            'ruleset_version', s.ruleset_version,
            'sample_name', s.sample_name,
            'sample_version', s.sample_version,
            'scanner_name', s.scanner_name,
            'scanner_version', s.scanner_version,
            'scan_mode', s.scan_mode,
            'scoring_version', s.scoring_version,
            'source', s.source,
            'source_id', s.source_id,
            'source_kind', s.source_kind,
            'submission_checks', coalesce(cp.submission_checks, '[]'::jsonb),
            'submission_fingerprint', s.submission_fingerprint,
            'submitted_at', s.submitted_at,
            'target_kind', s.target_kind,
            'total_findings', s.total_findings
          )::text
        ),
        'sha256'
      ),
      'hex'
    ) as record_sha256
  from public.aira_submissions s
  left join checks_payload cp on cp.submission_id = s.id
)
update public.aira_submissions s
set record_sha256 = rh.record_sha256
from record_hashes rh
where s.id = rh.id;

with ordered as (
  select
    id,
    lag(record_sha256) over (
      partition by sample_name, sample_version
      order by submitted_at, created_at, id
    ) as parent_record_sha256
  from public.aira_submissions
)
update public.aira_submissions s
set parent_record_sha256 = ordered.parent_record_sha256
from ordered
where s.id = ordered.id;

alter table public.aira_submissions alter column sample_name set not null;
alter table public.aira_submissions alter column sample_version set not null;
alter table public.aira_submissions alter column attribution_class set not null;
alter table public.aira_submissions alter column scanner_name set not null;
alter table public.aira_submissions alter column scanner_version set not null;
alter table public.aira_submissions alter column ruleset_version set not null;
alter table public.aira_submissions alter column scoring_version set not null;
alter table public.aira_submissions alter column fti_score set not null;
alter table public.aira_submissions alter column risk_level set not null;
alter table public.aira_submissions alter column record_sha256 set not null;
alter table public.aira_submissions alter column submission_fingerprint set not null;

drop trigger if exists aira_submissions_append_only_guard on public.aira_submissions;
create trigger aira_submissions_append_only_guard
before update or delete on public.aira_submissions
for each row execute function public.aira_reject_append_only_mutation();

drop trigger if exists aira_submission_checks_append_only_guard on public.aira_submission_checks;
create trigger aira_submission_checks_append_only_guard
before update or delete on public.aira_submission_checks
for each row execute function public.aira_reject_append_only_mutation();

commit;
