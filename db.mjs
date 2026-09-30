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
  roles: ['Discord roles introduction', 'The official GUC role directory mirrors the command, faction, unit, rank, specialist, staff and community roles used in the Discord structure.'],
  discord: ['Discord structure introduction', 'Browse the GUC Discord category and channel structure from Server Information through faction command, units, operations and training.'],
  training: ['Training introduction', 'Training certifications mirror the qualifications listed in the GUC Discord academy structure.'],
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
  discord_roles: { fields: { name: 'text', category: 'text', faction: 'faction', description: 'long', sort_order: 'number' } },
  discord_channels: { fields: { name: 'text', category: 'text', channel_type: 'text', faction: 'faction', sort_order: 'number' } },
  certifications: { fields: { name: 'text', faction: 'faction', description: 'long', sort_order: 'number' } },
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
 CREATE TABLE IF NOT EXISTS discord_roles (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL, faction TEXT NOT NULL DEFAULT 'Both', description TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS discord_channels (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL, channel_type TEXT NOT NULL DEFAULT 'Text', faction TEXT NOT NULL DEFAULT 'Both', sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS certifications (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, faction TEXT NOT NULL DEFAULT 'Both', description TEXT NOT NULL DEFAULT '', sort_order INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS allies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS statuses (id INTEGER PRIMARY KEY AUTOINCREMENT, display_name TEXT NOT NULL, designation TEXT NOT NULL DEFAULT '', rank TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', edit_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')));
 CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_at);
 CREATE INDEX IF NOT EXISTS idx_statuses_updated ON statuses(updated_at DESC);
 `);
 const ins = db.prepare('INSERT OR IGNORE INTO site_content(key,value) VALUES (?,?)');
 for(const [key, [,copy]] of Object.entries(PAGE_COPY)) ins.run(key, copy);

 // Mirror the saved GUC Discord structure into the public website.
 if(!db.prepare("SELECT value FROM site_meta WHERE key='discord_mirror_v1'").get()) {
  db.exec('BEGIN');
  try {
   db.prepare("DELETE FROM units").run();
   db.prepare("DELETE FROM ranks").run();
   db.prepare("DELETE FROM discord_roles").run();
   db.prepare("DELETE FROM discord_channels").run();
   db.prepare("DELETE FROM certifications").run();
   db.prepare("DELETE FROM guild_tiers").run();
   db.prepare("DELETE FROM rewards WHERE name IN ('Bounty Hunter role','Custom bounty poster')").run();

   const unitGroups = [
    ['Republic','Republic Army Unit / Battalion',['501st Legion','212th Attack Battalion','187th Battalion','41st Elite Corps','Coruscant Guard','327th Star Corps','91st Recon Corps','21st Nova Corps','104th Battalion','442nd Siege Battalion','7th Sky Corps','13th Battalion','332nd Company','Green Company','Grey Battalion']],
    ['Republic','Specialized Republic Formation',['ARC Troopers','Republic Commandos','Clone Commandos','Advanced Recon Force (ARF)','Clone Scouts','Clone Pilots','Clone Engineers','Clone Medics','Clone Heavy Troopers','Clone Sharpshooters','Clone Naval Personnel','Republic Intelligence','Republic Special Operations','Republic Military Police','Senate Guard','Senate Commandos','Red Guard','Republic Navy','Jedi Order']],
    ['Empire','Imperial Army / Stormtrooper Formation',['Stormtrooper Corps',"501st Legion / Vader's Fist",'1st Legion','Coruscant Guard','Imperial Army','Imperial Army Troopers','Imperial Special Forces','Imperial Commandos','Scout Troopers','Heavy Stormtroopers','Shock Troopers','Incinerator Troopers','Mortar Troopers','Patrol Troopers','Range Troopers','Shoretroopers','Snowtroopers','Sandtroopers','Magma Troopers','Swamp Troopers','Jump Troopers','Jet Troopers','Spacetroopers','Death Troopers','Shadow Troopers','Dark Troopers','Purge Troopers','Imperial Pilots','TIE Pilots','AT-AT Crews','AT-ST Crews','Imperial Engineers','Imperial Medics']],
    ['Empire','Imperial Security Organization',['Imperial Security Bureau (ISB)','Imperial Intelligence','Imperial Security','Imperial Special Forces','Death Troopers','Imperial Royal Guard','Imperial Honor Guard','CompForce','Naval Intelligence','Imperial Navy','Sith / Dark Side','Inquisitorius']]
   ];
   const unitIns=db.prepare('INSERT INTO units(name,faction,description,sort_order) VALUES (?,?,?,?)');
   let unitOrder=1;
   for(const [faction,kind,names] of unitGroups) for(const name of names) unitIns.run(name,faction,kind,unitOrder++);

   const rankGroups = [
    ['Republic','Clone Enlisted',[['CT — Clone Trooper','CT'],['CT PFC — Private First Class','CT PFC'],['CL — Lance Corporal','CL'],['CP — Corporal','CP'],['CS — Sergeant','CS'],['CSM — Sergeant Major','CSM']]],
    ['Republic','Clone Officers',[['Second Lieutenant',''],['First Lieutenant',''],['Captain',''],['Major',''],['Battalion Commander',''],['Regimental Commander',''],['Senior Commander',''],['Marshal Commander','']]],
    ['Republic','ARC',[['ARC Trooper',''],['ARC Sergeant',''],['ARC Lieutenant',''],['ARC Captain',''],['ARC Commander','']]],
    ['Republic','Commando',[['Commando',''],['Commando Sergeant',''],['Commando Captain',''],['Commando Commander','']]],
    ['Republic','Pilot',[['Pilot',''],['Senior Pilot',''],['Flight Lieutenant',''],['Flight Captain',''],['Flight Commander','']]],
    ['Republic','Republic Navy',[['Crewman',''],['Petty Officer',''],['Chief Petty Officer',''],['Ensign',''],['Lieutenant',''],['Lieutenant Commander',''],['Commander',''],['Captain',''],['Commodore',''],['Rear Admiral',''],['Vice Admiral',''],['Admiral',''],['Fleet Admiral','']]],
    ['Republic','Jedi Order',[['Jedi Initiate',''],['Jedi Youngling',''],['Jedi Padawan',''],['Jedi Knight',''],['Jedi General',''],['Jedi Master',''],['Jedi Council Member',''],['Master of the Order',''],['Grand Master','']]],
    ['Empire','Imperial Army / Stormtrooper',[['Recruit',''],['Private',''],['Private First Class',''],['Lance Corporal',''],['Corporal',''],['Sergeant',''],['Staff Sergeant',''],['Sergeant Major',''],['Second Lieutenant',''],['First Lieutenant',''],['Captain',''],['Major',''],['Lieutenant Colonel',''],['Colonel',''],['Commander',''],['Senior Commander',''],['General',''],['High General','']]],
    ['Empire','Imperial Navy',[['Crewman',''],['Petty Officer',''],['Chief Petty Officer',''],['Ensign',''],['Sub-Lieutenant',''],['Lieutenant',''],['Lieutenant Commander',''],['Commander',''],['Captain',''],['Commodore',''],['Rear Admiral',''],['Vice Admiral',''],['Admiral',''],['Fleet Admiral',''],['Grand Admiral','']]],
    ['Empire','Dark Side',[['Force Initiate',''],['Acolyte',''],['Apprentice',''],['Dark Jedi',''],['Inquisitor',''],['Sith Apprentice',''],['Sith Lord',''],['Dark Lord',''],['Sith Master','']]]
   ];
   const rankIns=db.prepare('INSERT INTO ranks(name,abbreviation,branch,faction,sort_order) VALUES (?,?,?,?,?)');
   let rankOrder=1;
   for(const [faction,branch,rows] of rankGroups) for(const [name,abbr] of rows) rankIns.run(name,abbr,branch,faction,rankOrder++);

   const roleGroups = [
    ['GUC / Community','Both',['👑 Server Owner','⚜️ GUC Founder','⭐ GUC High Command','🛡️ Server Administration','🔨 Moderator','HighCom Council','Community Command','Event Director','Instructor','Event Staff','Lore Team','Media Team','Allied Representative','Veteran','Member','Recruit']],
    ['Republic Command','Republic',['Republic High Command','Republic Command','Jedi High Command','Republic Navy Command','Battalion Commanders','Republic Officers','Republic NCOs','Republic Enlisted']],
    ['Republic Unit Roles','Republic',['501st Legion','212th Attack Battalion','187th Battalion','41st Elite Corps','Coruscant Guard','327th Star Corps','91st Recon Corps','21st Nova Corps','104th Battalion','442nd Siege Battalion','7th Sky Corps','13th Battalion','332nd Company','Green Company','Grey Battalion']],
    ['Republic Specializations','Republic',['ARC Troopers','Republic Commandos','Clone Commandos','Advanced Recon Force (ARF)','Clone Scouts','Clone Pilots','Clone Engineers','Clone Medics','Clone Heavy Troopers','Clone Sharpshooters','Clone Naval Personnel','Republic Intelligence','Republic Special Operations','Republic Military Police','Senate Guard','Senate Commandos','Red Guard']],
    ['Republic Rank Roles','Republic',['CT — Clone Trooper','CT PFC — Private First Class','CL — Lance Corporal','CP — Corporal','CS — Sergeant','CSM — Sergeant Major','Second Lieutenant','First Lieutenant','Captain','Major','Battalion Commander','Regimental Commander','Senior Commander','Marshal Commander','ARC Trooper','ARC Sergeant','ARC Lieutenant','ARC Captain','ARC Commander','Commando','Commando Sergeant','Commando Captain','Commando Commander','Pilot','Senior Pilot','Flight Lieutenant','Flight Captain','Flight Commander']],
    ['Republic Navy Roles','Republic',['Crewman','Petty Officer','Chief Petty Officer','Ensign','Lieutenant','Lieutenant Commander','Commander','Captain','Commodore','Rear Admiral','Vice Admiral','Admiral','Fleet Admiral']],
    ['Jedi Roles','Republic',['Jedi Initiate','Jedi Youngling','Jedi Padawan','Jedi Knight','Jedi General','Jedi Master','Jedi Council Member','Master of the Order','Grand Master']],
    ['Imperial Command','Empire',['Imperial High Command','Imperial Command','Sith Command','Imperial Navy Command','Legion Commanders','Imperial Officers','Imperial NCOs','Imperial Enlisted']],
    ['Imperial Unit Roles','Empire',['Stormtrooper Corps',"501st Legion / Vader's Fist",'1st Legion','Coruscant Guard','Imperial Army','Imperial Army Troopers','Imperial Special Forces','Imperial Commandos','Scout Troopers','Heavy Stormtroopers','Shock Troopers','Incinerator Troopers','Mortar Troopers','Patrol Troopers','Range Troopers','Shoretroopers','Snowtroopers','Sandtroopers','Magma Troopers','Swamp Troopers','Jump Troopers','Jet Troopers','Spacetroopers','Death Troopers','Shadow Troopers','Dark Troopers','Purge Troopers','Imperial Pilots','TIE Pilots','AT-AT Crews','AT-ST Crews','Imperial Engineers','Imperial Medics']],
    ['Imperial Security Roles','Empire',['Imperial Security Bureau (ISB)','Imperial Intelligence','Imperial Security','Imperial Special Forces','Death Troopers','Imperial Royal Guard','Imperial Honor Guard','CompForce','Naval Intelligence']],
    ['Imperial Rank Roles','Empire',['Recruit','Private','Private First Class','Lance Corporal','Corporal','Sergeant','Staff Sergeant','Sergeant Major','Second Lieutenant','First Lieutenant','Captain','Major','Lieutenant Colonel','Colonel','Commander','Senior Commander','General','High General']],
    ['Imperial Navy Roles','Empire',['Crewman','Petty Officer','Chief Petty Officer','Ensign','Sub-Lieutenant','Lieutenant','Lieutenant Commander','Commander','Captain','Commodore','Rear Admiral','Vice Admiral','Admiral','Fleet Admiral','Grand Admiral']],
    ['Dark Side Roles','Empire',['Force Initiate','Acolyte','Apprentice','Dark Jedi','Inquisitor','Sith Apprentice','Sith Lord','Dark Lord','Sith Master']]
   ];
   const roleIns=db.prepare('INSERT INTO discord_roles(name,category,faction,description,sort_order) VALUES (?,?,?,?,?)');
   let roleOrder=1;
   for(const [category,faction,names] of roleGroups) for(const name of names) roleIns.run(name,category,faction,'Mirrored from the GUC Discord role structure.',roleOrder++);

   const channelGroups = [
    ['Server Information','Both','Text',['📌start-here','📜・server-rules','・guc-handbook','・announcements','🗓️event-schedule','🎖️rank-structure','・unit-directory','・punishment-codex','❓・faq','・support-tickets','・alliances']],
    ['Community','Both','Text',['・general','・introductions','・screenshots','・clips-and-media','・art-and-creations','・bot-commands','・suggestions','😂memes','・other-games']],
    ['Community','Both','Voice',['🔊 General VC','🔊 Gaming VC','🔊 AFK']],
    ['GUC High Command','Both','Text',['・highcom-announcements','📋highcom-orders','💬highcom-chat','・command-reports','・personnel-records','⚖️disciplinary-reports','🎖️promotions','・demotions','・loa-reports','🗺️operation-planning','🤝diplomatic-command']],
    ['GUC High Command','Both','Voice',['🔊 High Command','🔊 Command Meeting','🔊 Private Briefing']],
    ['Republic Command','Republic','Text',['・republic-announcements','📜republic-orders','💬republic-chat','📋republic-reports','🎖️republic-promotions','🗺️republic-operations','・republic-training','🪖republic-recruitment']],
    ['Republic Command','Republic','Voice',['🔊 Republic Command','🔊 Republic Briefing','🔊 Republic Operations']],
    ['Battalion Template','Republic','Text',['📢unit-announcements','💬unit-chat','📋unit-orders','🎖️unit-promotions','📊unit-reports','📚unit-training','📝unit-roster']],
    ['Battalion Template','Republic','Voice',['🔊 Unit Briefing','🔊 Unit Operations','🔊 Unit Patrol']],
    ['Coruscant Guard','Republic','Text',['・cg-announcements','📜cg-orders','・cg-punishment-codex','・arrest-reports','⚖️case-reports','・detainment-records','📋patrol-reports','🛡️security-reports','🎖️cg-promotions','📚cg-training','💬cg-chat']],
    ['Coruscant Guard','Republic','Voice',['🔊 CG Headquarters','🔊 Patrol','🔊 Security Detail','🔊 Detention Center','🔊 CG Command']],
    ['Republic Navy','Republic','Text',['⚓ navy-announcements','💬navy-chat','・fleet-operations','🛰️ship-assignments','✈️pilot-corps','📋naval-reports']],
    ['Republic Navy','Republic','Voice',['🔊 Fleet Command','🔊 Bridge','🔊 Flight Operations']],
    ['Jedi Order','Republic','Text',['・jedi-announcements','💬jedi-temple','📚jedi-archives','⚔️combat-training','・force-training','📜jedi-assignments','🪖general-assignments','🏛️jedi-council']],
    ['Jedi Order','Republic','Voice',['🔊 Jedi Temple','🔊 Training Chamber','🔊 Council Chamber']],
    ['Imperial Command','Empire','Text',['🔴imperial-announcements','📜imperial-orders','💬imperial-chat','📋imperial-reports','🎖️imperial-promotions','🗺️imperial-operations','📚imperial-training','🪖imperial-recruitment']],
    ['Imperial Command','Empire','Voice',['🔊 Imperial Command','🔊 Imperial Briefing','🔊 Imperial Operations']],
    ['Imperial Security & Intelligence','Empire','Text',['🔒classified','📋intelligence-reports','👁️surveillance','・wanted-persons','📁case-files','⚠️security-alerts']],
    ['Imperial Security & Intelligence','Empire','Voice',['🔊 Intelligence Command','🔊 Secure Communications']],
    ['Sith / Dark Side','Empire','Text',['・sith-orders','💬sith-chambers','📚sith-archives','⚔️combat-training','🔴inquisitorius','👑sith-command']],
    ['Sith / Dark Side','Empire','Voice',['🔊 Sith Chamber','🔊 Inquisitorius','🔊 Private Council']],
    ['Operations Center','Both','Text',['📢operation-announcements','🗺️mission-briefings','📋operation-orders','🎯objectives','📊after-action-reports','・commendations']],
    ['Operations Center','Both','Voice',['🔊 Operation Command','🔊 Republic Operations','🔊 Imperial Operations','🔊 Republic Squad 1','🔊 Republic Squad 2','🔊 Imperial Squad 1','🔊 Imperial Squad 2']],
    ['Training Academy','Both','Text',['📚training-information','📝training-requests','・certifications','🪖basic-training','・weapons-training','🚨security-training','🛩️pilot-training','🎖️officer-academy']],
    ['Training Academy','Both','Voice',['🔊 Classroom','🔊 Training Grounds','🔊 Officer Academy']]
   ];
   const chanIns=db.prepare('INSERT INTO discord_channels(name,category,channel_type,faction,sort_order) VALUES (?,?,?,?,?)');
   let chanOrder=1;
   for(const [category,faction,type,names] of channelGroups) for(const name of names) chanIns.run(name,category,type,faction,chanOrder++);

   const certs=['Basic Training','Advanced Combat','Heavy Weapons','Marksman','Medic','Engineer','Pilot','Vehicle','Security','Leadership','Officer','Instructor','ARC','Commando','Special Operations'];
   const certIns=db.prepare('INSERT INTO certifications(name,faction,description,sort_order) VALUES (?,?,?,?)');
   let certOrder=1; for(const name of certs) certIns.run(name,'Both','Training Academy certification.',certOrder++);

   const discordRules = [
    '1. Respect all members. Harassment, discrimination, targeted hostility, or hate speech is prohibited.',
    "2. Follow Discord's Terms of Service and Community Guidelines.",
    '3. Keep roleplay conflict inside roleplay. Republic vs. Empire rivalry does not justify attacking players personally.',
    '4. Follow the Chain of Command while participating in official roleplay.',
    '5. Do not abuse rank or authority.',
    '6. No impersonating staff, High Command, or another member.',
    '7. No NSFW or sexually explicit content.',
    '8. No spam, malicious links, scams, or disruptive behavior.',
    '9. Use channels for their intended purposes.',
    '10. Do not leak restricted faction or High Command information.',
    '11. Follow event-host instructions during official operations.',
    '12. Do not intentionally sabotage official events.',
    '13. Report staff or command misconduct through the appropriate reporting system.',
    '14. Retaliation against members who make good-faith reports is prohibited.',
    '15. Staff decisions may be appealed through the designated appeal system.'
   ].join('\n');
   db.prepare("INSERT INTO site_content(key,value) VALUES('rules',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run(discordRules);
   db.prepare("INSERT INTO site_content(key,value) VALUES('roles',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run('A complete website directory of the leadership, faction, battalion, rank, specialist, staff and community roles mirrored from the GUC Discord structure.');
   db.prepare("INSERT INTO site_content(key,value) VALUES('discord',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run('The website mirrors the GUC Discord server layout, including information, community, High Command, faction command, active unit templates, operations and training channels.');
   db.prepare("INSERT INTO site_content(key,value) VALUES('training',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value").run('Training Academy qualifications and certifications used across the GUC community.');
   db.prepare("INSERT INTO site_meta(key,value) VALUES('discord_mirror_v1','1')").run();
   db.exec('COMMIT');
  } catch(error) {
   db.exec('ROLLBACK');
   throw error;
  }
 }
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
 const rewards=[['Nickname color (30 days)',1000000,'Subject to Discord role availability.'],['Unit insignia',10000000,'Custom unit insignia concept.'],['Recruitment poster',12500000,'Custom recruitment artwork.'],['Avatar recolor commission',25000000,'Scope and files agreed with creator.'],['Basic custom VRChat avatar',50000000,'Commission subject to scope and creator availability.'],['Personal room in a GUC world',100000000,'World editor approval required.'],['Small custom VRChat map',125000000,'Scope agreed with creator.'],['Advanced custom VRChat map',175000000,'Scope agreed with creator.'],['Full custom VRChat world',250000000,'Highest reward; custom scope, timeline and creator approval required.']];
 if(db.prepare('SELECT COUNT(*) AS n FROM rewards').get().n===0){const s=db.prepare('INSERT INTO rewards(name,credits,description) VALUES (?,?,?)');for(const row of rewards)s.run(...row);}
 db.prepare("INSERT INTO site_meta(key,value) VALUES('initial_seeded','1')").run();
}

export function publicData() {
 const content=Object.fromEntries(db.prepare('SELECT key,value FROM site_content').all().map(r=>[r.key,r.value]));
 const data={content};
 for(const collection of Object.keys(COLLECTIONS)) {
  const order=collection==='events'?'starts_at ASC':collection==='announcements'?'pinned DESC, created_at DESC':collection==='rewards'?'credits ASC':collection==='allies'?'id ASC':'sort_order ASC, id ASC';
  data[collection]=db.prepare(`SELECT * FROM ${collection} ORDER BY ${order}`).all();
 }
 data.statuses=db.prepare('SELECT id,display_name,designation,rank,unit,status,note,created_at,updated_at FROM statuses ORDER BY updated_at DESC LIMIT 200').all();
 return data;
}
