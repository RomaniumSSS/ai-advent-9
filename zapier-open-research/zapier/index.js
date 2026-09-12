const authentication = require('./authentication');
const { addApiKey, handleApiError } = require('./lib/http');
const newWork = require('./triggers/new_work');
const savedWorkChanged = require('./triggers/saved_work_changed');
const saveWork = require('./creates/save_work');
const recordReview = require('./creates/record_review');
const findSavedWork = require('./searches/find_saved_work');

module.exports = {
  version: require('./package.json').version,
  platformVersion: require('zapier-platform-core').version,
  authentication,
  flags: { cleanInputData: false },
  beforeRequest: [addApiKey],
  afterResponse: [handleApiError],
  triggers: {
    [newWork.key]: newWork,
    [savedWorkChanged.key]: savedWorkChanged,
  },
  creates: {
    [saveWork.key]: saveWork,
    [recordReview.key]: recordReview,
  },
  searches: {
    [findSavedWork.key]: findSavedWork,
  },
  searchOrCreates: {
    [findSavedWork.key]: {
      key: findSavedWork.key,
      display: {
        label: 'Find or Save a Research Work',
        description: 'Finds a saved work by DOI or saves it when absent.',
      },
      search: findSavedWork.key,
      create: saveWork.key,
    },
  },
};
