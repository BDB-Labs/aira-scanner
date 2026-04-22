import crypto from 'node:crypto';

export const CHECK_DEFINITIONS = [
  { ordinal: 1, check_id: 'C01', check_key: 'success_integrity', check_name: 'SUCCESS INTEGRITY', weight: 3 },
  { ordinal: 2, check_id: 'C02', check_key: 'audit_integrity', check_name: 'AUDIT / EVIDENCE INTEGRITY', weight: 3 },
  { ordinal: 3, check_id: 'C03', check_key: 'exception_handling', check_name: 'BROAD EXCEPTION SUPPRESSION', weight: 3 },
  {
    ordinal: 4,
    check_id: 'C04',
    check_key: 'fallback_control',
    check_name: 'DISTRIBUTED FALLBACK / DEGRADED EXECUTION',
    weight: 2,
  },
  { ordinal: 5, check_id: 'C05', check_key: 'bypass_controls', check_name: 'BYPASS / OVERRIDE PATHS', weight: 2 },
  { ordinal: 6, check_id: 'C06', check_key: 'return_contracts', check_name: 'AMBIGUOUS RETURN CONTRACTS', weight: 2 },
  { ordinal: 7, check_id: 'C07', check_key: 'logic_consistency', check_name: 'PARALLEL LOGIC DRIFT', weight: 1 },
  { ordinal: 8, check_id: 'C08', check_key: 'background_tasks', check_name: 'UNSUPERVISED BACKGROUND TASKS', weight: 1 },
  {
    ordinal: 9,
    check_id: 'C09',
    check_key: 'environment_safety',
    check_name: 'ENVIRONMENT-DEPENDENT SAFETY',
    weight: 1,
  },
  { ordinal: 10, check_id: 'C10', check_key: 'startup_integrity', check_name: 'STARTUP INTEGRITY', weight: 1 },
  {
    ordinal: 11,
    check_id: 'C11',
    check_key: 'determinism',
    check_name: 'DETERMINISTIC REASONING DRIFT',
    weight: 2,
  },
  { ordinal: 12, check_id: 'C12', check_key: 'lineage', check_name: 'SOURCE-TO-OUTPUT LINEAGE', weight: 1 },
  {
    ordinal: 13,
    check_id: 'C13',
    check_key: 'confidence_representation',
    check_name: 'CONFIDENCE MISREPRESENTATION',
    weight: 3,
  },
  {
    ordinal: 14,
    check_id: 'C14',
    check_key: 'test_coverage_symmetry',
    check_name: 'TEST COVERAGE ASYMMETRY',
    weight: 1,
  },
  {
    ordinal: 15,
    check_id: 'C15',
    check_key: 'idempotency_safety',
    check_name: 'RETRY / IDEMPOTENCY ASSUMPTION DRIFT',
    weight: 2,
  },
];

const CHECK_DEFINITION_BY_ID = Object.fromEntries(CHECK_DEFINITIONS.map(def => [def.check_id, def]));
const CHECK_DEFINITION_BY_KEY = Object.fromEntries(CHECK_DEFINITIONS.map(def => [def.check_key, def]));
const VALID_ATTRIBUTION_CLASSES = new Set(['explicit_ai', 'suspected_ai', 'human_baseline', 'unknown']);
const VALID_SOURCE_KINDS = new Set(['repo', 'directory', 'dataset_file', 'dataset_repo', 'ci_run', 'manual']);
const VALID_CHECK_STATUSES = new Set(['PASS', 'FAIL', 'UNKNOWN']);
const DEFAULT_SCANNER_VERSION = '1.2.1';
const DEFAULT_SCORING_VERSION = 'fti-v1';

export const FTI_V1_TOTAL_WEIGHT = CHECK_DEFINITIONS.reduce((sum, def) => sum + def.weight, 0);

function nonEmptyString(value) {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function normalizeInteger(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.trunc(number));
}

function normalizeDecimal(value) {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) return 0;
  return number;
}

function parseObject(value) {
  if (!value) return {};
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
    } catch {
      return {};
    }
  }
  return typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function sortValue(value) {
  if (Array.isArray(value)) return value.map(sortValue);
  if (value && typeof value === 'object' && !(value instanceof Date)) {
    return Object.keys(value)
      .sort()
      .reduce((acc, key) => {
        acc[key] = sortValue(value[key]);
        return acc;
      }, {});
  }
  if (typeof value === 'number' && !Number.isFinite(value)) return null;
  return value;
}

export function canonicalize(value) {
  return JSON.stringify(sortValue(value));
}

export function sha256Hex(value) {
  return crypto.createHash('sha256').update(String(value)).digest('hex');
}

function normalizeStatus(value) {
  const normalized = String(value || 'UNKNOWN').toUpperCase();
  return VALID_CHECK_STATUSES.has(normalized) ? normalized : 'UNKNOWN';
}

