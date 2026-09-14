import assert from 'node:assert/strict';
import test from 'node:test';
import { scoreWork } from '../src/scoring.js';

test('рейтинг складывается из четырёх прозрачных критериев', () => {
  const result = scoreWork({
    title: 'Artificial Intelligence for Science',
    publication_date: '2026-09-01',
    open_access_url: 'https://example.org/article',
    doi: 'https://doi.org/10.1000/example',
    openalex_url: 'https://openalex.org/W123',
    cited_by_count: 99,
  }, 'artificial intelligence', new Date('2026-09-12T00:00:00Z'));

  assert.deepEqual(result.score_breakdown, {
    relevance: 40,
    recency: 30,
    open_access: 20,
    citations: 10,
  });
  assert.equal(result.score, 100);
  assert.equal(result.article_url, 'https://example.org/article');
  assert.match(result.score_explanation, /title relevance 40\/40/);
});

test('нет запроса, даты, OA и цитат — нет выдуманных баллов', () => {
  const result = scoreWork({ title: 'Unknown', cited_by_count: 0 }, '', new Date('2026-09-12'));
  assert.equal(result.score, 0);
  assert.equal(result.article_url, undefined);
});

test('будущая дата публикации не получает баллы за свежесть', () => {
  const result = scoreWork({title: 'Future', publication_date: '2029-05-06'}, '', new Date('2026-09-14'));
  assert.equal(result.score_breakdown.recency, 0);
});
