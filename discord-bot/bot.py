"""GUC command bot. Python 3.11+. Single process / single server."""
import asyncio
import json
import logging
import os
import sqlite3
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
BASE = Path(__file__).parent
CONFIG = json.loads((BASE / 'config.json').read_text())
DATA = Path(os.getenv('DATA_DIR', str(BASE / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
db = sqlite3.connect(DATA / 'guc.sqlite3')
db.executescript('''
CREATE TABLE IF NOT EXISTS bindings (key TEXT PRIMARY KEY, role_id INTEGER UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS certs (user_id INTEGER, key TEXT, issuer INTEGER, reason TEXT,
 issued TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,key));
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, actor INTEGER, target INTEGER,
 action TEXT, detail TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY, user_id INTEGER,
 faction TEXT, text TEXT, status TEXT DEFAULT 'pending', reviewer INTEGER,
 created TEXT DEFAULT CURRENT_TIMESTAMP);
''')
lock = asyncio.Lock()
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID', '0'))

def audit(actor, target, action, detail):
    with db:
        db.execute('INSERT INTO audit(actor,target,action,detail) VALUES(?,?,?,?)',
                   (actor, target, action, detail))

def owner(i):
    return i.user.id == i.guild.owner_id

def staff(i):
    allowed = set(CONFIG['staff_role_ids'])
    if not (owner(i) or (i.user.guild_permissions.manage_roles and
                        any(str(r.id) in allowed for r in i.user.roles))):
        raise ValueError('Requires a configured staff role and Manage Roles permission (or server owner).')

def check_target(i, member):
    if member.bot or member.id == i.guild.owner_id:
        raise ValueError('Bot accounts and the server owner are protected.')
    if member.id == i.user.id:
        raise ValueError('Ask another authorized staff member to change your roles.')
    if not owner(i) and member.top_role >= i.user.top_role:
        raise ValueError('You can only manage members below your highest role.')
    if member.top_role >= i.guild.me.top_role:
        raise ValueError('Move the bot role above this member’s roles first.')

def check_role(i, role):
    if role is None or role.is_default() or role.managed:
        raise ValueError('Role is missing, managed by Discord, or is @everyone.')
    if role.permissions.value != 0:
        raise ValueError('Only roles with zero server permissions may be managed by this bot.')
    if str(role.id) in CONFIG['staff_role_ids']:
        raise ValueError('Staff access roles are protected.')
    if role >= i.guild.me.top_role:
        raise ValueError('Move the bot role above the selected role.')
    if not owner(i) and role >= i.user.top_role:
        raise ValueError('You cannot assign or remove a role at or above your highest role.')

def role_for(i, key):
    if key not in CONFIG['roles']:
        raise ValueError('Unknown role key. Use /catalog.')
    row = db.execute('SELECT role_id FROM bindings WHERE key=?', (key,)).fetchone()
    if not row:
        raise ValueError('Role has not been bound. Ask the owner to use /bind.')
    role = i.guild.get_role(row[0])
    check_role(i, role)
    return role

class Tree(app_commands.CommandTree):
    async def interaction_check(self, i):
        return i.guild is not None and i.guild.id == GUILD_ID

class Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.tree = Tree(self)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

bot = Bot()

@bot.tree.error
async def on_error(i, error):
    original = getattr(error, 'original', error)
    if isinstance(original, ValueError):
        message = str(original)
    elif isinstance(original, discord.HTTPException):
        message = 'Discord rejected the request. Check bot permissions and role order, then retry. A multi-role change may be partial; check /profile.'
    else:
        logging.exception('Command failure', exc_info=original)
        message = 'The command failed. Ask the host administrator to check the logs.'
    if i.response.is_done():
        await i.followup.send(message, ephemeral=True)
    else:
        await i.response.send_message(message, ephemeral=True)

@bot.tree.command(description='Show GUC bot commands')
async def help(i: discord.Interaction):
    await i.response.send_message(
        '**The Galactic Unification Corps**\n'
        'Members: `/menu`, `/enlist`, `/startcombat`, `/stopcombat`, `/startonduty`, `/stoponduty`, `/status create`, `/rules`\n'
        'Staff: `/assign`, `/revoke`, `/applications`, `/review`, `/announce`\n'
        'Server owner: `/bind`\n'
        'Ranks use /rankup and approval checks. Battalion assignment replaces the previous battalion. '
        'Certifications can be stacked. No self-issued roles or certifications.', ephemeral=True)

@bot.tree.command(description='List configured rank, battalion and certification keys')
async def catalog(i: discord.Interaction):
    lines = [f"{k}: {v['name']} ({v['kind']}, {v['faction']})" for k, v in CONFIG['roles'].items()]
    import io
    await i.response.send_message(file=discord.File(io.BytesIO('\n'.join(lines).encode()), 'GUC_roles.txt'), ephemeral=True)

async def keys(i: discord.Interaction, current: str):
    return [app_commands.Choice(name=v['name'][:100], value=k)
            for k,v in CONFIG['roles'].items() if current.lower() in (k+' '+v['name']).lower()][:25]

@bot.tree.command(description='Owner: connect a catalog key to an existing Discord role')
@app_commands.autocomplete(key=keys)
async def bind(i: discord.Interaction, key: str, role: discord.Role):
    if not owner(i):
        raise ValueError('Only the server owner can bind roles.')
    if key not in CONFIG['roles']:
        raise ValueError('Unknown key. Use /catalog.')
    check_role(i, role)
    async with lock:
        old = db.execute('SELECT role_id FROM bindings WHERE key=?', (key,)).fetchone()
        if old and old[0] != role.id:
            raise ValueError('This key is already bound. Rebinding requires a deliberate database migration; see README.')
        other = db.execute('SELECT key FROM bindings WHERE role_id=?', (role.id,)).fetchone()
        if other and other[0] != key:
            raise ValueError('This Discord role is already bound to another key.')
        with db:
            db.execute('INSERT OR IGNORE INTO bindings VALUES(?,?)', (key, role.id))
        audit(i.user.id, role.id, 'bind', key)
    await i.response.send_message(f'Bound `{key}` to {role.name}.', ephemeral=True)

@bot.tree.command(description='Staff: assign a battalion, certification or non-rank role')
@app_commands.autocomplete(key=keys)
async def assign(i: discord.Interaction, member: discord.Member, key: str, reason: app_commands.Range[str, 3, 400]):
    staff(i)
    await i.response.defer(ephemeral=True)
    async with lock:
        member = await i.guild.fetch_member(member.id)
        check_target(i, member)
        if key.startswith('__up_'):
            key = next_rank(member, key[5:], 1)
        elif key.startswith('__down_'):
            key = next_rank(member, key[7:], -1)
        role = role_for(i, key)
        spec = CONFIG['roles'][key]
        if spec['kind'] == 'rank':
            raise ValueError('Rank changes require /rankup and the promotion approval workflow. Initial roles must be registered by the owner.')
        removals = []
        if spec['kind'] in ('rank', 'battalion'):
            for other, info in CONFIG['roles'].items():
                if other != key and (info['kind'],info['faction']) == (spec['kind'],spec['faction']):
                    row = db.execute('SELECT role_id FROM bindings WHERE key=?',(other,)).fetchone()
                    old = i.guild.get_role(row[0]) if row else None
                    if old in member.roles:
                        check_role(i, old)
                        removals.append(old)
        detail = f'{key}: {reason}'
        audit(i.user.id, member.id, 'assign_requested', detail)
        # Add first: a failed grant never strips the member's existing rank.
        await member.add_roles(role, reason=f'GUC staff {i.user.id}: {reason}')
        if removals:
            await member.remove_roles(*removals, reason=f'GUC replacement by {i.user.id}')
        if spec['kind'] == 'cert':
            with db:
                db.execute('INSERT INTO certs(user_id,key,issuer,reason) VALUES(?,?,?,?) '
                           'ON CONFLICT(user_id,key) DO UPDATE SET issuer=excluded.issuer,reason=excluded.reason,issued=CURRENT_TIMESTAMP',
                           (member.id,key,i.user.id,reason))
        audit(i.user.id, member.id, 'assign_completed', detail)
    await i.followup.send(f'Assigned **{role.name}** to {member.display_name}.', ephemeral=True)

@bot.tree.command(description='Staff: revoke a catalog role or certification')
@app_commands.autocomplete(key=keys)
async def revoke(i: discord.Interaction, member: discord.Member, key: str, reason: app_commands.Range[str, 3, 400]):
    staff(i)
    await i.response.defer(ephemeral=True)
    async with lock:
        member = await i.guild.fetch_member(member.id)
        check_target(i, member)
        role = role_for(i, key)
        if CONFIG['roles'][key]['kind'] == 'rank':
            raise ValueError('Rank removal is restricted. The owner must change the role in Discord and reconcile with /rank_register.')
        audit(i.user.id, member.id, 'revoke_requested', f'{key}: {reason}')
        await member.remove_roles(role, reason=f'GUC staff {i.user.id}: {reason}')
        with db:
            db.execute('DELETE FROM certs WHERE user_id=? AND key=?', (member.id,key))
        audit(i.user.id, member.id, 'revoke_completed', f'{key}: {reason}')
    await i.followup.send(f'Revoked **{role.name}** from {member.display_name}.', ephemeral=True)

@bot.tree.command(description='View your GUC roles and certification records; staff may inspect others')
async def profile(i: discord.Interaction, member: discord.Member | None = None):
    member = member or i.user
    if member.id != i.user.id:
        staff(i)
    await i.response.defer(ephemeral=True)
    member = await i.guild.fetch_member(member.id)
    import io
    lines = [f'GUC personnel record: {member.display_name} ({member.id})', '', 'Current catalog roles:']
    for key, rid in db.execute('SELECT key,role_id FROM bindings'):
        if any(r.id == rid for r in member.roles):
            lines.append(key)
    lines += ['', 'Certification records (role presence shown separately):']
    for key, issuer, reason, issued in db.execute('SELECT key,issuer,reason,issued FROM certs WHERE user_id=?',(member.id,)):
        row = db.execute('SELECT role_id FROM bindings WHERE key=?',(key,)).fetchone()
        present = row is not None and any(r.id == row[0] for r in member.roles)
        lines.append(f'{key} | Issuer {issuer} | {issued} UTC | Role present: {present} | {reason}')
    await i.followup.send(file=discord.File(io.BytesIO('\n'.join(lines).encode()),'GUC_profile.txt'), ephemeral=True)

@bot.tree.command(description='Submit a Republic or Empire membership application')
@app_commands.choices(faction=[app_commands.Choice(name='Galactic Republic',value='Republic'),app_commands.Choice(name='Galactic Empire',value='Empire')])
async def apply(i: discord.Interaction, faction: str, statement: app_commands.Range[str, 20, 1500]):
    if db.execute("SELECT 1 FROM applications WHERE user_id=? AND status='pending'",(i.user.id,)).fetchone():
        raise ValueError('You already have a pending application.')
    with db:
        cur = db.execute('INSERT INTO applications(user_id,faction,text) VALUES(?,?,?)',(i.user.id,faction,statement))
    await i.response.send_message(f'Application #{cur.lastrowid} saved for staff review. Do not include private real-world information.',ephemeral=True)

@bot.tree.command(description='Staff: view up to 20 pending applications')
async def applications(i: discord.Interaction):
    staff(i)
    import io
    rows = db.execute("SELECT id,user_id,faction,text FROM applications WHERE status='pending' ORDER BY id LIMIT 20").fetchall()
    body = '\n\n'.join(f'#{r[0]} | User {r[1]} | {r[2]}\n{r[3]}' for r in rows) or 'No pending applications.'
    await i.response.send_message(file=discord.File(io.BytesIO(body.encode()),'applications.txt'),ephemeral=True)

@bot.tree.command(description='Staff: record application decision (does not automatically grant roles)')
@app_commands.choices(decision=[app_commands.Choice(name='Approve',value='approved'),app_commands.Choice(name='Deny',value='denied')])
async def review(i: discord.Interaction, application_id: int, decision: str, reason: app_commands.Range[str,3,400]):
    staff(i)
    row = db.execute("SELECT user_id FROM applications WHERE id=? AND status='pending'",(application_id,)).fetchone()
    if not row:
        raise ValueError('No pending application with that ID.')
    if row[0] == i.user.id:
        raise ValueError('You cannot review your own application.')
    with db:
        db.execute('UPDATE applications SET status=?,reviewer=? WHERE id=?',(decision,i.user.id,application_id))
    audit(i.user.id,row[0],f'application_{decision}',f'#{application_id}: {reason}')
    await i.response.send_message(f'Application #{application_id}: {decision}. Use /assign separately for roles.',ephemeral=True)

@bot.tree.command(description='Staff: post a GUC event or duty announcement')
async def announce(i: discord.Interaction, channel: discord.TextChannel, title: app_commands.Range[str,1,200], message: app_commands.Range[str,1,1800]):
    staff(i)
    if not channel.permissions_for(i.user).send_messages or not channel.permissions_for(i.user).view_channel:
        raise ValueError('You must be able to view and send in that channel yourself.')
    await i.response.defer(ephemeral=True)
    await channel.send(embed=discord.Embed(title=title,description=message,color=0x2459a6).set_footer(text='The Galactic Unification Corps'))
    audit(i.user.id,channel.id,'announcement',title)
    await i.followup.send('Announcement posted.',ephemeral=True)

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return
    cid = int(CONFIG.get('welcome_channel_id') or 0)
    channel = member.guild.get_channel(cid)
    if channel:
        try:
            await channel.send(f'Welcome to The Galactic Unification Corps, {discord.utils.escape_markdown(member.display_name)}! '
                               'Republic: Honor. Courage. Justice. Empire: Discipline. Order. Strength. '
                               'Use /apply to enlist and /help for commands.')
        except discord.HTTPException:
            logging.warning('Could not post welcome message.')

# Additional command suite
from datetime import timedelta

db.executescript('''
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS tickets(user_id INTEGER PRIMARY KEY,channel_id INTEGER UNIQUE);
''')
for k,v in db.execute('SELECT key,value FROM settings'):
    CONFIG[k] = json.loads(v)

def setting(key,value):
    with db:
        db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(value)))
    CONFIG[key]=value

@bot.tree.command(description='Owner: easy setup with actual Discord roles and channels')
async def setup(i: discord.Interaction, staff_role: discord.Role, welcome_channel: discord.TextChannel, ticket_category: discord.CategoryChannel):
    if not owner(i):
        raise ValueError('Only the server owner can configure the bot.')
    if staff_role.is_default() or staff_role.managed:
        raise ValueError('Choose a dedicated staff role, not @everyone or a managed role.')
    if not staff_role.permissions.manage_roles:
        raise ValueError('Give the staff role Manage Roles permission first.')
    if db.execute('SELECT 1 FROM bindings WHERE role_id=?',(staff_role.id,)).fetchone():
        raise ValueError('A role managed by the bot cannot become a staff access role.')
    setting('staff_role_ids',[str(staff_role.id)])
    setting('welcome_channel_id',str(welcome_channel.id))
    setting('ticket_category_id',str(ticket_category.id))
    audit(i.user.id,i.guild.id,'setup',f'Staff role {staff_role.id}')
    await i.response.send_message('Setup saved. Next: use /bind to link existing roles, /create_role for new catalog roles, and /menu for the command guide.',ephemeral=True)

@bot.tree.command(description='Owner: create and link a missing catalog role with no server permissions')
@app_commands.autocomplete(key=keys)
async def create_role(i: discord.Interaction, key: str):
    if not owner(i):
        raise ValueError('Only the server owner can create roles.')
    if key not in CONFIG['roles']:
        raise ValueError('Unknown key. Use /catalog.')
    await i.response.defer(ephemeral=True)
    async with lock:
        if db.execute('SELECT 1 FROM bindings WHERE key=?',(key,)).fetchone():
            raise ValueError('Already linked. Use /profile to inspect assigned roles.')
        role = await i.guild.create_role(name=CONFIG['roles'][key]['name'],permissions=discord.Permissions.none(),reason='GUC catalog setup')
        with db:
            db.execute('INSERT INTO bindings VALUES(?,?)',(key,role.id))
        audit(i.user.id,role.id,'create_role',key)
    await i.followup.send(f'Created and linked {role.name}. Arrange rank roles in Discord from highest to lowest.',ephemeral=True)

@bot.tree.command(description='Open the easy GUC command menu')
async def menu(i: discord.Interaction):
    embed=discord.Embed(title='GUC Command Center',color=0x2459a6,
        description='Type / and select a command. Discord shows the member, role, and channel pickers for you.')
    embed.add_field(name='Rank registration',value='/rank_register • /rank_requests • /rank_confirm • /rank_deny',inline=False)
    embed.add_field(name='Members',value='/enlist • /apply • /application_status • /profile • /catalog • /ticket',inline=False)
    embed.add_field(name='Staff — personnel & events',value='/assign • /revoke • /applications • /review • /announce • /audit_log',inline=False)
    embed.add_field(name='Staff — moderation',value='/warn • /timeout • /untimeout • /kick • /ban • /ticket_close',inline=False)
    embed.add_field(name='Owner — configuration',value='/setup • /bind • /create_role',inline=False)
    embed.add_field(name='Ranks, certs, attendance & rules',value='/structure • /rankup • /rank_queue • /cert_lookup • /cert_grant • /cert_revoke • /attendance • /attendance_export • /rules',inline=False)
    embed.add_field(name='Owner setup additions',value='/rank_registration_setup • /personnel_set • /attendance_setup • /rules_set',inline=False)
    embed.add_field(name='Promotion approvals & marks',value='/promotion_approve • /promotion_status • /promotion_execute • /promotion_deny • /rank_status • /mark_award • /mark_revoke',inline=False)
    embed.add_field(name='Events & member status',value='/startcombat • /stopcombat • /startonduty • /stoponduty • /attendance_active • /attendance_void • /status create • /status show • /member_status',inline=False)
    embed.add_field(name='Strikes & handbook',value='/strike add • /strike remove • /strike list • /handbook',inline=False)
    await i.response.send_message(embed=embed,ephemeral=True)

@bot.tree.command(description='Check your most recent membership application')
async def application_status(i: discord.Interaction):
    row=db.execute('SELECT id,faction,status FROM applications WHERE user_id=? ORDER BY id DESC LIMIT 1',(i.user.id,)).fetchone()
    await i.response.send_message(f'Application #{row[0]} — {row[1]}: **{row[2]}**' if row else 'No application yet. Use /apply.',ephemeral=True)

@bot.tree.command(description='Open a private GUC support ticket')
async def ticket(i: discord.Interaction, subject: app_commands.Range[str,3,100]):
    await i.response.defer(ephemeral=True)
    async with lock:
        old=db.execute('SELECT channel_id FROM tickets WHERE user_id=?',(i.user.id,)).fetchone()
        if old and i.guild.get_channel(old[0]):
            raise ValueError(f'You already have a ticket: <#{old[0]}>')
        category=i.guild.get_channel(int(CONFIG.get('ticket_category_id') or 0))
        if not isinstance(category,discord.CategoryChannel):
            raise ValueError('Ask the owner to run /setup first.')
        overwrites={i.guild.default_role:discord.PermissionOverwrite(view_channel=False),
                    i.user:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True),
                    i.guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,manage_channels=True)}
        for rid in CONFIG['staff_role_ids']:
            role=i.guild.get_role(int(rid))
            if role:
                overwrites[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True)
        channel=await i.guild.create_text_channel(f'ticket-{i.user.id}',category=category,overwrites=overwrites,reason='GUC support ticket')
        with db:
            db.execute('INSERT INTO tickets VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET channel_id=excluded.channel_id',(i.user.id,channel.id))
        audit(i.user.id,channel.id,'ticket_open',subject)
    await channel.send(f'**GUC support ticket**\nSubject: {discord.utils.escape_markdown(subject)}\nStaff will respond here. Staff can use /ticket_close to archive access.')
    await i.followup.send(f'Your ticket: {channel.mention}',ephemeral=True)

