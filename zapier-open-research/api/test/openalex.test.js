import assert from 'node:assert/strict';
import test from 'node:test';
import { listWorks } from '../src/openalex.js';

test('polling запрашивает даты до сегодня и не пропускает будущую запись из upstream', async () => {
  const items = await listWorks({
    query: 'retrieval augmented generation',
    now: new Date('2026-09-14T12:00:00Z'),
    fetchImpl: async (url) => {
      assert.equal(url.searchParams.get('filter'), 'to_publication_date:2026-09-14');
      assert.equal(url.searchParams.get('search'), 'retrieval augmented generation');
      return {
        ok: true,
        json: async () => ({results: [
          {id: 'https://openalex.org/W1', display_name: 'Future', publication_date: '2029-05-06'},
          {id: 'https://openalex.org/W2', display_name: 'Retrieval augmented generation published', publication_date: '2026-09-14'},
        ]}),
      };
    },
  });
  assert.deepEqual(items.map((item) => item.id), ['W2']);
});

test('polling отсекает случайные совпадения full-text и сохраняет лимит результата', async () => {
  const items = await listWorks({
    query: 'retrieval augmented generation',
    perPage: 1,
    now: new Date('2026-09-15T12:00:00Z'),
    fetchImpl: async (url) => {
      assert.equal(url.searchParams.get('per-page'), '100');
      return {
        ok: true,
        json: async () => ({ results: [
          { id: 'https://openalex.org/W1', display_name: 'Asset allocation', publication_date: '2026-09-15' },
          { id: 'https://openalex.org/W2', display_name: 'Retrieval-augmented generation for medicine', publication_date: '2026-09-15' },
          { id: 'https://openalex.org/W3', display_name: 'Retrieval-augmented generation for finance', publication_date: '2026-09-15' },
        ] }),
      };
    },
  });
  assert.deepEqual(items.map((item) => item.id), ['W2']);
  assert.ok(items[0].score_breakdown.relevance >= 20);
});
