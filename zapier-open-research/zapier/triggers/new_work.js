const { apiUrl } = require('../lib/http');

const perform = async (z, bundle) => {
  const response = await z.request({
    url: apiUrl('/v1/works'),
    params: {
      query: bundle.inputData.query || undefined,
      per_page: bundle.inputData.limit || 25,
    },
  });
  return response.data.items || [];
};

module.exports = {
  key: 'new_work',
  noun: 'Work',
  display: {
    label: 'New Research Work',
    description: 'Triggers when OpenAlex returns a new research work.',
  },
  operation: {
    perform,
    inputFields: [
      {
        key: 'query',
        label: 'Search Query',
        type: 'string',
        required: false,
        helpText: 'Optional full-text OpenAlex search, for example “retrieval augmented generation”.',
      },
      {
        key: 'limit',
        label: 'Results Per Poll',
        type: 'integer',
        required: false,
        default: '25',
      },
    ],
    sample: {
      id: 'W2741809807',
      title: 'The state of OA: a large-scale analysis of the prevalence and impact of Open Access articles',
      doi: 'https://doi.org/10.7287/peerj.preprints.3119v1',
      publication_date: '2017-08-02',
      primary_source: 'PeerJ Preprints',
      open_access_url: 'https://peerj.com/preprints/3119/',
      cited_by_count: 0,
      openalex_url: 'https://openalex.org/W2741809807',
      score: 60,
      score_explanation: 'title relevance 20/40; recency 0/30; open access 20/20; citations 10/10',
      article_url: 'https://peerj.com/preprints/3119/',
      score_breakdown: { relevance: 20, recency: 0, open_access: 20, citations: 10 },
    },
    outputFields: [
      { key: 'id', label: 'OpenAlex ID', primary: true },
      { key: 'title', label: 'Title' },
      { key: 'doi', label: 'DOI' },
      { key: 'publication_date', label: 'Publication Date', type: 'datetime' },
      { key: 'primary_source', label: 'Primary Source' },
      { key: 'open_access_url', label: 'Open Access URL' },
      { key: 'cited_by_count', label: 'Cited By Count', type: 'integer' },
      { key: 'openalex_url', label: 'OpenAlex URL' },
      { key: 'article_url', label: 'Best Article URL' },
      { key: 'score', label: 'Relevance Score', type: 'integer' },
      { key: 'score_explanation', label: 'Score Explanation' },
      { key: 'score_breakdown__relevance', label: 'Title Relevance Score', type: 'integer' },
      { key: 'score_breakdown__recency', label: 'Recency Score', type: 'integer' },
      { key: 'score_breakdown__open_access', label: 'Open Access Score', type: 'integer' },
      { key: 'score_breakdown__citations', label: 'Citation Score', type: 'integer' },
    ],
  },
};