@bot.tree.command(description='Staff: close this ticket while keeping its channel as a record')
async def ticket_close(i: discord.Interaction):
    staff(i)
    row=db.execute('SELECT user_id FROM tickets WHERE channel_id=?',(i.channel_id,)).fetchone()
    if not row:
        raise ValueError('Use this command inside an open ticket.')
    await i.response.defer(ephemeral=True)
    # Remove member-specific visibility, preserving staff-only archive.
    overwrite=dict(i.channel.overwrites)
    for target in list(overwrite):
        if isinstance(target,discord.Member) and target.id == row[0]:
            overwrite.pop(target)
    await i.channel.edit(name=f'closed-{row[0]}',overwrites=overwrite,reason=f'GUC closed by {i.user.id}')
    with db:
        db.execute('DELETE FROM tickets WHERE channel_id=?',(i.channel_id,))
    audit(i.user.id,row[0],'ticket_closed',str(i.channel_id))
    await i.followup.send('Ticket closed; channel retained for staff. Administrators can delete it when no longer needed.',ephemeral=True)

async def moderation_target(i,member,permission):
    staff(i)
    if not owner(i) and not getattr(i.user.guild_permissions,permission):
        raise ValueError(f'You also need the {permission} permission.')
    if not getattr(i.guild.me.guild_permissions,permission):
        raise ValueError(f'The bot needs the {permission} permission.')
    member=await i.guild.fetch_member(member.id)
    check_target(i,member)
    return member

