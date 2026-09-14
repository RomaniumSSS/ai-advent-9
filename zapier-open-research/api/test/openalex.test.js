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
          {id: 'https://openalex.org/W2', display_name: 'Published', publication_date: '2026-09-14'},
        ]}),
      };
    },
  });
  assert.deepEqual(items.map((item) => item.id), ['W2']);
});
