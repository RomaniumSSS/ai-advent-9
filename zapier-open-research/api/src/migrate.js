import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createPool } from './db.js';

const here = dirname(fileURLToPath(import.meta.url));
const sql = await readFile(join(here, '..', 'migrations', '001_initial.sql'), 'utf8');
const pool = createPool();

try {
  await pool.query(sql);
  console.log('Database schema is ready');
} finally {
  await pool.end();
}