@bot.tree.command(description='Staff: record a warning in the private audit log')
async def warn(i: discord.Interaction, member: discord.Member, reason: app_commands.Range[str,3,400]):
    staff(i)
    check_target(i,member)
    audit(i.user.id,member.id,'warning',reason)
    await i.response.send_message('Warning recorded. No DM was sent.',ephemeral=True)

@bot.tree.command(description='Staff: temporarily restrict a member (maximum 28 days)')
async def timeout(i: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int,1,40320], reason: app_commands.Range[str,3,400]):
    await i.response.defer(ephemeral=True)
    member=await moderation_target(i,member,'moderate_members')
    await member.timeout(timedelta(minutes=minutes),reason=reason)
    audit(i.user.id,member.id,'timeout',f'{minutes} minutes: {reason}')
    await i.followup.send('Timeout applied.',ephemeral=True)

@bot.tree.command(description='Staff: remove a member’s timeout')
async def untimeout(i: discord.Interaction, member: discord.Member, reason: app_commands.Range[str,3,400]):
    await i.response.defer(ephemeral=True)
    member=await moderation_target(i,member,'moderate_members')
    await member.timeout(None,reason=reason)
    audit(i.user.id,member.id,'untimeout',reason)
    await i.followup.send('Timeout removed.',ephemeral=True)

