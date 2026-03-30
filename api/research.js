import { publicResearchSubmissionEnabled, submitResearchRecord } from '../lib/research-store.js';

export const config = {
  api: {
    bodyParser: true,
  },
};

export default async function handler(req, res) {
  const publicSubmissionEnabled = publicResearchSubmissionEnabled(process.env);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: { message: 'Method not allowed' } });
  }

  if (!publicSubmissionEnabled) {
    return res.status(403).json({
      error: {
        message:
          'Public research submission is disabled. Canonical research records are reserved for internal curated CLI/CI workflows.',
      },
      publicSubmissionEnabled: false,
    });
  }

  try {
    const result = await submitResearchRecord(req.body || {}, process.env);
    return res.status(200).json(result);
  } catch (err) {
    return res.status(err.status || 500).json({ error: { message: err.message || 'Proxy error' } });
  }
}
