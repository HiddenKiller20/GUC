import './config.mjs';
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const OWNER_EMAIL = (process.env.OWNER_EMAIL || 'bigt1576@gmail.com').trim().toLowerCase();
const dbFile = resolve(process.env.DB_FILE || fileURLToPath(new URL('./data/guc.db', import.meta.url)));
mkdirSync(dirname(dbFile), { recursive: true });
export const db = new DatabaseSync(dbFile);
db.exec('PRAGMA journal_mode = WAL; PRAGMA foreign_keys = ON; PRAGMA busy_timeout = 5000;');

export const PAGE_COPY = {
  home_hero: ['Home: introduction', 'Two factions. One community. Countless battles. Join the Galactic Unification Corps and forge your legacy in Star Wars-inspired VRChat roleplay.'],
  home_about: ['Home: community overview', 'Republic and Empire operate under one community, each with a dedicated chain of command. Take part in patrols, operations, structured ranks, training and weekly events.'],
  about: ['About the Corps', 'The Galactic Unification Corps (GUC) is a Star Wars-themed VRChat roleplay community with two rival factions: the Galactic Republic and the Galactic Empire. Members can participate in military operations, large-scale events, story-driven campaigns, specialized units, social activities and community leadership.'],
  republic: ['Republic introduction', 'Honor. Courage. Justice. Defend the Republic alongside clone battalions, the Jedi Order and the Republic Navy. Train, deploy and rise through the ranks under the Republic chain of command.'],
  empire: ['Empire introduction', 'Discipline. Order. Strength. Serve within the Imperial military, specialized divisions and Imperial Navy. Complete operations, qualify for promotions and rise through the Empire’s chain of command.'],
  high_command: ['High Command introduction', 'Meet the people entrusted with leadership of the Galactic Unification Corps and its two factions. New appointments and roster updates are published by the owner.'],
  units: ['Units introduction', 'Explore the Corps’ battalions and specialized units. Each faction maintains its own organization, leadership and operations.'],
  ranks: ['Ranks introduction', 'Ranks and abbreviations are used for member statuses, promotions and chain-of-command organization. Exact promotion requirements are set by unit leadership.'],
  jedi: ['Jedi High Council introduction', 'The Jedi High Council oversees Jedi roleplay, training, trials and coordination with Republic leadership. Council membership is appointed by authorized GUC leadership.'],
  bounty: ['Bounty Guild introduction', 'The GUC Bounty Hunter Guild offers approved roleplay contracts, tier progression and Galactic Bounty Credits (GBC). Bounties, evidence and rewards must follow Guild rules and be confirmed by authorized staff.'],
  store: ['Reward Store introduction', 'Spend earned Galactic Bounty Credits on approved community rewards, from digital art to avatar work and a custom VRChat world. Availability and commission scope are confirmed by staff before redemption.'],
  events: ['Events introduction', 'Operations, battalion training, community games, campaigns and ceremonies appear here. All times should include a timezone.'],
  announcements: ['Announcements introduction', 'Official announcements from the owner and authorized group leadership.'],
  rules: ['Community rules', '1. Respect members and visitors. No harassment, hate speech or threats.\n2. Follow VRChat and Discord rules and applicable platform policies.\n3. Keep Republic and Empire roleplay in-character; avoid out-of-character hostility.\n4. Follow event hosts and the authorized chain of command during operations.\n5. No cheating, exploits, alt-account farming or fabricated bounty evidence.\n6. No unauthorized raids, doxxing, stalking or sharing private information.\n7. Obtain consent for personal interactions and follow world-specific RP boundaries.\n8. Report rule violations privately to moderators. Staff review evidence and may appeal decisions.'],
  join: ['Join introduction', 'You can browse this site and add your VRChat status without an account. To join the community or apply for a unit, open our Discord invite and follow the onboarding instructions.'],
  status: ['Status Board introduction', 'Post your VRChat name, rank or designation and on-duty status without creating an account. Save your private edit code if you want to update or remove your entry later. Posts are public; do not include private personal information.'],
  allies: ['Allies introduction', 'GUC allies and community partners may be listed here after approval by High Command.'],
  memorial: ['Memorial introduction', 'A place to honor members who have made a lasting contribution to our community. Memorial entries are added with respect and at the owner’s discretion.']
};