@bot.tree.command(description='Staff: kick a member; confirm must be true')
async def kick(i: discord.Interaction, member: discord.Member, reason: app_commands.Range[str,3,400], confirm: bool):
    if not confirm:
        raise ValueError('Cancelled. Set confirm to true only when ready.')
    await i.response.defer(ephemeral=True)
    member=await moderation_target(i,member,'kick_members')
    await member.kick(reason=reason)
    audit(i.user.id,member.id,'kick',reason)
    await i.followup.send('Member kicked.',ephemeral=True)

@bot.tree.command(description='Staff: ban a member without deleting message history; confirm must be true')
async def ban(i: discord.Interaction, member: discord.Member, reason: app_commands.Range[str,3,400], confirm: bool):
    if not confirm:
        raise ValueError('Cancelled. Set confirm to true only when ready.')
    await i.response.defer(ephemeral=True)
    member=await moderation_target(i,member,'ban_members')
    await member.ban(reason=reason,delete_message_seconds=0)
    audit(i.user.id,member.id,'ban',reason)
    await i.followup.send('Member banned. Unban through Discord server settings.',ephemeral=True)

@bot.tree.command(description='Staff: export the latest 100 audit records')
async def audit_log(i: discord.Interaction):
    staff(i)
    import io
    rows=db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100').fetchall()
    await i.response.send_message(file=discord.File(io.BytesIO(json.dumps(rows,indent=2).encode()),'GUC_audit.json'),ephemeral=True)


