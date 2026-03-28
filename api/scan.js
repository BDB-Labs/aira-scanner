export const config = {
  api: {
    bodyParser: true,
  },
};

/*
Legacy Anthropic proxy reference, intentionally kept commented out while AIRA
uses Gemini on the free tier:

const anthropicApiKey = process.env.ANTHROPIC_API_KEY;
const anthropicResponse = await fetch('https://api.anthropic.com/v1/messages', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': anthropicApiKey,
    'anthropic-version': '2023-06-01'
  },
  body: JSON.stringify(req.body)
});
*/

function buildPrompt(body) {
  if (typeof body?.prompt === 'string' && body.prompt.trim()) {
    return body.prompt.trim();
  }

  const firstMessage = Array.isArray(body?.messages) ? body.messages[0] : null;
  if (typeof firstMessage?.content === 'string' && firstMessage.content.trim()) {
    return firstMessage.content.trim();
  }

  return '';
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    return res.status(503).json({
      error: { message: 'Gemini API key not configured on server.' }
    });
  }

  const model = req.body?.model || process.env.GEMINI_MODEL || 'gemini-2.5-flash';
  const system = typeof req.body?.system === 'string' ? req.body.system.trim() : '';
  const prompt = buildPrompt(req.body);

  if (!prompt) {
    return res.status(400).json({ error: { message: 'No scan prompt provided.' } });
  }

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`,
      {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        systemInstruction: system ? { parts: [{ text: system }] } : undefined,
        contents: [
          {
            role: 'user',
            parts: [{ text: prompt }]
          }
        ],
        generationConfig: {
          temperature: 0.1,
          responseMimeType: 'application/json'
        }
      })
    });

    const data = await response.json();
    if (!response.ok) {
      const message =
        data?.error?.message ||
        data?.error?.status ||
        `Gemini API error ${response.status}`;
      return res.status(response.status).json({ error: { message } });
    }

    const text = (data?.candidates || [])
      .flatMap(candidate => candidate?.content?.parts || [])
      .map(part => part?.text || '')
      .join('')
      .trim();

    if (!text) {
      return res.status(502).json({ error: { message: 'Gemini returned an empty response.' } });
    }

    return res.status(200).json({
      text,
      model
    });
  } catch (err) {
    return res.status(500).json({ error: { message: `Proxy error: ${err.message}` } });
  }
}
