export const config = {
  api: {
    bodyParser: true,
  },
};

import { runLLM } from '../lib/llm.js';

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

  const system = typeof req.body?.system === 'string' ? req.body.system.trim() : '';
  const prompt = buildPrompt(req.body);
  const provider = typeof req.body?.provider === 'string' ? req.body.provider : 'auto';

  if (!prompt) {
    return res.status(400).json({ error: { message: 'No scan prompt provided.' } });
  }

  try {
    const result = await runLLM({ system, prompt, provider });

    return res.status(200).json({
      text: result.text,
      provider: result.provider,
      model: result.model
    });
  } catch (err) {
    return res.status(500).json({ error: { message: `Routing error: ${err.message}` } });
  }
}