function normalizeAttributionClass(value) {
  const normalized = nonEmptyString(value) || 'unknown';
  if (!VALID_ATTRIBUTION_CLASSES.has(normalized)) {
    throw new Error(
      `Invalid attribution_class '${normalized}'. Expected one of: explicit_ai, suspected_ai, human_baseline, unknown.`
    );
  }
  return normalized;
}

function normalizeSourceKind(value) {
  const normalized = nonEmptyString(value);
  if (!normalized) return null;
  if (!VALID_SOURCE_KINDS.has(normalized)) {
    throw new Error(
      `Invalid source_kind '${normalized}'. Expected one of: repo, directory, dataset_file, dataset_repo, ci_run, manual.`
    );
  }
  return normalized;
}

function normalizeScoringVersion(value) {
  const normalized = nonEmptyString(value) || DEFAULT_SCORING_VERSION;
  if (normalized !== DEFAULT_SCORING_VERSION) {
    throw new Error(`Unsupported scoring_version '${normalized}'. Only fti-v1 is currently supported.`);
  }
  return normalized;
}

function engineLabel(meta = {}, body = {}) {
  if (body.engine) return body.engine;
  if (meta.engine_label) return meta.engine_label;
  if (meta.provider && meta.model) return `${meta.provider}:${meta.model}`;
  return meta.engine || meta.mode || 'unknown';
}

export function normalizeCheckCounts(raw = {}) {
  const counts = Object.fromEntries(CHECK_DEFINITIONS.map(def => [def.check_id, 0]));
  for (const [key, value] of Object.entries(parseObject(raw))) {
    const definition = CHECK_DEFINITION_BY_ID[key] || CHECK_DEFINITION_BY_KEY[key];
    if (!definition) continue;
    counts[definition.check_id] = normalizeInteger(value);
  }
  return counts;
}

export function normalizeCheckSeverity(raw = {}) {
  const matrix = Object.fromEntries(
    CHECK_DEFINITIONS.map(def => [def.check_id, { HIGH: 0, MEDIUM: 0, LOW: 0, TOTAL: 0 }])
  );
  for (const [key, bucket] of Object.entries(parseObject(raw))) {
    const definition = CHECK_DEFINITION_BY_ID[key] || CHECK_DEFINITION_BY_KEY[key];
    if (!definition) continue;
    const parsedBucket = parseObject(bucket);
    const high = normalizeInteger(parsedBucket.HIGH);
    const medium = normalizeInteger(parsedBucket.MEDIUM);
    const low = normalizeInteger(parsedBucket.LOW);
    const total = normalizeInteger(parsedBucket.TOTAL || high + medium + low);
    matrix[definition.check_id] = { HIGH: high, MEDIUM: medium, LOW: low, TOTAL: total };
  }
  return matrix;
}

export function normalizeChecksJson(raw = {}) {
  const input = parseObject(raw);
  return Object.fromEntries(
    CHECK_DEFINITIONS.map(def => [def.check_key, normalizeStatus(input[def.check_key] ?? input[def.check_id])])
  );
}

export function buildSubmissionChecks(checksRaw = {}, checkCountsRaw = {}, checkSeverityRaw = {}) {
  const checksJson = normalizeChecksJson(checksRaw);
  const checkCounts = normalizeCheckCounts(checkCountsRaw);
  const checkSeverity = normalizeCheckSeverity(checkSeverityRaw);

  return CHECK_DEFINITIONS.map(def => {
    const severity = checkSeverity[def.check_id];
    return {
      check_id: def.check_id,
      check_name: def.check_name,
      check_key: def.check_key,
      status: checksJson[def.check_key],
      weight: def.weight,
      finding_count: checkCounts[def.check_id],
      high_count: severity.HIGH,
      medium_count: severity.MEDIUM,
      low_count: severity.LOW,
    };
  });
}

export function computeFTIScore(checksOrRows = {}) {
  const rows = Array.isArray(checksOrRows)
    ? checksOrRows
    : buildSubmissionChecks(checksOrRows, {}, {});
  const failedWeight = rows.reduce((sum, row) => sum + (row.status === 'FAIL' ? row.weight : 0), 0);
  const score = 100 - (failedWeight / FTI_V1_TOTAL_WEIGHT) * 100;
  return Math.round((score + Number.EPSILON) * 100) / 100;
}

export function riskLevelFromFTI(score) {
  if (score >= 85) return 'LOW_RISK';
  if (score >= 65) return 'MODERATE_RISK';
  if (score >= 40) return 'HIGH_RISK';
  return 'CRITICAL_RISK';
}

