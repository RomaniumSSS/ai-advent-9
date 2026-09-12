const { apiUrl, required } = require('../lib/http');

const perform = async (z, bundle) => {
  required(z, bundle.inputData, ['openalex_id', 'score', 'source_event_id']);
  const score = Number(bundle.inputData.score);
  if (!Number.isInteger(score) || score < -100 || score > 100) {
    throw new z.errors.HaltedError('score must be an integer between -100 and 100.');
  }
  // Один и тот же исходный event всегда даёт один ключ, включая повторы Zapier.
  const idempotencyKey = z.hash(
    'sha256',
    `open-research-review-v1:${bundle.inputData.openalex_id}:${bundle.inputData.source_event_id}`,
  );
  const response = await z.request({
    url: apiUrl('/v1/reviews'),
    method: 'POST',
    headers: { 'idempotency-key': idempotencyKey },
    body: {
      openalex_id: bundle.inputData.openalex_id,
      score,
      source_event_id: bundle.inputData.source_event_id,
    },
  });
  return response.data;
};

module.exports = {
  key: 'record_review',
  noun: 'Review Score',
  display: {
    label: 'Record Review Score',
    description: 'Adds an idempotent score entry for a saved research work.',
  },
  operation: {
    perform,
    inputFields: [
      { key: 'openalex_id', label: 'OpenAlex ID', type: 'string', required: true },
      { key: 'score', label: 'Score', type: 'integer', required: true },
      {
        key: 'source_event_id',
        label: 'Source Event ID',
        type: 'string',
        required: true,
        helpText: 'Map the trigger record ID here. Zapier retries will reuse it.',
      },
    ],
    sample: {
      id: '8f98bf58-790a-4f5d-a323-692cc15c129f',
      openalex_id: 'W2741809807',
      score: 10,
      total_score: 10,
      replayed: false,
    },
  },
};