# Version 2: hierarchy, certifications, attendance, published rules
import time
import csv
import io
from datetime import datetime, timezone
from discord.ext import tasks

FACTIONS=[app_commands.Choice(name='Republic',value='Republic'),app_commands.Choice(name='Empire',value='Empire')]

def ladder(faction):
    return CONFIG.get('rank_ladders',{}).get(faction,[])

def next_rank(member,faction,direction):
    ordered=ladder(faction)
    if not ordered:raise ValueError('Owner must configure this rank ladder first.')
    owned={r.id for r in member.roles}
    current=[key for key in ordered if (row:=db.execute('SELECT role_id FROM bindings WHERE key=?',(key,)).fetchone()) and row[0] in owned]
    if len(current)!=1:raise ValueError('Member must have exactly one linked rank in this ladder. Use /assign to correct it.')
    n=ordered.index(current[0])+direction
    if not 0<=n<len(ordered):raise ValueError('Member is already at the end of this rank ladder.')
    return ordered[n]

@bot.tree.command(description='Show the configured GUC rank ladders and role structure')
async def structure(i: discord.Interaction):
    lines=['GUC configured structure — lowest to highest. Owner must verify against official hierarchy.']
    for faction in ('Republic','Empire'):
        lines.append('\n'+faction)
        for n,key in enumerate(ladder(faction),1):
            row=db.execute('SELECT role_id FROM bindings WHERE key=?',(key,)).fetchone()
            lines.append(f"{n}. {CONFIG['roles'][key]['name']} | {key} | Discord role: {row[0] if row else 'NOT LINKED'}")
    lines.append('\nOther configured units/roles/certs:')
    lines.extend(f"{v['faction']} | {v['kind']} | {v['name']}" for v in CONFIG['roles'].values() if v['kind']!='rank')
    await i.response.send_message(file=discord.File(io.BytesIO('\n'.join(lines).encode()),'GUC_structure.txt'),ephemeral=True)