function inferSourceKind({ sourceKind, sourceId, source, targetKind, ciRunId, ciWorkflow }) {
  const explicit = normalizeSourceKind(sourceKind);
  if (explicit) return explicit;
  if (nonEmptyString(ciRunId) || nonEmptyString(ciWorkflow)) return 'ci_run';
  if (String(source || '').startsWith('github:')) return 'repo';
  if (nonEmptyString(sourceId) && String(sourceId).includes('/')) return 'repo';
  if (targetKind === 'directory') return 'directory';
  if (targetKind === 'file') return 'dataset_file';
  return 'manual';
}

function resolveSampleName({ requestedSampleName, sourceKind, sourceId, source, targetName, fallbackSeed }) {
  const explicit = nonEmptyString(requestedSampleName);
  if (explicit) return explicit;
  if (nonEmptyString(sourceId)) return sourceId;
  if (String(source || '').startsWith('github:')) return String(source).slice('github:'.length);
  if (sourceKind === 'repo' || sourceKind === 'dataset_repo') {
    const sourceLabel = nonEmptyString(source);
    if (sourceLabel) return sourceLabel;
  }
  if (nonEmptyString(targetName)) return targetName;
  return `adhoc:${sha256Hex(fallbackSeed).slice(0, 16)}`;
}

function buildFingerprintPayload(record, submissionChecks) {
  return {
    attribution_class: record.attribution_class,
    checks_failed: record.checks_failed,
    checks_json: record.checks_json,
    checks_passed: record.checks_passed,
    checks_unknown: record.checks_unknown,
    ci_ref: record.ci_ref,
    ci_run_id: record.ci_run_id,
    ci_workflow: record.ci_workflow,
    engine: record.engine,
    files_scanned: record.files_scanned,
    high_count: record.high_count,
    language: record.language,
    low_count: record.low_count,
    medium_count: record.medium_count,
    metadata_json: record.metadata_json,
    model: record.model,
    provider: record.provider,
    ruleset_version: record.ruleset_version,
    sample_name: record.sample_name,
    sample_version: record.sample_version,
    scanner_name: record.scanner_name,
    scanner_version: record.scanner_version,
    scan_mode: record.scan_mode,
    scoring_version: record.scoring_version,
    source: record.source,
    source_id: record.source_id,
    source_kind: record.source_kind,
    submission_checks: submissionChecks.map(({ check_id, status, weight, finding_count, high_count, medium_count, low_count }) => ({
      check_id,
      status,
      weight,
      finding_count,
      high_count,
      medium_count,
      low_count,
    })),
    target_kind: record.target_kind,
    total_findings: record.total_findings,
  };
}

function buildPersistedPayload(record, submissionChecks) {
  return {
    attribution_class: record.attribution_class,
    check_count_json: record.check_count_json,
    check_severity_json: record.check_severity_json,
    checks_failed: record.checks_failed,
    checks_json: record.checks_json,
    checks_passed: record.checks_passed,
    checks_unknown: record.checks_unknown,
    ci_ref: record.ci_ref,
    ci_run_id: record.ci_run_id,
    ci_workflow: record.ci_workflow,
    engine: record.engine,
    files_scanned: record.files_scanned,
    fti_score: record.fti_score,
    high_count: record.high_count,
    language: record.language,
    low_count: record.low_count,
    medium_count: record.medium_count,
    metadata_json: record.metadata_json,
    model: record.model,
    parent_record_sha256: record.parent_record_sha256,
    provider: record.provider,
    risk_level: record.risk_level,
    ruleset_version: record.ruleset_version,
    sample_name: record.sample_name,
    sample_version: record.sample_version,
    scanner_name: record.scanner_name,
    scanner_version: record.scanner_version,
    scan_mode: record.scan_mode,
    scoring_version: record.scoring_version,
    source: record.source,
    source_id: record.source_id,
    source_kind: record.source_kind,
    submission_checks: submissionChecks.map(
      ({ check_id, check_name, status, weight, finding_count, high_count, medium_count, low_count }) => ({
        check_id,
        check_name,
        status,
        weight,
        finding_count,
        high_count,
        medium_count,
        low_count,
      })
    ),
    submission_fingerprint: record.submission_fingerprint,
    submitted_at: record.submitted_at,
    target_kind: record.target_kind,
    total_findings: record.total_findings,
  };
}

