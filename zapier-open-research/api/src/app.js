import { randomUUID, timingSafeEqual } from 'node:crypto';
import express from 'express';
import { listWorks } from './openalex.js';

function secureEqual(actual, expected) {
  const left = Buffer.from(actual || '');
  const right = Buffer.from(expected || '');
  return left.length === right.length && timingSafeEqual(left, right);
}

function apiError(res, status, code, message) {
  return res.status(status).json({ error: { code, message } });
}

function normalizeDoi(value) {
  if (!value) return null;
  const bare = String(value).trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, '');
  return bare ? `https://doi.org/${bare}` : null;
}

function savedWorkOutput(work) {
  return {
    ...work,
    article_url: work.open_access_url || work.doi || `https://openalex.org/${work.openalex_id}`,
  };
}

function allowedHookTarget(targetUrl, allowlist) {
  try {
    const url = new URL(targetUrl);
    return url.protocol === 'https:' && allowlist.includes(url.hostname);
  } catch {
    return false;
  }
}

async function sendWebhook(fetchImpl, subscription, payload) {
  const response = await fetchImpl(subscription.target_url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(8_000),
  });
  if (!response.ok) throw new Error(`Webhook delivery failed with ${response.status}`);
}

export function createApp({
  pool,
  apiKey = process.env.API_KEY,
  fetchImpl = fetch,
  hookAllowlist = (process.env.HOOK_TARGET_ALLOWLIST || 'hooks.zapier.com').split(','),
} = {}) {
  if (!pool) throw new Error('pool is required');
  if (!apiKey) throw new Error('API_KEY is required');

  const app = express();
  app.disable('x-powered-by');
  app.use(express.json({ limit: '64kb' }));

  app.get('/', (_req, res) => {
    res.type('html').send(
      '<main><h1>Open Research Watch</h1><p>Synthetic portfolio environment. Publication metadata comes from OpenAlex CC0; saved works and scores are demo data.</p></main>',
    );
  });
  app.get('/health', (_req, res) => res.json({ ok: true }));

  app.use('/v1', (req, res, next) => {
    if (!secureEqual(req.get('x-api-key'), apiKey)) {
      return apiError(res, 401, 'invalid_api_key', 'The API key is invalid.');
    }
    next();
  });

  app.get('/v1/me', (_req, res) => {
    res.json({ id: 'demo', name: 'Open Research Watch Demo' });
  });

  app.get('/v1/works', async (req, res, next) => {
    try {
      const perPage = Number(req.query.per_page || 25);
      if (!Number.isInteger(perPage) || perPage < 1 || perPage > 100) {
        return apiError(res, 422, 'invalid_per_page', 'per_page must be an integer between 1 and 100.');
      }
      const items = await listWorks({
        query: typeof req.query.query === 'string' ? req.query.query : '',
        perPage,
        fetchImpl,
      });
      res.json({ items, page: 1, has_more: items.length === 100 });
    } catch (error) {
      if (error.status === 429) {
        return res
          .status(429)
          .set('retry-after', error.retryAfter || '60')
          .json({ error: { code: 'upstream_throttled', message: error.message } });
      }
      next(error);
    }
  });

  app.post('/v1/webhook-subscriptions', async (req, res, next) => {
    const { target_url: targetUrl, event } = req.body || {};
    if (!allowedHookTarget(targetUrl, hookAllowlist)) {
      return apiError(res, 422, 'invalid_target_url', 'target_url must use HTTPS and an allowed hostname.');
    }
    if (event !== 'saved_work.changed') {
      return apiError(res, 422, 'invalid_event', 'event must be saved_work.changed.');
    }
    try {
      const id = randomUUID();
      const result = await pool.query(
        'INSERT INTO webhook_subscriptions (id, target_url, event) VALUES ($1, $2, $3) RETURNING id, target_url, event, created_at',
        [id, targetUrl, event],
      );
      res.status(201).json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.delete('/v1/webhook-subscriptions/:id', async (req, res, next) => {
    try {
      await pool.query('DELETE FROM webhook_subscriptions WHERE id = $1', [req.params.id]);
      res.status(204).end();
    } catch (error) {
      next(error);
    }
  });

  app.get('/v1/saved-works', async (req, res, next) => {
    try {
      const values = [];
      let where = '';
      if (typeof req.query.doi === 'string' && req.query.doi.trim()) {
        values.push(normalizeDoi(req.query.doi).toLowerCase());
        where = 'WHERE LOWER(doi) = $1';
      }
      const result = await pool.query(
        `SELECT * FROM saved_works ${where} ORDER BY updated_at DESC LIMIT 100`,
        values,
      );
      res.json({ items: result.rows.map(savedWorkOutput) });
    } catch (error) {
      next(error);
    }
  });

  app.put('/v1/saved-works/:openalexId', async (req, res, next) => {
    const openalexId = String(req.params.openalexId || '').trim();
    const title = String(req.body?.title || '').trim();
    if (!/^W\d+$/.test(openalexId)) {
      return apiError(res, 422, 'invalid_openalex_id', 'openalex_id must look like W123456789.');
    }
    if (!title) return apiError(res, 422, 'required_field', 'title is required.');
    const score = req.body?.score === undefined || req.body?.score === null || req.body?.score === ''
      ? null
      : Number(req.body.score);
    if (score !== null && (!Number.isInteger(score) || score < 0 || score > 100)) {
      return apiError(res, 422, 'invalid_score', 'score must be an integer between 0 and 100.');
    }

    try {
      const result = await pool.query(
        `INSERT INTO saved_works
          (openalex_id, title, doi, publication_date, primary_source, open_access_url, score, score_explanation, note)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
         ON CONFLICT (openalex_id) DO UPDATE SET
          title = EXCLUDED.title,
          doi = EXCLUDED.doi,
          publication_date = EXCLUDED.publication_date,
          primary_source = EXCLUDED.primary_source,
          open_access_url = EXCLUDED.open_access_url,
          score = EXCLUDED.score,
          score_explanation = EXCLUDED.score_explanation,
          note = EXCLUDED.note,
          updated_at = NOW()
         RETURNING *`,
        [
          openalexId,
          title,
          normalizeDoi(req.body.doi),
          req.body.publication_date || null,
          req.body.primary_source || null,
          req.body.open_access_url || null,
          score,
          req.body.score_explanation || null,
          req.body.note || null,
        ],
      );
      const work = savedWorkOutput(result.rows[0]);
      const event = {
        id: `saved-work:${randomUUID()}`,
        event: 'saved_work.changed',
        occurred_at: new Date(work.updated_at).toISOString(),
        work,
      };
      const subscriptions = await pool.query(
        'SELECT target_url FROM webhook_subscriptions WHERE event = $1',
        ['saved_work.changed'],
      );
      const deliveries = await Promise.allSettled(
        subscriptions.rows.map((subscription) => sendWebhook(fetchImpl, subscription, event)),
      );
      res.json({ ...work, webhook_deliveries: deliveries.length });
    } catch (error) {
      if (error.code === '23505') {
        return apiError(res, 409, 'doi_already_saved', 'doi is already attached to another saved work.');
      }
      next(error);
    }
  });

  app.post('/v1/reviews', async (req, res, next) => {
    const idempotencyKey = req.get('idempotency-key');
    const openalexId = String(req.body?.openalex_id || '').trim();
    const sourceEventId = String(req.body?.source_event_id || '').trim();
    const score = Number(req.body?.score);
    if (!idempotencyKey) return apiError(res, 422, 'required_field', 'Idempotency-Key is required.');
    if (!/^W\d+$/.test(openalexId)) {
      return apiError(res, 422, 'invalid_openalex_id', 'openalex_id must look like W123456789.');
    }
    if (!sourceEventId) return apiError(res, 422, 'required_field', 'source_event_id is required.');
    if (!Number.isInteger(score) || score < -100 || score > 100) {
      return apiError(res, 422, 'invalid_score', 'score must be an integer between -100 and 100.');
    }

    try {
      const id = randomUUID();
      const inserted = await pool.query(
        `INSERT INTO review_ledger (id, idempotency_key, openalex_id, score, source_event_id)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (idempotency_key) DO NOTHING
         RETURNING *`,
        [id, idempotencyKey, openalexId, score, sourceEventId],
      );
      const row = inserted.rows[0] || (
        await pool.query('SELECT * FROM review_ledger WHERE idempotency_key = $1', [idempotencyKey])
      ).rows[0];
      const total = await pool.query(
        'SELECT COALESCE(SUM(score), 0)::integer AS total_score FROM review_ledger WHERE openalex_id = $1',
        [openalexId],
      );
      const wasInserted = row.id === id;
      res.status(wasInserted ? 201 : 200).json({
        ...row,
        replayed: !wasInserted,
        total_score: total.rows[0].total_score,
      });
    } catch (error) {
      if (error.code === '23503') {
        return apiError(res, 422, 'unknown_work', 'openalex_id must reference a saved work.');
      }
      next(error);
    }
  });

  app.use((error, _req, res, _next) => {
    console.error(error);
    apiError(res, 500, 'internal_error', 'The service could not complete the request.');
  });

  return app;
}
