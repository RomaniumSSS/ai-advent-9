const { apiUrl, required } = require('../lib/http');

const fallbackEvent = {
  id: 'sample:saved-work:W2741809807',
  event: 'saved_work.changed',
  occurred_at: '2017-08-02T00:00:00.000Z',
  work: {
    openalex_id: 'W2741809807',
    title: 'The state of OA: a large-scale analysis of the prevalence and impact of Open Access articles',
    doi: 'https://doi.org/10.7287/peerj.preprints.3119v1',
    note: 'Sample built from a CC0 OpenAlex record.',
  },
};

const performSubscribe = async (z, bundle) => {
  const response = await z.request({
    url: apiUrl('/v1/webhook-subscriptions'),
    method: 'POST',
    body: { target_url: bundle.targetUrl, event: 'saved_work.changed' },
  });
  return response.data;
};

const performUnsubscribe = async (z, bundle) => {
  required(z, bundle.subscribeData || {}, ['id']);
  await z.request({
    url: apiUrl(`/v1/webhook-subscriptions/${encodeURIComponent(bundle.subscribeData.id)}`),
    method: 'DELETE',
  });
  return {};
};

const perform = (z, bundle) => {
  const payload = bundle.cleanedRequest || {};
  required(z, payload, ['id', 'event', 'occurred_at', 'work']);
  if (payload.event !== 'saved_work.changed' || !payload.work.openalex_id) {
    throw new z.errors.HaltedError('Malformed saved_work.changed webhook payload.');
  }
  return [payload];
};

const performList = async (z) => {
  const response = await z.request({ url: apiUrl('/v1/saved-works') });
  const events = (response.data.items || []).slice(0, 3).map((work) => ({
    id: `saved-work:${work.openalex_id}:${work.updated_at}`,
    event: 'saved_work.changed',
    occurred_at: work.updated_at,
    work,
  }));
  return events.length ? events : [fallbackEvent];
};

module.exports = {
  key: 'saved_work_changed',
  noun: 'Saved Work Event',
  display: {
    label: 'Saved Research Work Changed',
    description: 'Triggers when a saved research work is created or updated.',
  },
  operation: {
    type: 'hook',
    performSubscribe,
    performUnsubscribe,
    perform,
    performList,
    sample: fallbackEvent,
    outputFields: [
      { key: 'id', label: 'Event ID', primary: true },
      { key: 'event', label: 'Event Type' },
      { key: 'occurred_at', label: 'Occurred At', type: 'datetime' },
      { key: 'work__openalex_id', label: 'OpenAlex ID' },
      { key: 'work__title', label: 'Title' },
      { key: 'work__doi', label: 'DOI' },
      { key: 'work__article_url', label: 'Best Article URL' },
      { key: 'work__score', label: 'Automatic Score', type: 'integer' },
      { key: 'work__score_explanation', label: 'Score Explanation' },
      { key: 'work__note', label: 'Note' },
    ],
  },
};