export function buildSupabaseSubmissionBundle(body = {}, env = process.env) {
  const meta = parseObject(body.meta || body.metadata_json);
  const summary = parseObject(body.summary);
  const checksJson = normalizeChecksJson(body.checks || body.checks_json);
  const checkCountJson = normalizeCheckCounts(body.check_counts || body.check_count_json);
  const checkSeverityJson = normalizeCheckSeverity(body.check_severity || body.check_severity_json);
  const submissionChecks = buildSubmissionChecks(checksJson, checkCountJson, checkSeverityJson);
  const ftiScore = computeFTIScore(submissionChecks);
  const riskLevel = riskLevelFromFTI(ftiScore);
  const source = nonEmptyString(body.source) || 'aira.bageltech.net';
  const targetKind = nonEmptyString(body.target_kind);
  const sourceId = nonEmptyString(body.source_id);
  const sourceKind = inferSourceKind({
    sourceKind: body.source_kind,
    sourceId,
    source,
    targetKind,
    ciRunId: body.ci_run_id,
    ciWorkflow: body.ci_workflow,
  });
  const scannerName = nonEmptyString(body.scanner_name) || 'aira';
  const scannerVersion =
    nonEmptyString(body.scanner_version) ||
    nonEmptyString(meta.scanner_version) ||
    nonEmptyString(env.AIRA_SCANNER_VERSION) ||
    DEFAULT_SCANNER_VERSION;
  const rulesetVersion =
    nonEmptyString(body.ruleset_version) ||
    nonEmptyString(meta.ruleset_version) ||
    nonEmptyString(env.AIRA_RULESET_VERSION) ||
    scannerVersion;
  const scoringVersion = normalizeScoringVersion(body.scoring_version || env.AIRA_SCORING_VERSION);
  const fingerprintSeed = canonicalize({
    checks_json: checksJson,
    ci_ref: body.ci_ref || null,
    ci_run_id: body.ci_run_id || null,
    ci_workflow: body.ci_workflow || null,
    metadata_json: meta,
    source,
    source_id: sourceId,
    source_kind: sourceKind,
    target_kind: targetKind,
  });
  const sampleName = resolveSampleName({
    requestedSampleName: body.sample_name || env.AIRA_SAMPLE_NAME,
    sourceKind,
    sourceId,
    source,
    targetName: body.target_name,
    fallbackSeed: fingerprintSeed,
  });
  const sampleVersion = nonEmptyString(body.sample_version || env.AIRA_SAMPLE_VERSION) || 'v1';

  const record = {
    submitted_at: body.submitted_at || new Date().toISOString(),
    source,
    language: nonEmptyString(body.language) || nonEmptyString(meta.language),
    engine: engineLabel(meta, body),
    scan_mode: nonEmptyString(body.scan_mode) || nonEmptyString(meta.mode) || nonEmptyString(meta.engine),
    provider: nonEmptyString(body.provider) || nonEmptyString(meta.provider) || nonEmptyString(meta.engine),
    model: nonEmptyString(body.model) || nonEmptyString(meta.model),
    target_kind: targetKind,
    files_scanned: normalizeInteger(body.files_scanned ?? summary.files_scanned),
    high_count: normalizeInteger(body.high_count ?? summary.high ?? summary.by_severity?.HIGH),
    medium_count: normalizeInteger(body.medium_count ?? summary.medium ?? summary.by_severity?.MEDIUM),
    low_count: normalizeInteger(body.low_count ?? summary.low ?? summary.by_severity?.LOW),
    total_findings: normalizeInteger(body.total_findings ?? summary.total ?? summary.findings_total),
    checks_failed: submissionChecks.filter(check => check.status === 'FAIL').length,
    checks_passed: submissionChecks.filter(check => check.status === 'PASS').length,
    checks_unknown: submissionChecks.filter(check => check.status === 'UNKNOWN').length,
    checks_json: checksJson,
    check_count_json: checkCountJson,
    check_severity_json: checkSeverityJson,
    ci_workflow: nonEmptyString(body.ci_workflow),
    ci_run_id: nonEmptyString(body.ci_run_id),
    ci_ref: nonEmptyString(body.ci_ref),
    metadata_json: meta,
    sample_name: sampleName,
    sample_version: sampleVersion,
    attribution_class: normalizeAttributionClass(body.attribution_class || env.AIRA_ATTRIBUTION_CLASS),
    source_id: sourceId,
    source_kind: sourceKind,
    scanner_name: scannerName,
    scanner_version: scannerVersion,
    ruleset_version: rulesetVersion,
    scoring_version: scoringVersion,
    fti_score: normalizeDecimal(ftiScore.toFixed(2)),
    risk_level: riskLevel,
    parent_record_sha256: null,
  };

  const submissionFingerprint = sha256Hex(canonicalize(buildFingerprintPayload(record, submissionChecks)));
  return {
    record: {
      ...record,
      submission_fingerprint: submissionFingerprint,
    },
    submissionChecks,
  };
}

export function finalizeSupabaseSubmissionBundle(bundle, parentRecordSha256 = null) {
  const record = {
    ...bundle.record,
    parent_record_sha256: parentRecordSha256 || null,
  };
  return {
    record: {
      ...record,
      record_sha256: sha256Hex(canonicalize(buildPersistedPayload(record, bundle.submissionChecks))),
    },
    submissionChecks: bundle.submissionChecks,
  };
}
