const { apiUrl, required } = require('../lib/http');

const perform = async (z, bundle) => {
  required(z, bundle.inputData, ['openalex_id', 'title']);
  const response = await z.request({
    url: apiUrl(`/v1/saved-works/${encodeURIComponent(bundle.inputData.openalex_id)}`),
    method: 'PUT',
    body: bundle.inputData,
  });
  return response.data;
};

module.exports = {
  key: 'save_work',
  noun: 'Saved Work',
  display: {
    label: 'Create or Update Saved Work',
    description: 'Upserts a saved work by its stable OpenAlex ID.',
  },
  operation: {
    perform,
    inputFields: [
      { key: 'openalex_id', label: 'OpenAlex ID', type: 'string', required: true },
      { key: 'title', label: 'Title', type: 'string', required: true },
      { key: 'doi', label: 'DOI', type: 'string', required: false },
      { key: 'publication_date', label: 'Publication Date', type: 'datetime', required: false },
      { key: 'primary_source', label: 'Primary Source', type: 'string', required: false },
      { key: 'open_access_url', label: 'Open Access URL', type: 'string', required: false },
      { key: 'score', label: 'Automatic Score', type: 'integer', required: false },
      { key: 'score_explanation', label: 'Score Explanation', type: 'string', required: false },
      { key: 'note', label: 'Note', type: 'text', required: false },
    ],
    sample: {
      openalex_id: 'W2741809807',
      title: 'The state of OA',
      doi: 'https://doi.org/10.7287/peerj.preprints.3119v1',
      article_url: 'https://peerj.com/preprints/3119/',
      score: 60,
      score_explanation: 'title relevance 20/40; recency 0/30; open access 20/20; citations 10/10',
      updated_at: '2026-09-12T10:00:00.000Z',
    },
  },
};
