const { apiUrl } = require('./lib/http');

const test = (z) => z.request({ url: apiUrl('/v1/me') });

module.exports = {
  type: 'custom',
  fields: [
    {
      key: 'api_key',
      label: 'API Key',
      type: 'password',
      required: true,
      helpText: 'API key generated for the deployed Open Research Watch service.',
    },
  ],
  test,
  connectionLabel: '{{json.name}}',
};
