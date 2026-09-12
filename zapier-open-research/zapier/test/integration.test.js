const nock = require('nock');
const zapier = require('zapier-platform-core');
const App = require('../index');

const appTester = zapier.createAppTester(App);
const baseUrl = 'https://open-research.example.test';
const authData = { api_key: 'valid-key' };

beforeAll(() => {
  process.env.OPEN_RESEARCH_API_BASE_URL = baseUrl;
  nock.disableNetConnect();
});

afterEach(() => {
  nock.cleanAll();
});

afterAll(() => nock.enableNetConnect());

test('auth принимает верный ключ и возвращает label data', async () => {
  nock(baseUrl, { reqheaders: { 'x-api-key': 'valid-key' } })
    .get('/v1/me')
    .reply(200, { id: 'demo', name: 'Open Research Watch Demo' });
  const result = await appTester(App.authentication.test, { authData });
  expect(result.data.name).toBe('Open Research Watch Demo');
});

test('auth отклоняет неверный ключ с понятным сообщением', async () => {
  nock(baseUrl).get('/v1/me').reply(401, {
    error: { code: 'invalid_api_key', message: 'The API key is invalid.' },
  });
  await expect(appTester(App.authentication.test, { authData: { api_key: 'wrong' } }))
    .rejects.toThrow('The API key is invalid.');
});

test('polling сохраняет id между двумя одинаковыми ответами', async () => {
  const response = { items: [{ id: 'W123', title: 'Stable' }] };
  nock(baseUrl).get('/v1/works').query(true).twice().reply(200, response);
  const operation = App.triggers.new_work.operation.perform;
  const bundle = { authData, inputData: {} };
  const first = await appTester(operation, bundle);
  const second = await appTester(operation, bundle);
  expect(first[0].id).toBe('W123');
  expect(second[0].id).toBe(first[0].id);
});

test('пустой polling возвращает []', async () => {
  nock(baseUrl).get('/v1/works').query(true).reply(200, { items: [] });
  const result = await appTester(App.triggers.new_work.operation.perform, {
    authData,
    inputData: {},
  });
  expect(result).toEqual([]);
});

test('subscribe затем unsubscribe удаляет регистрацию', async () => {
  const subscriptions = new Set();
  nock(baseUrl)
    .post('/v1/webhook-subscriptions')
    .reply(201, (_uri, body) => {
      expect(body.target_url).toBe('https://hooks.zapier.com/test');
      subscriptions.add('subscription-1');
      return { id: 'subscription-1' };
    });
  nock(baseUrl).delete('/v1/webhook-subscriptions/subscription-1').reply(204, () => {
    subscriptions.delete('subscription-1');
  });
  const operation = App.triggers.saved_work_changed.operation;
  const subscribed = await appTester(operation.performSubscribe, {
    authData,
    inputData: {},
    targetUrl: 'https://hooks.zapier.com/test',
  });
  await appTester(operation.performUnsubscribe, {
    authData,
    subscribeData: subscribed,
  });
  expect(subscriptions.size).toBe(0);
});

test('malformed hook завершается HaltedError вместо crash или silent success', async () => {
  await expect(appTester(App.triggers.saved_work_changed.operation.perform, {
    authData,
    cleanedRequest: { event: 'saved_work.changed' },
  })).rejects.toMatchObject({ name: 'HaltedError' });
});

test('performList даёт setup sample при пустом хранилище', async () => {
  nock(baseUrl).get('/v1/saved-works').reply(200, { items: [] });
  const result = await appTester(App.triggers.saved_work_changed.operation.performList, {
    authData,
    inputData: {},
  });
  expect(result).toHaveLength(1);
  expect(result[0].work.openalex_id).toBe('W2741809807');
});

test('два upsert одного OpenAlex ID дают одну запись', async () => {
  const records = new Map();
  nock(baseUrl).put('/v1/saved-works/W123').twice().reply(200, (_uri, body) => {
    records.set('W123', { openalex_id: 'W123', ...body });
    return records.get('W123');
  });
  const operation = App.creates.save_work.operation.perform;
  await appTester(operation, { authData, inputData: { openalex_id: 'W123', title: 'First' } });
  await appTester(operation, { authData, inputData: { openalex_id: 'W123', title: 'Updated' } });
  expect(records.size).toBe(1);
  expect(records.get('W123').title).toBe('Updated');
});

test('повтор review использует тот же idempotency key и одну ledger entry', async () => {
  const ledger = new Map();
  let balance = 0;
  nock(baseUrl).post('/v1/reviews').twice().reply(function reply(_uri, body) {
    const key = this.req.headers['idempotency-key'];
    if (!ledger.has(key)) {
      ledger.set(key, body);
      balance += body.score;
    }
    return [200, { id: key, total_score: balance, replayed: ledger.size === 1 }];
  });
  const operation = App.creates.record_review.operation.perform;
  const bundle = {
    authData,
    inputData: { openalex_id: 'W123', score: 10, source_event_id: 'event-42' },
  };
  const first = await appTester(operation, bundle);
  const second = await appTester(operation, bundle);
  expect(ledger.size).toBe(1);
  expect(first.total_score).toBe(10);
  expect(second.total_score).toBe(10);
});

test('отсутствующее обязательное поле названо в HaltedError', async () => {
  await expect(appTester(App.creates.save_work.operation.perform, {
    authData,
    inputData: { openalex_id: 'W123' },
  })).rejects.toThrow('title is required.');
});

test('429 преобразуется в ThrottledError', async () => {
  nock(baseUrl).get('/v1/works').query(true).reply(429, {
    error: { message: 'Try later.' },
  }, { 'retry-after': '30' });
  await expect(appTester(App.triggers.new_work.operation.perform, {
    authData,
    inputData: {},
  })).rejects.toMatchObject({ name: 'ThrottledError' });
});

test('поиск без совпадения возвращает []', async () => {
  nock(baseUrl).get('/v1/saved-works').query({ doi: '10.1000/missing' }).reply(200, { items: [] });
  const result = await appTester(App.searches.find_saved_work.operation.perform, {
    authData,
    inputData: { doi: '10.1000/missing' },
  });
  expect(result).toEqual([]);
});
