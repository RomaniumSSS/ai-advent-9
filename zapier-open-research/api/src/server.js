import { createApp } from './app.js';
import { createPool } from './db.js';

const pool = createPool();
const app = createApp({ pool });
const port = Number(process.env.PORT || 3100);

const server = app.listen(port, '0.0.0.0', () => {
  console.log(`Open Research Watch API listening on port ${port}`);
});

async function shutdown() {
  server.close(async () => {
    await pool.end();
    process.exit(0);
  });
}

process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
