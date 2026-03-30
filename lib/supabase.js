import { buildSupabaseSubmissionBundle, finalizeSupabaseSubmissionBundle } from './research-schema-v2.js';

export function supabaseConfigFromEnv(env = process.env) {
  return {
    url: (env.SUPABASE_URL || '').replace(/\/$/, ''),
    key: env.SUPABASE_SERVICE_ROLE_KEY || env.SUPABASE_KEY || '',
    table: env.SUPABASE_TABLE || 'aira_submissions',
    checksTable: env.SUPABASE_CHECKS_TABLE || 'aira_submission_checks',
  };
}

export function supabaseConfigSnapshot(env = process.env) {
  const { url, key, table, checksTable } = supabaseConfigFromEnv(env);
  return {
    configured: Boolean(url && key),
    urlConfigured: Boolean(url),
    keyConfigured: Boolean(key),
    table,
    checksTable,
  };
}

function supabaseTableUrl(url, table, query = '') {
  const base = `${url}/rest/v1/${encodeURIComponent(table)}`;
  return query ? `${base}?${query}` : base;
}

export function buildSupabaseResearchRecord(body = {}, env = process.env) {
  return finalizeSupabaseSubmissionBundle(buildSupabaseSubmissionBundle(body, env)).record;
}

async function supabaseRequestJson(method, url, key, payload, options = {}) {
  const headers = {
    apikey: key,
    Authorization: `Bearer ${key}`,
    'Content-Type': 'application/json',
    Prefer: options.prefer || 'return=representation',
    ...(options.headers || {}),
  };
  const response = await fetch(url, {
    method,
    headers,
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

async function fetchSubmissionByFingerprint(config, fingerprint) {
  const query = new URLSearchParams({
    select: '*',
    submission_fingerprint: `eq.${fingerprint}`,
    limit: '1',
  }).toString();
  const data = await supabaseRequestJson('GET', supabaseTableUrl(config.url, config.table, query), config.key, null);
  return Array.isArray(data) ? data[0] || null : data || null;
}

async function fetchLatestParentRecord(config, sampleName, sampleVersion) {
  const query = new URLSearchParams({
    select: 'id,record_sha256',
    sample_name: `eq.${sampleName}`,
    sample_version: `eq.${sampleVersion}`,
    order: 'submitted_at.desc,created_at.desc',
    limit: '1',
  }).toString();
  const data = await supabaseRequestJson('GET', supabaseTableUrl(config.url, config.table, query), config.key, null);
  return Array.isArray(data) ? data[0] || null : data || null;
}

async function insertSubmissionChecks(config, submissionId, submissionChecks) {
  if (!submissionId || !submissionChecks.length) return [];
  const payload = submissionChecks.map(check => ({
    submission_id: submissionId,
    check_id: check.check_id,
    check_name: check.check_name,
    status: check.status,
    weight: check.weight,
    finding_count: check.finding_count,
    high_count: check.high_count,
    medium_count: check.medium_count,
    low_count: check.low_count,
  }));
  const query = new URLSearchParams({ on_conflict: 'submission_id,check_id' }).toString();
  return supabaseRequestJson(
    'POST',
    supabaseTableUrl(config.url, config.checksTable, query),
    config.key,
    payload,
    { prefer: 'resolution=ignore-duplicates,return=representation' }
  );
}

export async function submitSupabaseResearchRecord(body = {}, env = process.env) {
  const config = supabaseConfigFromEnv(env);
  if (!config.url || !config.key) {
    const error = new Error('Supabase env vars are not configured on the server.');
    error.status = 503;
    throw error;
  }

  const bundle = buildSupabaseSubmissionBundle(body, env);
  const existing = await fetchSubmissionByFingerprint(config, bundle.record.submission_fingerprint);
  if (existing?.id) {
    await insertSubmissionChecks(config, existing.id, bundle.submissionChecks);
    return {
      ok: true,
      backend: 'supabase',
      id: existing.id,
      duplicate: true,
      record: existing,
    };
  }

  const parent = await fetchLatestParentRecord(config, bundle.record.sample_name, bundle.record.sample_version);
  const finalized = finalizeSupabaseSubmissionBundle(bundle, parent?.record_sha256 || null);
  const query = new URLSearchParams({ on_conflict: 'submission_fingerprint' }).toString();
  const data = await supabaseRequestJson(
    'POST',
    supabaseTableUrl(config.url, config.table, query),
    config.key,
    [finalized.record],
    { prefer: 'resolution=ignore-duplicates,return=representation' }
  );
  let inserted = Array.isArray(data) ? data[0] : data;
  if (!inserted?.id) {
    inserted = await fetchSubmissionByFingerprint(config, finalized.record.submission_fingerprint);
  }
  if (!inserted?.id) {
    const error = new Error('Supabase submission did not return a persisted record.');
    error.status = 500;
    throw error;
  }
  await insertSubmissionChecks(config, inserted.id, finalized.submissionChecks);
  return {
    ok: true,
    backend: 'supabase',
    id: inserted?.id || null,
    duplicate: false,
    record: inserted,
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
