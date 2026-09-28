import { fileURLToPath } from 'node:url';
// Node 22+ loads the optional local .env directly; no dotenv package or external service.
try { process.loadEnvFile(fileURLToPath(new URL('./.env', import.meta.url))); }
catch (error) { if(error.code!=='ENOENT') throw error; }
