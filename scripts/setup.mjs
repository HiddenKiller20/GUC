import { randomBytes, scrypt as scryptCallback } from 'node:crypto';
import { promisify } from 'node:util';
import { createInterface } from 'node:readline/promises';
import { db, initDb, OWNER_EMAIL } from '../db.mjs';
const scrypt=promisify(scryptCallback);
initDb();
console.log(`Configuring the owner-only admin account: ${OWNER_EMAIL}`);
console.log('No ChatGPT or third-party login is used. The password is stored as a salted scrypt hash.');
let password=process.env.SETUP_PASSWORD;
if (!password) {
 const rl=createInterface({input:process.stdin,output:process.stdout});
 password=await rl.question('Enter a strong owner password (16+ characters): ');
 const confirm=await rl.question('Confirm password: ');
 rl.close();
 if(password!==confirm){console.error('Passwords did not match.');process.exit(1);}
}
if(typeof password!=='string'||password.length<16||Buffer.byteLength(password)>256){console.error('Use a password of 16–256 bytes.');process.exit(1);}
const salt=randomBytes(32).toString('hex');
const hash=(await scrypt(password,Buffer.from(salt,'hex'),64)).toString('hex');
password='';
db.prepare("INSERT INTO admins(id,email,salt,password_hash,created_at) VALUES(1,?,?,?,datetime('now')) ON CONFLICT(id) DO UPDATE SET email=excluded.email,salt=excluded.salt,password_hash=excluded.password_hash").run(OWNER_EMAIL,salt,hash);
db.prepare('DELETE FROM sessions').run();
console.log(`Owner account is ready: ${OWNER_EMAIL}. Existing admin sessions were signed out.`);
db.close();
