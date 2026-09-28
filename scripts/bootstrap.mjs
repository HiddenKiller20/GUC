import { randomBytes, scrypt as scryptCallback } from 'node:crypto';
import { promisify } from 'node:util';
import { db, initDb, OWNER_EMAIL } from '../db.mjs';

initDb();
const existing = db.prepare('SELECT id FROM admins WHERE id=1').get();
if (!existing) {
  const password = process.env.SETUP_PASSWORD;
  if (typeof password === 'string' && password.length >= 16 && Buffer.byteLength(password) <= 256) {
    const salt = randomBytes(32).toString('hex');
    const hash = (await promisify(scryptCallback)(password, Buffer.from(salt, 'hex'), 64)).toString('hex');
    db.prepare("INSERT INTO admins(id,email,salt,password_hash,created_at) VALUES(1,?,?,?,datetime('now'))")
      .run(OWNER_EMAIL, salt, hash);
    console.log(`Initial owner account configured for ${OWNER_EMAIL}. Remove SETUP_PASSWORD from the environment once configured.`);
  } else {
    console.warn('No owner account yet. Configure one using npm run setup, or provide SETUP_PASSWORD (16+ characters) on the server.');
  }
}
db.close();
