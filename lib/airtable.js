const OPTIONAL_FIELD_ORDER = [
  'Language',
  'Check Count JSON',
  'Check Severity JSON',
  'Checks Passed',
  'Checks Unknown',
  'Files Scanned',
  'Scan Mode',
  'Provider',
  'Model',
  'Target Kind',
  'CI Workflow',
  'CI Run ID',
  'CI Ref',
];

const CHECK_IDS = Array.from({ length: 15 }, (_, index) => `C${String(index + 1).padStart(2, '0')}`);

function buildEmptySeverityMatrix() {
  return Object.fromEntries(
    CHECK_IDS.map(checkId => [checkId, { HIGH: 0, MEDIUM: 0, LOW: 0, TOTAL: 0 }])
  );
}

export function airtableConfigFromEnv(env = process.env) {
  return {
    baseId: env.AIRTABLE_BASE_ID || '',
    table: env.AIRTABLE_TABLE || 'Submissions',
    token: env.AIRTABLE_TOKEN || '',
  };
}

export function airtableConfigSnapshot(env = process.env) {
  const { baseId, table, token } = airtableConfigFromEnv(env);
  return {
    configured: Boolean(baseId && token),
    baseIdConfigured: Boolean(baseId),
    table,
    tokenConfigured: Boolean(token),
  };
}

function airtableUrl(baseId, table, query = '') {
  const url = `https://api.airtable.com/v0/${encodeURIComponent(baseId)}/${encodeURIComponent(table)}`;
  return query ? `${url}?${query}` : url;
}

function engineLabel(meta = {}) {
  if (meta.engine_label) return meta.engine_label;
  if (meta.provider && meta.model) return `${meta.provider}:${meta.model}`;
  return meta.engine || meta.mode || 'unknown';
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

export function buildResearchFields(body = {}) {
  const checks = body.checks || {};
  const summary = body.summary || {};
  const meta = body.meta || {};
  const checkCounts = normalizeCheckCounts(body.check_counts || {});
  const checkSeverity = normalizeCheckSeverity(body.check_severity || {});

  const baselineFields = {
    'Submitted At': body.submitted_at || new Date().toISOString(),
    'Checks JSON': JSON.stringify(checks),
    'High Count': Number(summary.high || 0),
    'Medium Count': Number(summary.medium || 0),
    'Low Count': Number(summary.low || 0),
    'Total Findings': Number(summary.total || 0),
    'Checks Failed': Object.values(checks).filter(value => value === 'FAIL').length,
    'Engine': engineLabel(meta),
    'Source': body.source || 'aira.bageltech.net',
  };

  const optionalFields = {
    'Language': body.language || meta.language || '',
    'Check Count JSON': JSON.stringify(checkCounts),
    'Check Severity JSON': JSON.stringify(checkSeverity),
    'Checks Passed': Object.values(checks).filter(value => value === 'PASS').length,
    'Checks Unknown': Object.values(checks).filter(value => value === 'UNKNOWN').length,
    'Files Scanned': Number(summary.files_scanned || 0),
    'Scan Mode': meta.mode || meta.engine || '',
    'Provider': meta.provider || meta.engine || '',
    'Model': meta.model || '',
    'Target Kind': body.target_kind || '',
    'CI Workflow': body.ci_workflow || '',
    'CI Run ID': body.ci_run_id || '',
    'CI Ref': body.ci_ref || '',
  };

  return { baselineFields, optionalFields };
}

async function airtableRequestJson(method, url, token, payload) {
  const response = await fetch(url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: payload ? JSON.stringify(payload) : undefined,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data?.error?.message || data?.error?.type || `Airtable error ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function extractUnknownField(message = '') {
  const match = message.match(/Unknown field name:\s*"?(.*?)"?$/);
  return match ? match[1] : null;
}

export async function submitResearchRecord(body = {}, env = process.env) {
  const { baseId, table, token } = airtableConfigFromEnv(env);
  if (!baseId || !token) {
    const error = new Error('Airtable env vars are not configured on the server.');
    error.status = 503;
    throw error;
  }

  const { baselineFields, optionalFields } = buildResearchFields(body);
  const droppedOptionalFields = [];
  const url = airtableUrl(baseId, table);

  while (true) {
    const fields = { ...baselineFields, ...optionalFields };
    try {
      const data = await airtableRequestJson('POST', url, token, { fields });
      return { ok: true, id: data?.id || null, droppedOptionalFields, submittedFields: Object.keys(fields).sort() };
    } catch (error) {
      const unknownField = error.status === 422 ? extractUnknownField(error.message) : null;
      if (!unknownField) {
        throw error;
      }
      if (!(unknownField in optionalFields)) {
        throw error;
      }
      delete optionalFields[unknownField];
      droppedOptionalFields.push(unknownField);
    }
  }
}

export async function checkAirtableConnection(env = process.env) {
  const snapshot = airtableConfigSnapshot(env);
  if (!snapshot.configured) {
    return {
      ...snapshot,
      ok: false,
      reachable: false,
      message: 'AIRTABLE_BASE_ID and AIRTABLE_TOKEN are not configured on the server.',
    };
  }

  const { baseId, table, token } = airtableConfigFromEnv(env);
  try {
    await airtableRequestJson(
      'GET',
      airtableUrl(baseId, table, new URLSearchParams({ maxRecords: '1' }).toString()),
      token,
      null
    );
    return {
      ...snapshot,
      ok: true,
      reachable: true,
      message: 'Airtable connection verified.',
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

export { CHECK_IDS, OPTIONAL_FIELD_ORDER };