export const COLLECTIONS = {
  high_command: { fields: { name: 'text', title: 'text', faction: 'faction', bio: 'long', sort_order: 'number' } },
  units: { fields: { name: 'text', faction: 'faction', description: 'long', sort_order: 'number' } },
  ranks: { fields: { name: 'text', abbreviation: 'text', branch: 'text', faction: 'faction', sort_order: 'number' } },
  events: { fields: { title: 'text', faction: 'faction', starts_at: 'datetime', location: 'text', description: 'long' } },
  announcements: { fields: { title: 'text', faction: 'faction', body: 'long', pinned: 'boolean' } },
  rewards: { fields: { name: 'text', credits: 'number', description: 'long' } },
  guild_tiers: { fields: { tier: 'number', name: 'text', lifetime_credits: 'number', access: 'text' } },
  allies: { fields: { name: 'text', description: 'long', website: 'url' } }
};

export function initDb() {
 db.exec(`
 CREATE TABLE IF NOT EXISTS site_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY CHECK(id=1), email TEXT NOT NULL UNIQUE, salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, csrf_token TEXT NOT NULL, admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE, expires_at INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS site_content (key TEXT PRIMARY KEY, value TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS high_command (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, title TEXT NOT NULL, faction TEXT NOT NULL DEFAULT 'Both', bio TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, faction TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS ranks (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, abbreviation TEXT NOT NULL, branch TEXT NOT NULL, faction TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, faction TEXT NOT NULL, starts_at TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, faction TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')));
 CREATE TABLE IF NOT EXISTS rewards (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, credits INTEGER NOT NULL, description TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS guild_tiers (id INTEGER PRIMARY KEY AUTOINCREMENT, tier INTEGER NOT NULL, name TEXT NOT NULL, lifetime_credits INTEGER NOT NULL, access TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS allies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS statuses (id INTEGER PRIMARY KEY AUTOINCREMENT, display_name TEXT NOT NULL, designation TEXT NOT NULL DEFAULT '', rank TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', edit_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')));
 CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);
 CREATE INDEX IF NOT EXISTS idx_statuses_updated ON statuses(updated_at DESC);
 `);
 const ins = db.prepare('INSERT OR IGNORE INTO site_content(key,value) VALUES (?,?)');
 for(const [key, [,copy]] of Object.entries(PAGE_COPY)) ins.run(key, copy);
 if(db.prepare("SELECT value FROM site_meta WHERE key='initial_seeded'").get())return;
 if(db.prepare('SELECT COUNT(*) AS n FROM high_command').get().n===0) {
  db.prepare('INSERT INTO high_command(name,title,faction,bio,sort_order) VALUES (?,?,?,?,?)').run('Hidden_Killer20','Owner · Galactic Unification Corps','Both','Community owner and site administrator.',0);
 }
 const units = [
  ['Coruscant Guard','Republic','Republic security and protection unit.',1],
  ['501st Legion','Republic','Front-line clone trooper legion.',2],
  ['41st Elite Corps','Republic','Jungle and reconnaissance operations.',3],
  ['104th Battalion','Republic','Specialized clone battalion.',4],
  ['Grey Battalion','Republic','Custom GUC clone unit.',5],
  ['404th Misfit Battalion','Republic','Custom pink-themed battalion.',6],
  ['73rd Shadow Battalion','Republic','Specialized shadow operations.',7],
  ['Red Guard','Republic','Specialized ceremonial and protection roles.',8],
  ['Imperial Stormtrooper Corps','Empire','Imperial ground forces and patrols.',9],
  ['Imperial Navy','Empire','Imperial fleet and ship operations.',10],
  ['Imperial Security Bureau','Empire','Imperial intelligence and internal security RP.',11],
  ['Bounty Hunter Guild','Both','Approved bounties and Guild contracts.',12]
 ];
 if(db.prepare('SELECT COUNT(*) AS n FROM units').get().n===0) {
  const s=db.prepare('INSERT INTO units(name,faction,description,sort_order) VALUES (?,?,?,?)');for(const row of units)s.run(...row);
 }
 const ranks = [
  ['Recruit','RCT','Trooper','Both',1],['Private','PVT','Trooper','Both',2],['Private First Class','PFC','Trooper','Both',3],['Corporal','CPL','Trooper','Both',4],['Sergeant','SGT','Trooper','Both',5],['Staff Sergeant','SSG','Trooper','Both',6],['Sergeant Major','SGM','Trooper','Both',7],['Second Lieutenant','2LT','Officer','Both',8],['First Lieutenant','1LT','Officer','Both',9],['Captain','CPT','Officer','Both',10],['Major','MAJ','Officer','Both',11],['Commander','CDR','Command','Both',12],['General','GEN','Command','Both',13],['Jedi Padawan','JP','Jedi','Republic',14],['Jedi Knight','JK','Jedi','Republic',15],['Jedi Master','JM','Jedi','Republic',16]
 ];
 if(db.prepare('SELECT COUNT(*) AS n FROM ranks').get().n===0){const s=db.prepare('INSERT INTO ranks(name,abbreviation,branch,faction,sort_order) VALUES (?,?,?,?,?)');for(const row of ranks)s.run(...row);}
 const rewards=[['Nickname color (30 days)',1000000,'Subject to Discord role availability.'],['Bounty Hunter role',2500000,'Guild role, subject to qualification.'],['Custom bounty poster',5000000,'Digital poster with approved content.'],['Unit insignia',10000000,'Custom unit insignia concept.'],['Recruitment poster',12500000,'Custom recruitment artwork.'],['Avatar recolor commission',25000000,'Scope and files agreed with creator.'],['Basic custom VRChat avatar',50000000,'Commission subject to scope and creator availability.'],['Personal room in a GUC world',100000000,'World editor approval required.'],['Small custom VRChat map',125000000,'Scope agreed with creator.'],['Advanced custom VRChat map',175000000,'Scope agreed with creator.'],['Full custom VRChat world',250000000,'Highest reward; custom scope, timeline and creator approval required.']];
 if(db.prepare('SELECT COUNT(*) AS n FROM rewards').get().n===0){const s=db.prepare('INSERT INTO rewards(name,credits,description) VALUES (?,?,?)');for(const row of rewards)s.run(...row);}
 const tiers=[[1,'Initiate Hunter',0,'Class E'],[2,'Licensed Hunter',2500000,'Class D'],[3,'Tracker',10000000,'Class C'],[4,'Enforcer',25000000,'Class B'],[5,'Elite Hunter',50000000,'Class A'],[6,'Master Hunter',100000000,'Class S'],[7,'Guild Champion',175000000,'Legendary'],[8,'Apex Hunter',250000000,'Highest Guild status']];
 if(db.prepare('SELECT COUNT(*) AS n FROM guild_tiers').get().n===0){const s=db.prepare('INSERT INTO guild_tiers(tier,name,lifetime_credits,access) VALUES (?,?,?,?)');for(const row of tiers)s.run(...row);}
 db.prepare("INSERT INTO site_meta(key,value) VALUES('initial_seeded','1')").run();
}

export function publicData() {
 const content=Object.fromEntries(db.prepare('SELECT key,value FROM site_content').all().map(r=>[r.key,r.value]));
 const data={content};
 for(const collection of Object.keys(COLLECTIONS)) {
  const order=collection==='events'?'starts_at ASC':collection==='announcements'?'pinned DESC, created_at DESC':collection==='rewards'?'credits ASC':collection==='guild_tiers'?'tier ASC':collection==='allies'?'id ASC':'sort_order ASC, id ASC';
  data[collection]=db.prepare(`SELECT * FROM ${collection} ORDER BY ${order}`).all();
 }
 data.statuses=db.prepare('SELECT id,display_name,designation,rank,unit,status,note,created_at,updated_at FROM statuses ORDER BY updated_at DESC LIMIT 200').all();
 return data;
}
