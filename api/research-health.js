import { checkResearchConnection } from '../lib/research-store.js';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: { message: 'Method not allowed' } });
  }

  const snapshot = await checkResearchConnection(process.env);
  return res.status(snapshot.ok ? 200 : (snapshot.status || 503)).json({
    ...snapshot,
    route: '/api/research-health',
    preferredBackend: snapshot.preferredBackend || 'supabase',
  });
}
