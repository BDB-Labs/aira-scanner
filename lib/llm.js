const AUTO_PROVIDER_ORDER = ['groq', 'gemini', 'openrouter'];
const MAX_ATTEMPTS_PER_PROVIDER = 2;

function configuredProviders() {
  return AUTO_PROVIDER_ORDER.filter(provider => {
    if (provider === 'groq') return Boolean(process.env.GROQ_API_KEY);
    if (provider === 'openrouter') return Boolean(process.env.OPENROUTER_API_KEY && process.env.OPENROUTER_MODEL);
    if (provider === 'gemini') return Boolean(process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY);
    return false;
  });
}

function buildMessages(system, prompt) {
  return [
    system ? { role: 'system', content: system } : null,
    { role: 'user', content: prompt }
  ].filter(Boolean);
}

function parseOpenAiCompatibleText(data) {
  const content = data?.choices?.[0]?.message?.content;
  if (typeof content === 'string') return content.trim();
  if (Array.isArray(content)) {
    return content
      .map(part => typeof part?.text === 'string' ? part.text : '')
      .join('')
      .trim();
  }
  return '';
}

function ensureValidJson(text) {
  JSON.parse(text);
  return text;
}

async function parseJsonResponse(response, providerName) {
  const data = await response.json();
  if (!response.ok) {
    const message =
      data?.error?.message ||
      data?.error?.metadata?.raw ||
      `${providerName} API error ${response.status}`;
    throw new Error(message);
  }
  return data;
}

async function callGroq({ system, prompt }) {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error('GROQ_API_KEY is not configured.');
  }

  const model = process.env.GROQ_MODEL || 'llama-3.1-8b-instant';
  const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      temperature: 0,
      response_format: { type: 'json_object' },
      messages: buildMessages(system, prompt)
    })
  });

  const data = await parseJsonResponse(response, 'Groq');
  return {
    provider: 'groq',
    model,
    text: ensureValidJson(parseOpenAiCompatibleText(data))
  };
}

async function callOpenRouter({ system, prompt }) {
  const apiKey = process.env.OPENROUTER_API_KEY;
  const model = process.env.OPENROUTER_MODEL;
  if (!apiKey || !model) {
    throw new Error('OPENROUTER_API_KEY and OPENROUTER_MODEL must both be configured.');
  }

  const response = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model,
      temperature: 0,
      response_format: { type: 'json_object' },
      messages: buildMessages(system, prompt)
    })
  });

  const data = await parseJsonResponse(response, 'OpenRouter');
  return {
    provider: 'openrouter',
    model,
    text: ensureValidJson(parseOpenAiCompatibleText(data))
  };
}

async function callGemini({ system, prompt }) {
  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    throw new Error('GEMINI_API_KEY or GOOGLE_API_KEY is not configured.');
  }

  const model = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
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
          temperature: 0,
          responseMimeType: 'application/json'
        }
      })
    }
  );

  const data = await parseJsonResponse(response, 'Gemini');
  const text = (data?.candidates || [])
    .flatMap(candidate => candidate?.content?.parts || [])
    .map(part => part?.text || '')
    .join('')
    .trim();

  if (!text) {
    throw new Error('Gemini returned an empty response.');
  }

  return {
    provider: 'gemini',
    model,
    text: ensureValidJson(text)
  };
}

const PROVIDERS = {
  groq: callGroq,
  openrouter: callOpenRouter,
  gemini: callGemini
};

export async function runLLM({ system = '', prompt = '', provider = 'auto' }) {
  if (!prompt.trim()) {
    throw new Error('No scan prompt provided.');
  }

  const providerOrder = provider === 'auto'
    ? configuredProviders()
    : [provider];

  if (providerOrder.length === 0) {
    throw new Error(
      'No cloud providers are configured. Set GROQ_API_KEY, OPENROUTER_API_KEY + OPENROUTER_MODEL, or GEMINI_API_KEY.'
    );
  }

  const errors = [];
  for (const providerName of providerOrder) {
    const runner = PROVIDERS[providerName];
    if (!runner) {
      errors.push(`${providerName}: unsupported provider`);
      continue;
    }

    for (let attempt = 1; attempt <= MAX_ATTEMPTS_PER_PROVIDER; attempt += 1) {
      try {
        return await runner({ system, prompt });
      } catch (err) {
        errors.push(`${providerName} attempt ${attempt}: ${err.message}`);
      }
    }
  }

  throw new Error(`All configured providers failed. ${errors.join(' | ')}`);
}
