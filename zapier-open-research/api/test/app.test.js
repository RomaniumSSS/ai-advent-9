import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { newDb } from 'pg-mem';
import request from 'supertest';
import { createApp } from '../src/app.js';

const here = dirname(fileURLToPath(import.meta.url));
const migration = await readFile(join(here, '..', 'migrations', '001_initial.sql'), 'utf8');

async function fixture() {
  const memory = newDb();
  const adapter = memory.adapters.createPg();
  const pool = new adapter.Pool();
  await pool.query(migration);
  const deliveries = [];
  const fetchImpl = async (url, options = {}) => {
    const target = String(url);
    if (target.startsWith('https://api.openalex.org/works')) {
      return new Response(JSON.stringify({
        results: [{
          id: 'https://openalex.org/W123',
          display_name: 'A real open work',
          doi: 'https://doi.org/10.1000/test',
          publication_date: '2026-09-12',
          primary_location: { source: { display_name: 'Test Journal' } },
          open_access: { oa_url: 'https://example.org/work' },
          cited_by_count: 4,
        }],
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    }
    deliveries.push({ target, body: JSON.parse(options.body) });
    return new Response('{}', { status: 200 });
  };
  const app = createApp({
    pool,
    apiKey: 'test-key',
    fetchImpl,
    hookAllowlist: ['hooks.example.test'],
  });
  return { app, pool, deliveries };
}

const auth = { 'x-api-key': 'test-key' };

test('публичная страница явно помечена как synthetic demo', async () => {
  const { app, pool } = await fixture();
  const response = await request(app).get('/');
  assert.equal(response.status, 200);
  assert.match(response.text, /Synthetic portfolio environment/);
  await pool.end();
});

test('API key защищает приватные маршруты понятной ошибкой', async () => {
  const { app, pool } = await fixture();
  const denied = await request(app).get('/v1/me').set('x-api-key', 'wrong');
  assert.equal(denied.status, 401);
  assert.equal(denied.body.error.code, 'invalid_api_key');
  const accepted = await request(app).get('/v1/me').set(auth);
  assert.equal(accepted.body.name, 'Open Research Watch Demo');
  await pool.end();
});

test('OpenAlex records сохраняют стабильный id между опросами', async () => {
  const { app, pool } = await fixture();
  const first = await request(app).get('/v1/works?query=real%20open').set(auth);
  const second = await request(app).get('/v1/works?query=real%20open').set(auth);
  assert.equal(first.body.items[0].id, 'W123');
  assert.equal(second.body.items[0].id, first.body.items[0].id);
  assert.equal(first.body.items[0].score_breakdown.relevance, 40);
  assert.equal(first.body.items[0].article_url, 'https://example.org/work');
  await pool.end();
});

test('subscribe и unsubscribe не оставляют подписку', async () => {
  const { app, pool } = await fixture();
  const created = await request(app)
    .post('/v1/webhook-subscriptions')
    .set(auth)
    .send({ target_url: 'https://hooks.example.test/catch/1', event: 'saved_work.changed' });
  assert.equal(created.status, 201);
  await request(app).delete(`/v1/webhook-subscriptions/${created.body.id}`).set(auth).expect(204);
  const rows = await pool.query('SELECT * FROM webhook_subscriptions');
  assert.equal(rows.rowCount, 0);
  await pool.end();
});

test('повторный upsert оставляет одну работу и отправляет hook', async () => {
  const { app, pool, deliveries } = await fixture();
  await request(app)
    .post('/v1/webhook-subscriptions')
    .set(auth)
    .send({ target_url: 'https://hooks.example.test/catch/1', event: 'saved_work.changed' });
  await request(app).put('/v1/saved-works/W123').set(auth).send({ title: 'First title' }).expect(200);
  await request(app).put('/v1/saved-works/W123').set(auth).send({ title: 'Updated title' }).expect(200);
  const rows = await pool.query('SELECT * FROM saved_works');
  assert.equal(rows.rowCount, 1);
  assert.equal(rows.rows[0].title, 'Updated title');
  assert.equal(deliveries.length, 2);
  await pool.end();
});

test('повтор idempotency key не добавляет строку и не меняет сумму', async () => {
  const { app, pool } = await fixture();
  await request(app).put('/v1/saved-works/W123').set(auth).send({ title: 'Work' }).expect(200);
  const body = { openalex_id: 'W123', score: 10, source_event_id: 'event-1' };
  const first = await request(app).post('/v1/reviews').set(auth).set('idempotency-key', 'stable').send(body);
  const second = await request(app).post('/v1/reviews').set(auth).set('idempotency-key', 'stable').send(body);
  assert.equal(first.status, 201);
  assert.equal(second.status, 200);
  assert.equal(second.body.replayed, true);
  assert.equal(first.body.total_score, 10);
  assert.equal(second.body.total_score, 10);
  const rows = await pool.query('SELECT * FROM review_ledger');
  assert.equal(rows.rowCount, 1);
  await pool.end();
});
