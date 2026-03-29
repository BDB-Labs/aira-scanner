import { checkAirtableConnection, submitResearchRecord as submitAirtableResearchRecord } from './airtable.js';
import { checkSupabaseConnection, submitSupabaseResearchRecord } from './supabase.js';

function requestedBackend(env = process.env) {
  return (env.RESEARCH_BACKEND || env.AIRA_RESEARCH_BACKEND || '').trim().toLowerCase();
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
  return { backend };
}

export async function submitResearchRecord(body = {}, env = process.env) {
  const backend = detectResearchBackend(env);
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
    };
  }
  const error = new Error(
    'No research backend is configured. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY or AIRTABLE_BASE_ID + AIRTABLE_TOKEN.'
  );
  error.status = 503;
  throw error;
}

export async function checkResearchConnection(env = process.env) {
  const backend = detectResearchBackend(env);
  if (backend === 'jsonl') {
    return {
      backend: 'jsonl',
      configured: true,
      ok: false,
      reachable: false,
      message: 'The jsonl research backend is only supported by the CLI/local collector, not the hosted web API.',
      status: 400,
    };
  }
  if (backend === 'supabase') {
    const snapshot = await checkSupabaseConnection(env);
    return { backend, ...snapshot };
  }
  if (backend === 'airtable') {
    const snapshot = await checkAirtableConnection(env);
    return { backend, ...snapshot };
  }
  return {
    backend: 'none',
    configured: false,
    ok: false,
    reachable: false,
    message: 'No research backend is configured.',
  };
}
