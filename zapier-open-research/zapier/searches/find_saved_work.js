const { apiUrl, required } = require('../lib/http');

const perform = async (z, bundle) => {
  required(z, bundle.inputData, ['doi']);
  const response = await z.request({
    url: apiUrl('/v1/saved-works'),
    params: { doi: bundle.inputData.doi },
  });
  return response.data.items || [];
};

module.exports = {
  key: 'find_saved_work',
  noun: 'Saved Work',
  display: {
    label: 'Find Saved Work by DOI',
    description: 'Finds a saved work by exact DOI and returns no result when absent.',
  },
  operation: {
    perform,
    inputFields: [{ key: 'doi', label: 'DOI', type: 'string', required: true }],
    sample: {
      openalex_id: 'W2741809807',
      title: 'The state of OA',
      doi: 'https://doi.org/10.7287/peerj.preprints.3119v1',
      updated_at: '2026-09-12T10:00:00.000Z',
    },
    outputFields: [
      { key: 'openalex_id', label: 'OpenAlex ID' },
      { key: 'title', label: 'Title' },
      { key: 'doi', label: 'DOI' },
      { key: 'updated_at', label: 'Updated At', type: 'datetime' },
    ],
  },
};
