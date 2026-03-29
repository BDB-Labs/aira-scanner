import { checkAirtableConnection, submitResearchRecord as submitAirtableResearchRecord } from './airtable.js';
import { checkSupabaseConnection, submitSupabaseResearchRecord } from './supabase.js';

export const DEFAULT_WEB_RESEARCH_BACKEND = 'supabase';
export const WEB_RESEARCH_BACKEND_ORDER = ['supabase', 'airtable'];
const VALID_RESEARCH_BACKENDS = new Set(['supabase', 'airtable', 'jsonl', 'none']);

function requestedBackend(env = process.env) {
  return (env.RESEARCH_BACKEND || env.AIRA_RESEARCH_BACKEND || '').trim().toLowerCase();
}

function snapshotFor(backend) {
  return {
    backend,
    preferredBackend: DEFAULT_WEB_RESEARCH_BACKEND,
    backendOrder: WEB_RESEARCH_BACKEND_ORDER,
    legacyFallbackBackend: 'airtable',
  };
}

function isValidBackend(backend) {
  return VALID_RESEARCH_BACKENDS.has(backend);
}

export function detectResearchBackend(env = process.env) {
  const requested = requestedBackend(env);
  if (requested) return requested;
  if (env.SUPABASE_URL && (env.SUPABASE_SERVICE_ROLE_KEY || env.SUPABASE_KEY)) return 'supabase';
  if (env.AIRTABLE_BASE_ID && env.AIRTABLE_TOKEN) return 'airtable';
  return 'none';
}

export function researchBackendSnapshot(env = process.env) {
  const backend = detectResearchBackend(env);
  return snapshotFor(backend);
}

export async function submitResearchRecord(body = {}, env = process.env) {
  const backend = detectResearchBackend(env);
  if (!isValidBackend(backend)) {
    const error = new Error(`Unknown research backend '${backend}'. Use one of: supabase, airtable.`);
    error.status = 400;
    throw error;
  }
  if (backend === 'jsonl') {
    const error = new Error('The jsonl research backend is only supported by the CLI/local collector, not the hosted web API.');
    error.status = 400;
    throw error;
  }
  if (backend === 'supabase') {
    return submitSupabaseResearchRecord(body, env);
  }
  if (backend === 'airtable') {
    const result = await submitAirtableResearchRecord(body, env);
    return {
      ...result,
      backend: 'airtable',
      legacyFallback: true,
    };
  }
  const error = new Error(
    'No research backend is configured. Supabase is the preferred hosted backend. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY. Airtable remains available only as a legacy fallback.'
  );
  error.status = 503;
  throw error;
}

export async function checkResearchConnection(env = process.env) {
  const backend = detectResearchBackend(env);
  if (!isValidBackend(backend)) {
    return {
      ...snapshotFor(backend),
      configured: false,
      ok: false,
      reachable: false,
      invalidBackend: true,
      message: `Unknown research backend '${backend}'. Use one of: supabase, airtable.`,
      status: 400,
    };
  }
  if (backend === 'jsonl') {
    return {
      ...snapshotFor('jsonl'),
      configured: true,
      ok: false,
      reachable: false,
      message: 'The jsonl research backend is only supported by the CLI/local collector, not the hosted web API.',
      status: 400,
    };
  }
  if (backend === 'supabase') {
    const snapshot = await checkSupabaseConnection(env);
    return { ...snapshotFor(backend), ...snapshot };
  }
  if (backend === 'airtable') {
    const snapshot = await checkAirtableConnection(env);
    return {
      ...snapshotFor(backend),
      ...snapshot,
      legacyFallback: true,
      message: snapshot.ok
        ? 'Airtable connection verified. This backend is supported only as a legacy compatibility fallback.'
        : snapshot.message,
    };
  }
  return {
    ...snapshotFor('none'),
    configured: false,
    ok: false,
    reachable: false,
    message: 'No research backend is configured. Supabase is the preferred hosted backend.',
  };
}
