const DAY_MS = 24 * 60 * 60 * 1000;
const WORD_RE = /[\p{L}\p{N}]+/gu;

function words(value) {
  return new Set(String(value || '').toLocaleLowerCase('en').match(WORD_RE) || []);
}

function relevanceScore(title, query) {
  const queryWords = [...words(query)].filter((word) => word.length >= 3);
  if (!queryWords.length) return 0;
  const titleWords = words(title);
  const matched = queryWords.filter((word) => titleWords.has(word)).length;
  return Math.round((matched / queryWords.length) * 40);
}

function recencyScore(publicationDate, now) {
  const published = new Date(publicationDate);
  if (!publicationDate || Number.isNaN(published.getTime()) || published > now) return 0;
  const ageDays = Math.max(0, Math.floor((now.getTime() - published.getTime()) / DAY_MS));
  if (ageDays <= 30) return 30;
  if (ageDays <= 365) return 20;
  if (ageDays <= 730) return 10;
  return 0;
}

function citationScore(count) {
  const citations = Math.max(0, Number(count) || 0);
  return Math.min(10, Math.round(Math.log10(citations + 1) * 5));
}

export function scoreWork(work, query, now = new Date()) {
  const breakdown = {
    relevance: relevanceScore(work.title, query),
    recency: recencyScore(work.publication_date, now),
    open_access: work.open_access_url ? 20 : 0,
    citations: citationScore(work.cited_by_count),
  };
  const score = Object.values(breakdown).reduce((sum, value) => sum + value, 0);
  const explanation = [
    `title relevance ${breakdown.relevance}/40`,
    `recency ${breakdown.recency}/30`,
    `open access ${breakdown.open_access}/20`,
    `citations ${breakdown.citations}/10`,
  ].join('; ');
  return {
    score,
    score_breakdown: breakdown,
    score_explanation: explanation,
    article_url: work.open_access_url || work.doi || work.openalex_url,
  };
}
