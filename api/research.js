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

  const baseId = process.env.AIRTABLE_BASE_ID;
  const table = process.env.AIRTABLE_TABLE || 'Submissions';
  const token = process.env.AIRTABLE_TOKEN;

  if (!baseId || !token) {
    return res.status(503).json({
      error: { message: 'Airtable env vars are not configured on the server.' }
    });
  }

  const body = req.body || {};
  const checks = body.checks || {};
  const summary = body.summary || {};
  const meta = body.meta || {};

  const payload = {
    fields: {
      'Submitted At': body.submitted_at || new Date().toISOString(),
      'Checks JSON': JSON.stringify(checks),
      'High Count': Number(summary.high || 0),
      'Medium Count': Number(summary.medium || 0),
      'Low Count': Number(summary.low || 0),
      'Total Findings': Number(summary.total || 0),
      'Checks Failed': Object.values(checks).filter(value => value === 'FAIL').length,
      'Engine': meta.engine_label || meta.engine || 'unknown',
      'Source': body.source || 'aira.bageltech.net'
    }
  };

  try {
    const response = await fetch(
      `https://api.airtable.com/v0/${encodeURIComponent(baseId)}/${encodeURIComponent(table)}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      }
    );

    const data = await response.json();
    if (!response.ok) {
      return res.status(response.status).json({
        error: { message: data?.error?.message || `Airtable error ${response.status}` }
      });
    }

    return res.status(200).json({ ok: true, id: data?.id || null });
  } catch (err) {
    return res.status(500).json({ error: { message: `Proxy error: ${err.message}` } });
  }
}