@bot.tree.command(description='Owner: place a linked rank in its faction ladder, 1 is lowest')
@app_commands.autocomplete(key=keys)
async def rank_order(i: discord.Interaction,key: str,position: app_commands.Range[int,1,100]):
    if not owner(i):raise ValueError('Only the server owner may edit the hierarchy.')
    spec=CONFIG['roles'].get(key,{})
    if spec.get('kind')!='rank':raise ValueError('Select a rank key from /catalog.')
    async with lock:
        data={k:list(v) for k,v in CONFIG.get('rank_ladders',{}).items()}
        arr=data.setdefault(spec['faction'],[])
        if key in arr:arr.remove(key)
        if position>len(arr)+1:raise ValueError(f'Position must be at most {len(arr)+1}.')
        arr.insert(position-1,key)
        setting('rank_ladders',data)
        audit(i.user.id,i.guild.id,'rank_order',f'{key} -> {position}')
    await i.response.send_message('Rank order updated. Check /structure.',ephemeral=True)

@bot.tree.command(description='Owner: add an existing server rank to the catalog and end of its ladder')
@app_commands.choices(faction=FACTIONS)
async def rank_add(i: discord.Interaction,role: discord.Role,faction: str):
    if not owner(i):raise ValueError('Only the server owner may add ranks.')
    check_role(i,role)
    async with lock:
        if db.execute('SELECT 1 FROM bindings WHERE role_id=?',(role.id,)).fetchone():
            raise ValueError('Role is already linked. Use /rank_order for its catalog key.')
        key=f'rank_{role.id}'
        data=dict(CONFIG['roles'])
        data[key]={'name':role.name,'kind':'rank','faction':faction}
        ladders={k:list(v) for k,v in CONFIG.get('rank_ladders',{}).items()}
        ladders.setdefault(faction,[]).append(key)
        with db:
            db.execute('INSERT INTO bindings VALUES(?,?)',(key,role.id))
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('roles',json.dumps(data)))
            db.execute('INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('rank_ladders',json.dumps(ladders)))
        CONFIG['roles']=data
        CONFIG['rank_ladders']=ladders
        audit(i.user.id,role.id,'rank_add',key)
    await i.response.send_message(f'Added `{key}`. Use /rank_order to position it correctly.',ephemeral=True)

@bot.tree.command(description='Staff: request the next rank; checks marks, waits and required approvals')
@app_commands.choices(faction=FACTIONS)
async def rankup(i: discord.Interaction,member: discord.Member,faction: str,reason: app_commands.Range[str,3,400]):
    await request_rank_promotion(i,member,faction,reason)

@bot.tree.command(description='Staff: demote a member one step in the configured faction ladder')
@app_commands.choices(faction=FACTIONS)
async def rankdown(i: discord.Interaction,member: discord.Member,faction: str,reason: app_commands.Range[str,3,400]):
    await assign.callback(i,member,'__down_'+faction,reason)

async def cert_keys(i: discord.Interaction,current: str):
    return [app_commands.Choice(name=v['name'][:100],value=k) for k,v in CONFIG['roles'].items() if v['kind']=='cert' and current.lower() in (k+' '+v['name']).lower()][:25]

@bot.tree.command(description='Staff: grant a certification role and save issuer/date/reason')
@app_commands.autocomplete(key=cert_keys)
async def cert_grant(i: discord.Interaction,member: discord.Member,key: str,reason: app_commands.Range[str,3,400]):
    if CONFIG['roles'].get(key,{}).get('kind')!='cert':raise ValueError('Choose a certification key.')
    await assign.callback(i,member,key,reason)

@bot.tree.command(description='Staff: revoke a certification role and its active record')
@app_commands.autocomplete(key=cert_keys)
async def cert_revoke(i: discord.Interaction,member: discord.Member,key: str,reason: app_commands.Range[str,3,400]):
    if CONFIG['roles'].get(key,{}).get('kind')!='cert':raise ValueError('Choose a certification key.')
    await revoke.callback(i,member,key,reason)

@bot.tree.command(description='Look up your certification records; staff can look up another member')
async def cert_lookup(i: discord.Interaction,member: discord.Member | None=None):
    member=member or i.user
    if member.id!=i.user.id:staff(i)
    await i.response.defer(ephemeral=True)
    member=await i.guild.fetch_member(member.id)
    owned={r.id for r in member.roles}
    rows=[]
    for key,spec in CONFIG['roles'].items():
        if spec['kind']!='cert':continue
        bound=db.execute('SELECT role_id FROM bindings WHERE key=?',(key,)).fetchone()
        record=db.execute('SELECT issuer,issued,reason FROM certs WHERE user_id=? AND key=?',(member.id,key)).fetchone()
        has_role=bool(bound and bound[0] in owned)
        if record or has_role:rows.append(f"{spec['name']} | Role present: {has_role} | "+(f'Issuer: {record[0]} | {record[1]} UTC | {record[2]}' if record else 'No bot-issued record (assigned outside bot)'))
    await i.followup.send(file=discord.File(io.BytesIO(('\n'.join(rows) or 'No certifications found.').encode()),'certifications.txt'),ephemeral=True)

@bot.tree.command(description='Read the owner-published GUC rules')
async def rules(i: discord.Interaction):
    body=CONFIG.get('published_rules')
    if not body:
        await i.response.send_message('Official rules have not been published in this bot yet. Ask the owner to use /rules_set.',ephemeral=True)
    else:await i.response.send_message(embed=discord.Embed(title='GUC Rules',description=body,color=0x2459a6),ephemeral=True)

@bot.tree.command(description='Owner: publish or replace the official rules shown by /rules')
async def rules_set(i: discord.Interaction,text: app_commands.Range[str,10,3800]):
    if not owner(i):raise ValueError('Only the server owner can publish official rules.')
    setting('published_rules',text)
    audit(i.user.id,i.guild.id,'rules_updated',text)
    await i.response.send_message('Rules saved. Members can read them with /rules.',ephemeral=True)


import sys
from governance import install as install_governance
install_governance(sys.modules[__name__])
from rank_registration import install as install_rank_registration
install_rank_registration(sys.modules[__name__])
from role_requests import install as install_role_requests
install_role_requests(sys.modules[__name__])
from event_status import install as install_event_status
install_event_status(sys.modules[__name__])
from manual_attendance import install as install_manual_attendance
install_manual_attendance(sys.modules[__name__])
from strikes import install as install_strikes
install_strikes(sys.modules[__name__])

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    if not token or not GUILD_ID:
        raise SystemExit('Set DISCORD_TOKEN and DISCORD_GUILD_ID in .env first. See README.md.')
    bot.run(token)
