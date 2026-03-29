import { CHECK_IDS } from './airtable.js';

function buildEmptySeverityMatrix() {
  return Object.fromEntries(
    CHECK_IDS.map(checkId => [checkId, { HIGH: 0, MEDIUM: 0, LOW: 0, TOTAL: 0 }])
  );
}

function normalizeCheckCounts(raw = {}) {
  const counts = Object.fromEntries(CHECK_IDS.map(checkId => [checkId, 0]));
  for (const [checkId, value] of Object.entries(raw || {})) {
    counts[checkId] = Number(value || 0);
  }
  return counts;
}

function normalizeCheckSeverity(raw = {}) {
  const matrix = buildEmptySeverityMatrix();
  for (const [checkId, bucket] of Object.entries(raw || {})) {
    const current = matrix[checkId] || { HIGH: 0, MEDIUM: 0, LOW: 0, TOTAL: 0 };
    current.HIGH = Number(bucket?.HIGH || 0);
    current.MEDIUM = Number(bucket?.MEDIUM || 0);
    current.LOW = Number(bucket?.LOW || 0);
    current.TOTAL = Number(bucket?.TOTAL || (current.HIGH + current.MEDIUM + current.LOW));
    matrix[checkId] = current;
  }
  return matrix;
}

function engineLabel(meta = {}) {
  if (meta.engine_label) return meta.engine_label;
  if (meta.provider && meta.model) return `${meta.provider}:${meta.model}`;
  return meta.engine || meta.mode || 'unknown';
}

export function supabaseConfigFromEnv(env = process.env) {
  return {
    url: (env.SUPABASE_URL || '').replace(/\/$/, ''),
    key: env.SUPABASE_SERVICE_ROLE_KEY || env.SUPABASE_KEY || '',
    table: env.SUPABASE_TABLE || 'aira_submissions',
  };
}

export function supabaseConfigSnapshot(env = process.env) {
  const { url, key, table } = supabaseConfigFromEnv(env);
  return {
    configured: Boolean(url && key),
    urlConfigured: Boolean(url),
    keyConfigured: Boolean(key),
    table,
  };
}

function supabaseTableUrl(url, table, query = '') {
  const base = `${url}/rest/v1/${encodeURIComponent(table)}`;
  return query ? `${base}?${query}` : base;
}

export function buildSupabaseResearchRecord(body = {}) {
  const checks = body.checks || {};
  const summary = body.summary || {};
  const meta = body.meta || {};

  return {
    submitted_at: body.submitted_at || new Date().toISOString(),
    source: body.source || 'aira.bageltech.net',
    language: body.language || meta.language || null,
    engine: engineLabel(meta),
    scan_mode: meta.mode || meta.engine || null,
    provider: meta.provider || null,
    model: meta.model || null,
    target_kind: body.target_kind || null,
    files_scanned: Number(summary.files_scanned || 0),
    high_count: Number(summary.high || 0),
    medium_count: Number(summary.medium || 0),
    low_count: Number(summary.low || 0),
    total_findings: Number(summary.total || 0),
    checks_failed: Object.values(checks).filter(value => value === 'FAIL').length,
    checks_passed: Object.values(checks).filter(value => value === 'PASS').length,
    checks_unknown: Object.values(checks).filter(value => value === 'UNKNOWN').length,
    checks_json: checks,
    check_count_json: normalizeCheckCounts(body.check_counts || {}),
    check_severity_json: normalizeCheckSeverity(body.check_severity || {}),
    ci_workflow: body.ci_workflow || null,
    ci_run_id: body.ci_run_id || null,
    ci_ref: body.ci_ref || null,
    metadata_json: meta,
  };
}

async function supabaseRequestJson(method, url, key, payload) {
  const response = await fetch(url, {
    method,
    headers: {
      apikey: key,
      Authorization: `Bearer ${key}`,
      'Content-Type': 'application/json',
      Prefer: 'return=representation',
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.message || data?.error_description || data?.error || `Supabase error ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

export async function submitSupabaseResearchRecord(body = {}, env = process.env) {
  const { url, key, table } = supabaseConfigFromEnv(env);
  if (!url || !key) {
    const error = new Error('Supabase env vars are not configured on the server.');
    error.status = 503;
    throw error;
  }

  const record = buildSupabaseResearchRecord(body);
  const data = await supabaseRequestJson('POST', supabaseTableUrl(url, table), key, [record]);
  const inserted = Array.isArray(data) ? data[0] : data;
  return {
    ok: true,
    backend: 'supabase',
    id: inserted?.id || null,
    record,
  };
}

export async function checkSupabaseConnection(env = process.env) {
  const snapshot = supabaseConfigSnapshot(env);
  if (!snapshot.configured) {
    return {
      ...snapshot,
      ok: false,
      reachable: false,
      message: 'SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not configured on the server.',
    };
  }

  const { url, key, table } = supabaseConfigFromEnv(env);
  try {
    await supabaseRequestJson(
      'GET',
      supabaseTableUrl(url, table, new URLSearchParams({ select: 'id', limit: '1' }).toString()),
      key,
      null
    );
    return {
      ...snapshot,
      ok: true,
      reachable: true,
      message: 'Supabase connection verified.',
    };
  } catch (error) {
    return {
      ...snapshot,
      ok: false,
      reachable: false,
      message: error.message,
      status: error.status || 500,
    };
  }
}
