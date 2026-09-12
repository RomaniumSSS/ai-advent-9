import { scoreWork } from './scoring.js';

const OPENALEX_BASE_URL = 'https://api.openalex.org';

function shortId(value) {
  return String(value || '').replace('https://openalex.org/', '');
}

export function normalizeWork(work) {
  return {
    id: shortId(work.id),
    title: work.display_name || work.title || 'Untitled work',
    doi: work.doi || null,
    publication_date: work.publication_date || null,
    primary_source: work.primary_location?.source?.display_name || null,
    open_access_url: work.open_access?.oa_url || null,
    cited_by_count: work.cited_by_count ?? 0,
    openalex_url: work.id,
  };
}

export async function listWorks({ query, perPage = 25, fetchImpl = fetch }) {
  const url = new URL('/works', OPENALEX_BASE_URL);
  url.searchParams.set('sort', 'publication_date:desc');
  url.searchParams.set('per-page', String(Math.min(Math.max(perPage, 1), 100)));
  url.searchParams.set(
    'select',
    'id,display_name,doi,publication_date,primary_location,open_access,cited_by_count',
  );
  if (query) url.searchParams.set('search', query);
  if (process.env.OPENALEX_API_KEY) {
    url.searchParams.set('api_key', process.env.OPENALEX_API_KEY);
  }
  if (process.env.OPENALEX_MAILTO) {
    url.searchParams.set('mailto', process.env.OPENALEX_MAILTO);
  }

  const response = await fetchImpl(url, {
    headers: { 'User-Agent': 'OpenResearchWatch/1.0' },
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    const error = new Error(`OpenAlex request failed with ${response.status}`);
    error.status = response.status;
    error.retryAfter = response.headers.get('retry-after');
    throw error;
  }
  const body = await response.json();
  return (body.results || []).map((rawWork) => {
    const work = normalizeWork(rawWork);
    return { ...work, ...scoreWork(work, query) };
  });
}
