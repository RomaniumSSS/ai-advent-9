import assert from 'node:assert/strict';
import test from 'node:test';
import { listWorks } from '../src/openalex.js';

test('live OpenAlex возвращает настоящие работы со стабильными id', async () => {
  const first = await listWorks({ query: 'artificial intelligence', perPage: 3 });
  const second = await listWorks({ query: 'artificial intelligence', perPage: 3 });
  assert.ok(first.length > 0);
  assert.deepEqual(first.map((work) => work.id), second.map((work) => work.id));
  assert.ok(first.every((work) => /^W\d+$/.test(work.id)));
  assert.ok(first.every((work) => Number.isInteger(work.score)));
  assert.ok(first.every((work) => work.article_url));
});
