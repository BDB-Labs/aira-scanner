import { submitResearchRecord } from '../lib/airtable.js';

export const config = {
  api: {
    bodyParser: true,
  },
};

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: { message: 'Method not allowed' } });
  }

  try {
    const result = await submitResearchRecord(req.body || {}, process.env);
    return res.status(200).json(result);
  } catch (err) {
    return res.status(err.status || 500).json({ error: { message: err.message || 'Proxy error' } });
  }
}
