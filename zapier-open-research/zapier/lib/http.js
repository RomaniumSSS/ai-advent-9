function apiUrl(path) {
  const baseUrl = process.env.OPEN_RESEARCH_API_BASE_URL;
  if (!baseUrl) throw new Error('OPEN_RESEARCH_API_BASE_URL is not configured.');
  return `${baseUrl.replace(/\/$/, '')}${path}`;
}

function messageFrom(response) {
  return response.data?.error?.message || `API request failed with status ${response.status}.`;
}

const addApiKey = (request, _z, bundle) => {
  request.headers = request.headers || {};
  request.headers['x-api-key'] = bundle.authData.api_key;
  // AICODE-NOTE: собственная обработка нужна, чтобы 422 и 429 получили разные
  // классы Zapier, а не превратились в один автоматический HTTP error.
  request.skipThrowForStatus = true;
  return request;
};

const handleApiError = (response, z) => {
  if (response.status < 400) return response;
  const message = messageFrom(response);
  if (response.status === 401 || response.status === 403) {
    throw new z.errors.ExpiredAuthError(message);
  }
  if (response.status === 429) {
    const retryAfter = Number(response.headers.get('retry-after')) || 60;
    throw new z.errors.ThrottledError(message, retryAfter);
  }
  if ([400, 409, 422].includes(response.status)) {
    throw new z.errors.HaltedError(message);
  }
  throw new z.errors.Error(message, 'OpenResearchApiError', response.status);
};

function required(z, inputData, fields) {
  for (const field of fields) {
    if (inputData[field] === undefined || inputData[field] === null || inputData[field] === '') {
      throw new z.errors.HaltedError(`${field} is required.`);
    }
  }
}

module.exports = { apiUrl, addApiKey, handleApiError, required };
