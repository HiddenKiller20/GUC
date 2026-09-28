import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import net from 'node:net';
import { fileURLToPath } from 'node:url';
const cwd=resolve(fileURLToPath(new URL('../',import.meta.url)));
const PASSWORD='testOwnerStrongPassword#456';

async function freePort(){return await new Promise((resolvePort,reject)=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolvePort(p));});s.on('error',reject);});}
function runNode(args,env){return new Promise((ok,bad)=>{const child=spawn(process.execPath,args,{cwd,env,stdio:['ignore','pipe','pipe']});let out='';child.stdout.on('data',c=>out+=c);child.stderr.on('data',c=>out+=c);child.on('error',bad);child.on('exit',code=>code===0?ok(out):bad(Error(`Exit ${code}: ${out}`)));});}
function startNode(args,env){const child=spawn(process.execPath,args,{cwd,env,stdio:['ignore','pipe','pipe']});return child;}
async function waitHealthy(base,child){for(let i=0;i<80;i++){if(child.exitCode!==null)throw Error('Server exited unexpectedly.');try{const r=await fetch(base+'/api/health');if(r.ok)return;}catch{}await new Promise(r=>setTimeout(r,80));}throw Error('Server did not become healthy.');}
async function request(base,path,{method='GET',body,cookie,csrf}={}){const headers={};if(body!==undefined)headers['Content-Type']='application/json';if(cookie)headers.Cookie=cookie;if(csrf)headers['x-csrf-token']=csrf;if(method!=='GET')headers.Origin=base;const r=await fetch(base+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body)});return {status:r.status,data:await r.json(),headers:r.headers};}

test('public pages, no-account status, and owner-only editable CMS',async t=>{
 const tmp=await mkdtemp(resolve(tmpdir(),'guc-test-'));const port=await freePort();const env={...process.env,DB_FILE:resolve(tmp,'test.db'),SETUP_PASSWORD:PASSWORD,OWNER_EMAIL:'bigt1576@gmail.com',PORT:String(port),HOST:'127.0.0.1',NODE_ENV:'development'};
 t.after(async()=>{await rm(tmp,{recursive:true,force:true});});
 await runNode(['scripts/setup.mjs'],env);
 const child=startNode(['server.mjs'],env);
 t.after(()=>{child.kill('SIGTERM');});
 const base=`http://127.0.0.1:${port}`;await waitHealthy(base,child);
 const page=await fetch(base+'/');assert.equal(page.status,200);assert.match(await page.text(),/Galactic Unification Corps/);
 const assets=await fetch(base+'/assets/fused.png');assert.equal(assets.status,200);assert.match(assets.headers.get('content-type'),/image\/png/);
 const publicSite=await request(base,'/api/bootstrap');assert.equal(publicSite.status,200);assert.ok(publicSite.data.units.length>4);assert.equal(publicSite.data.discord,'https://discord.gg/FuspHdkmEN');
 assert.equal((await request(base,'/api/admin/dashboard')).status,401);
 assert.equal((await request(base,'/api/admin/high_command',{method:'POST',body:{name:'Unauthorized'}})).status,403);
 const login=await request(base,'/api/admin/login',{method:'POST',body:{email:'bigt1576@gmail.com',password:PASSWORD}});assert.equal(login.status,200);
 const cookie=login.headers.get('set-cookie').split(';')[0];assert.ok(cookie.startsWith('guc_session='));assert.ok(login.data.csrfToken);
 const dash=await request(base,'/api/admin/dashboard',{cookie});assert.equal(dash.status,200);
 const csrf=dash.data.csrfToken;
 assert.equal((await request(base,'/api/admin/high_command',{method:'POST',cookie,body:{name:'Fake'}})).status,403,'CSRF is required');
 const newLeader=await request(base,'/api/admin/high_command',{method:'POST',cookie,csrf,body:{name:'Test Commander',title:'High Command',faction:'Republic',bio:'Test record',sort_order:4}});assert.equal(newLeader.status,201);
 assert.ok((await request(base,'/api/bootstrap')).data.high_command.some(x=>x.name==='Test Commander'));
 const anonymous=await request(base,'/api/status',{method:'POST',body:{display_name:'CT-8868 Tali',designation:'CT-8868',rank:'SSG',unit:'Clone X Trooper',status:'On Duty',note:'Training in VRChat',website:''}});assert.equal(anonymous.status,201);assert.ok(anonymous.data.editCode);
 assert.ok((await request(base,'/api/statuses')).data.statuses.some(s=>s.display_name==='CT-8868 Tali'));
 const changed=await request(base,`/api/status/${anonymous.data.id}`,{method:'PUT',body:{display_name:'Tali',designation:'CT-8868',rank:'SSG',unit:'Clone X Trooper',status:'Training',note:'At the academy',editCode:anonymous.data.editCode}});assert.equal(changed.status,200);
 assert.equal((await request(base,'/api/statuses')).data.statuses.find(s=>s.id===anonymous.data.id).status,'Training');
 assert.equal((await request(base,`/api/status/${anonymous.data.id}/remove`,{method:'POST',body:{editCode:'bad'}})).status,403);
 assert.equal((await request(base,`/api/status/${anonymous.data.id}/remove`,{method:'POST',body:{editCode:anonymous.data.editCode}})).status,200);
 assert.ok(!(await request(base,'/api/statuses')).data.statuses.some(s=>s.id===anonymous.data.id));
 assert.equal((await request(base,`/api/admin/high_command/${newLeader.data.id}`,{method:'DELETE',cookie,csrf})).status,200);
 assert.ok(!(await request(base,'/api/bootstrap')).data.high_command.some(s=>s.id===newLeader.data.id));
 const logout=await request(base,'/api/admin/logout',{method:'POST',cookie,csrf,body:{}});assert.equal(logout.status,200);
 assert.equal((await request(base,'/api/admin/dashboard',{cookie})).status,401);
});
