import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { createHash, randomBytes, timingSafeEqual, scrypt as scryptCallback } from 'node:crypto';
import { promisify } from 'node:util';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { db, initDb, OWNER_EMAIL, PAGE_COPY, COLLECTIONS, publicData } from './db.mjs';

const scrypt=promisify(scryptCallback);
const ROOT=resolve(fileURLToPath(new URL('./public/',import.meta.url)));
const PORT=Number(process.env.PORT||3000);
const HOST=process.env.HOST||'127.0.0.1';
const PRODUCTION=process.env.NODE_ENV==='production';
const DISCORD='https://discord.gg/FuspHdkmEN';
const STATUS_VALUES=new Set(['On Duty','Off Duty','Training','Deployed','Available','Away']);
const FACTIONS=new Set(['Both','Republic','Empire']);
const counters=new Map();
initDb();

function json(res,code,data){const output=JSON.stringify(data);res.writeHead(code,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(output);}
function failure(res,code,message){return json(res,code,{error:message});}
function sha(s){return createHash('sha256').update(s).digest('hex');}
function sameString(a,b){const x=Buffer.from(String(a),'utf8'),y=Buffer.from(String(b),'utf8');return x.length===y.length&&timingSafeEqual(x,y);}
function clientIp(req){if(process.env.TRUST_PROXY==='1'){const first=String(req.headers['x-forwarded-for']||'').split(',')[0].trim();if(first)return first;}return req.socket.remoteAddress||'unknown';}
function limit(req,key,max,windowMs){const k=`${key}:${sha(clientIp(req))}`;const now=Date.now();let rec=counters.get(k);if(!rec||now-rec.since>windowMs)rec={since:now,count:0};rec.count++;counters.set(k,rec);if(counters.size>25000)for(const [kk,rr] of counters)if(now-rr.since>windowMs)counters.delete(kk);return rec.count<=max;}
function cookies(req){const out={};for(const part of String(req.headers.cookie||'').split(';')){const i=part.indexOf('=');if(i>0)out[part.slice(0,i).trim()]=part.slice(i+1).trim();}return out;}
function auth(req){const token=cookies(req).guc_session;if(!token||token.length!==64||!/^[a-f0-9]+$/.test(token))return null;const sess=db.prepare('SELECT csrf_token,expires_at FROM sessions WHERE token_hash=? AND admin_id=1').get(sha(token));return sess&&sess.expires_at>Date.now()?sess:null;}
function cookie(res,token,age){res.setHeader('Set-Cookie',`guc_session=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${age}${PRODUCTION?'; Secure':''}`);}
function validOrigin(req){const origin=req.headers.origin;if(!origin)return true;const expected=process.env.SITE_ORIGIN||`${PRODUCTION?'https':'http'}://${req.headers.host}`;return origin===expected;}
function adminWrite(req,sess){return !!sess&&sameString(req.headers['x-csrf-token']||'',sess.csrf_token)&&validOrigin(req);}
function plain(v,max=160,required=false){if(typeof v!=='string')throw Error('All text fields must contain text.');const s=v.trim();if(s.length>max||s.includes('\0')||(required&&!s))throw Error(`Text must be 1–${max} characters.`);return s;}
async function body(req){let chunks=[],size=0;for await(const c of req){size+=c.length;if(size>32768)throw Object.assign(new Error('Request too large.'),{httpStatus:413});chunks.push(c);}let value;try{value=JSON.parse(Buffer.concat(chunks).toString('utf8')||'{}');}catch{throw Error('Invalid JSON.');}if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Invalid request body.');return value;}
function cleanStatus(b){const status=plain(b.status,24,true);if(!STATUS_VALUES.has(status))throw Error('Choose a valid status.');return {display_name:plain(b.display_name,48,true),designation:plain(b.designation||'',40),rank:plain(b.rank||'',48),unit:plain(b.unit||'',64),status,note:plain(b.note||'',220)};}
function sendStatus(res,code,id,editCode){json(res,code,{ok:true,id,editCode});}
function updateStatus(id,value){db.prepare('UPDATE statuses SET display_name=?,designation=?,rank=?,unit=?,status=?,note=?,updated_at=datetime(\'now\') WHERE id=?').run(value.display_name,value.designation,value.rank,value.unit,value.status,value.note,id);}
function writableRecord(collection,b){const out={};for(const [field,type] of Object.entries(COLLECTIONS[collection].fields)){
 let v=b[field];
 if(type==='number'){v=Number(v??0);if(!Number.isSafeInteger(v)||v<0||v>1000000000000)throw Error(`${field} must be a non-negative whole number.`);}
 else if(type==='boolean')v=v===true||v===1||v==='1'?1:0;
 else if(type==='faction'){v=plain(v||'Both',32,true);if(!FACTIONS.has(v))throw Error('Invalid faction.');}
 else if(type==='url'){v=plain(v||'',255);if(v&&!/^https:\/\/[a-z0-9.-]+(?:\:[0-9]+)?(?:[/?#][^\s]*)?$/i.test(v))throw Error('Allied website must be a valid HTTPS URL.');}
 else v=plain(v||'',type==='long'?2000:type==='datetime'?40:100,type==='text'&&['name','title','abbreviation','branch'].includes(field));
 out[field]=v;
 }
 return out;
}
function statusList(){return db.prepare('SELECT id,display_name,designation,rank,unit,status,note,created_at,updated_at FROM statuses ORDER BY updated_at DESC LIMIT 200').all();}
function routeApi(req,res,path){return (async()=>{
 const method=req.method;
 if(path==='/api/health'&&method==='GET')return json(res,200,{ok:true});
 if(path==='/api/bootstrap'&&method==='GET')return json(res,200,{...publicData(),discord:DISCORD});
 if(path==='/api/statuses'&&method==='GET')return json(res,200,{statuses:statusList()});
 if(path==='/api/admin/session'&&method==='GET')return json(res,200,{authenticated:!!auth(req),email:auth(req)?OWNER_EMAIL:null});
 if(path==='/api/admin/login'&&method==='POST'){
  if(!validOrigin(req))return failure(res,403,'Invalid origin.');
  if(!limit(req,'login',6,15*60*1000))return failure(res,429,'Too many login attempts. Try again later.');
  const b=await body(req);const email=plain(b.email||'',254).toLowerCase();const pwd=b.password; if(typeof pwd!=='string'||pwd.length>256)throw Error('Invalid password.');
  const row=db.prepare('SELECT salt,password_hash FROM admins WHERE id=1').get();
  if(!row||email!==OWNER_EMAIL)return failure(res,401,'Invalid owner email or password.');
  const check=(await scrypt(pwd,Buffer.from(row.salt,'hex'),64)).toString('hex');
  if(!sameString(check,row.password_hash))return failure(res,401,'Invalid owner email or password.');
  const token=randomBytes(32).toString('hex'),csrf=randomBytes(32).toString('hex');
  db.prepare('INSERT INTO sessions(token_hash,csrf_token,admin_id,expires_at) VALUES (?,?,1,?)').run(sha(token),csrf,Date.now()+7*86400000);
  db.prepare('DELETE FROM sessions WHERE expires_at<?').run(Date.now());
  cookie(res,token,7*86400);return json(res,200,{ok:true,email:OWNER_EMAIL,csrfToken:csrf});
 }
 if(path==='/api/admin/logout'&&method==='POST'){
  const session=auth(req);if(!adminWrite(req,session))return failure(res,403,'Not authorized.');
  db.prepare('DELETE FROM sessions WHERE token_hash=?').run(sha(cookies(req).guc_session));cookie(res,'',0);return json(res,200,{ok:true});
 }
 if(path==='/api/status'&&method==='POST'){
  if(!validOrigin(req))return failure(res,403,'Invalid origin.');
  if(!limit(req,'status',4,60*60*1000))return failure(res,429,'Too many posts from this connection. Try again later.');
  const b=await body(req);if(b.website)return failure(res,400,'Submission failed.');const v=cleanStatus(b);const editCode=randomBytes(18).toString('base64url');
  const r=db.prepare('INSERT INTO statuses(display_name,designation,rank,unit,status,note,edit_hash) VALUES (?,?,?,?,?,?,?)').run(v.display_name,v.designation,v.rank,v.unit,v.status,v.note,sha(editCode));return sendStatus(res,201,Number(r.lastInsertRowid),editCode);
 }
 const sm=path.match(/^\/api\/status\/(\d+)(?:\/(remove))?$/);
 if(sm&&(method==='PUT'||method==='POST')){
  if(!validOrigin(req))return failure(res,403,'Invalid origin.');
  if(!limit(req,'editstatus',15,60*60*1000))return failure(res,429,'Too many attempts.');
  const id=Number(sm[1]),b=await body(req),code=plain(b.editCode||'',80,true);const r=db.prepare('SELECT edit_hash FROM statuses WHERE id=?').get(id);
  if(!r||!sameString(sha(code),r.edit_hash))return failure(res,403,'Invalid entry ID or private edit code.');
  if(sm[2]==='remove'&&method==='POST'){db.prepare('DELETE FROM statuses WHERE id=?').run(id);return json(res,200,{ok:true});}
  if(!sm[2]&&method==='PUT'){updateStatus(id,cleanStatus(b));return json(res,200,{ok:true});}
 }
 const session=auth(req);
 if(path==='/api/admin/dashboard'&&method==='GET'){
  if(!session)return failure(res,401,'Owner login required.');
  const dashboard=publicData();dashboard.statuses=db.prepare('SELECT id,display_name,designation,rank,unit,status,note,created_at,updated_at FROM statuses ORDER BY updated_at DESC').all();
  return json(res,200,{...dashboard,discord:DISCORD,csrfToken:session.csrf_token,email:OWNER_EMAIL});
 }
 if(path.startsWith('/api/admin/')&&method!=='GET'){
  if(!adminWrite(req,session))return failure(res,403,'Owner session or security token missing.');
  if(path==='/api/admin/password'&&method==='PUT'){
   const b=await body(req),old=b.currentPassword,next=b.newPassword;
   if(typeof old!=='string'||typeof next!=='string'||old.length>256||next.length>256)throw Error('Invalid password fields.');
   if(next.length<16)return failure(res,400,'New password must be at least 16 characters.');
   const r=db.prepare('SELECT salt,password_hash FROM admins WHERE id=1').get();const oldHash=(await scrypt(old,Buffer.from(r.salt,'hex'),64)).toString('hex');
   if(!sameString(oldHash,r.password_hash))return failure(res,403,'Current password is incorrect.');
   const salt=randomBytes(32).toString('hex'),hash=(await scrypt(next,Buffer.from(salt,'hex'),64)).toString('hex');
   db.prepare('UPDATE admins SET salt=?,password_hash=? WHERE id=1').run(salt,hash);
   db.prepare('DELETE FROM sessions').run();cookie(res,'',0);return json(res,200,{ok:true,message:'Password changed. Sign in again.'});
  }
  const cm=path.match(/^\/api\/admin\/content\/([a-z_]+)$/);
  if(cm&&method==='PUT'){
   if(!(cm[1] in PAGE_COPY))return failure(res,404,'Content field not found.');
   const b=await body(req),value=plain(b.value||'',8000);db.prepare('INSERT INTO site_content(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value').run(cm[1],value);return json(res,200,{ok:true});
  }
  const rm=path.match(/^\/api\/admin\/(high_command|units|ranks|events|announcements|rewards|discord_roles|discord_channels|certifications|allies|statuses)(?:\/(\d+))?$/);
  if(rm){const [,collection,idText]=rm,id=idText?Number(idText):null;
   if(collection==='statuses'&&id&&method==='DELETE'){db.prepare('DELETE FROM statuses WHERE id=?').run(id);return json(res,200,{ok:true});}
   if(collection==='statuses'&&id&&method==='PUT'){const v=cleanStatus(await body(req));const r=db.prepare('SELECT id FROM statuses WHERE id=?').get(id);if(!r)return failure(res,404,'Entry not found.');updateStatus(id,v);return json(res,200,{ok:true});}
   if(collection==='statuses')return failure(res,405,'Use status moderation to remove a status.');
   if(method==='POST'&&!id){const v=writableRecord(collection,await body(req)),fields=Object.keys(v),q=fields.map(()=>'?').join(',');let r;
     if(collection==='announcements')r=db.prepare(`INSERT INTO ${collection}(${fields.join(',')}) VALUES (${q})`).run(...Object.values(v));
     else r=db.prepare(`INSERT INTO ${collection}(${fields.join(',')}) VALUES (${q})`).run(...Object.values(v));
     return json(res,201,{ok:true,id:Number(r.lastInsertRowid)});
   }
   if(id&&method==='PUT'){const v=writableRecord(collection,await body(req));const fields=Object.keys(v);const r=db.prepare(`UPDATE ${collection} SET ${fields.map(f=>`${f}=?`).join(',')} WHERE id=?`).run(...Object.values(v),id);return r.changes?json(res,200,{ok:true}):failure(res,404,'Entry not found.');}
   if(id&&method==='DELETE'){db.prepare(`DELETE FROM ${collection} WHERE id=?`).run(id);return json(res,200,{ok:true});}
  }
 }
 return failure(res,404,'Endpoint not found.');
 })().catch(e=>{const code=e.httpStatus||((e.message.startsWith('Text')||e.message.startsWith('All text')||e.message.startsWith('Choose')||e.message.startsWith('Invalid')||e.message.startsWith('Request')||e.message.includes('must')||e.message.includes('URL')||e.message.includes('field'))?400:500);if(code===500)console.error('Server error:',e);return failure(res,code,code===500?'Internal server error.':e.message);});}

const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.webp':'image/webp','.svg':'image/svg+xml','.ico':'image/x-icon','.json':'application/json; charset=utf-8'};
const server=http.createServer(async(req,res)=>{
 res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','strict-origin-when-cross-origin');res.setHeader('X-Frame-Options','DENY');
 res.setHeader('Permissions-Policy','camera=(), microphone=(), geolocation=()');
 res.setHeader('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
 if(PRODUCTION)res.setHeader('Strict-Transport-Security','max-age=31536000; includeSubDomains');
 if(!['GET','POST','PUT','DELETE'].includes(req.method))return failure(res,405,'Method not allowed.');
 let path;try{path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);}catch{return failure(res,400,'Invalid URL.');}
 if(path.startsWith('/api/'))return routeApi(req,res,path);
 if(req.method!=='GET')return failure(res,405,'Method not allowed.');
 const target=resolve(ROOT,`.${path==='/'?'/index.html':path}`);
 if(target!==ROOT&&!target.startsWith(ROOT+sep))return failure(res,403,'Forbidden.');
 try{const f=await stat(target);if(!f.isFile())return failure(res,404,'File not found.');const ext=target.slice(target.lastIndexOf('.'));if(!mime[ext])return failure(res,403,'File type not allowed.');
  const buf=await readFile(target);res.writeHead(200,{'Content-Type':mime[ext],'Cache-Control':ext==='.html'?'no-store':'public, max-age=86400'});res.end(buf);
 }catch{return failure(res,404,'File not found.');}
});
server.listen(PORT,HOST,()=>console.log(`GUC website running at http://${HOST}:${PORT} | Admin: ${OWNER_EMAIL} | Discord: ${DISCORD}`));
