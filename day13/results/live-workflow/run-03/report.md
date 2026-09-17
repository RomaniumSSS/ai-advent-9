# Semi-autonomous workflow — real-provider live validation

- Result: `FAIL`
- Provenance: real OpenRouter provider responses; fake/mock forbidden
- Model: `deepseek-v4-flash`
- Provider calls: 3/3
- Tokens: 635 input + 371 output
- Reported cost: `$0.00005578`; cumulative with precursors: `$0.0017562643` (limit `$0.005`)
- Final FSM stage: `done`
- Restart duplicate calls: 0
- Automatic retries: 0

Fake/mock responses are not accepted by this evaluator. Full sanitized provider traces and responses are stored in `report.json`; the API key and credential path are not stored.
