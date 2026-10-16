"""Self-service initial registration, approved by a configured Server Manager role."""
import time
from datetime import datetime, timezone
import discord
from discord import app_commands
from promotion_policy import CODES


def install(b):
    db=b.db
    db.executescript('''CREATE TABLE IF NOT EXISTS rank_registrations(
        id INTEGER PRIMARY KEY,user_id INTEGER,faction TEXT,rank_code TEXT,
        rank_since REAL,service_since REAL,reason TEXT,status TEXT DEFAULT 'pending',
        reviewer INTEGER,review_reason TEXT,created REAL);
        CREATE UNIQUE INDEX IF NOT EXISTS one_rank_registration
        ON rank_registrations(user_id,faction) WHERE status='pending';''')
    def key(faction,code):return ('rep_' if faction=='Republic' else 'emp_')+code
    def held(member,faction):
        ids={r.id for r in member.roles}
        return [c for c in CODES if (row:=db.execute('SELECT role_id FROM bindings WHERE key=?',(key(faction,c),)).fetchone()) and row[0] in ids]
    def manager_role(guild):
        configured=b.CONFIG.get('server_manager_role_id')
        if configured:
            role=guild.get_role(int(configured))
            if role and not role.is_default():return role
        else:
            matches=[r for r in guild.roles if r.name.casefold()=='server manager' and not r.is_default()]
            if len(matches)==1:return matches[0]
        raise ValueError('Owner must select the Server Manager role with /rank_registration_setup.')
    async def reviewer(i):
        role=manager_role(i.guild)
        member=await i.guild.fetch_member(i.user.id)
        if role.id not in {r.id for r in member.roles}:
            raise ValueError('Only members with the Server Manager role can review registrations.')
        return member
    def parse(value):
        try:stamp=datetime.strptime(value,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
        except ValueError:raise ValueError('Use YYYY-MM-DD dates in UTC.')
        if stamp>time.time():raise ValueError('Dates cannot be in the future.')
        return stamp
    async def submit(i,faction,rs,ss,reason,recruit=False):
        manager_role(i.guild)
        if ss>rs:raise ValueError('Service start cannot be after rank start.')
        await i.response.defer(ephemeral=True)
        async with b.lock:
            member=await i.guild.fetch_member(i.user.id)
            if member.bot:raise ValueError('Bot accounts cannot register.')
            if db.execute('SELECT 1 FROM personnel WHERE user_id=? AND faction=?',(member.id,faction)).fetchone():
                raise ValueError('Already registered. Use the rankup approval workflow for promotions.')
            if db.execute("SELECT 1 FROM rank_registrations WHERE user_id=? AND faction=? AND status='pending'",(member.id,faction)).fetchone():
                raise ValueError('You already have a pending registration for this faction.')
            ranks=held(member,faction)
            if recruit:
                if ranks:raise ValueError('You already hold a linked rank. Use /rank_register.')
                code='recruit'
            else:
                if len(ranks)!=1:raise ValueError('You must hold exactly one linked rank for this faction. New members can use /enlist to request Recruit.')
                code=ranks[0]
            with db:
                cur=db.execute('INSERT INTO rank_registrations(user_id,faction,rank_code,rank_since,service_since,reason,created) VALUES(?,?,?,?,?,?,?)',(member.id,faction,code,rs,ss,reason,time.time()))
            b.audit(member.id,member.id,'registration_requested',f'#{cur.lastrowid} {faction} {code}: {reason}')
        await i.followup.send(f'Registration #{cur.lastrowid} is pending Server Manager confirmation. No rank record has been activated yet.',ephemeral=True)

    b.bot.tree.remove_command('rank_register')
    b.bot.tree.remove_command('enlist')

    @b.bot.tree.command(description='Request registration of your existing rank; Server Manager confirmation required')
    @app_commands.choices(faction=b.FACTIONS)
    async def rank_register(i:discord.Interaction,faction:str,rank_started:str,service_started:str,reason:app_commands.Range[str,3,400]):
        await submit(i,faction,parse(rank_started),parse(service_started),reason)

    @b.bot.tree.command(description='Request Recruit membership; Server Manager confirmation required')
    @app_commands.choices(faction=b.FACTIONS)
    async def enlist(i:discord.Interaction,faction:str):
        now=time.time()
        await submit(i,faction,now,now,'New Recruit enlistment',True)

    @b.bot.tree.command(description='Owner: select the role allowed to confirm rank registrations')
    async def rank_registration_setup(i:discord.Interaction,manager:discord.Role):
        if not b.owner(i):raise ValueError('Only the server owner may configure the reviewer role.')
        if manager.is_default() or manager.managed:raise ValueError('Select a dedicated human Server Manager role.')
        b.setting('server_manager_role_id',str(manager.id))
        await i.response.send_message(f'Rank registrations require confirmation by {manager.name}.',ephemeral=True)

    @b.bot.tree.command(description='Server Manager: list pending initial rank registrations')
    async def rank_requests(i:discord.Interaction):
        await reviewer(i)
        rows=db.execute("SELECT id,user_id,faction,rank_code,rank_since,service_since FROM rank_registrations WHERE status='pending' ORDER BY id LIMIT 20").fetchall()
        await i.response.send_message('\n'.join(f'#{rid} | Member {uid} | {faction} {code} | Rank <t:{int(rs)}:d> | Service <t:{int(ss)}:d>' for rid,uid,faction,code,rs,ss in rows) or 'No pending registrations.',ephemeral=True)

    async def review(i,request_id,reason,approve):
        await i.response.defer(ephemeral=True)
        async with b.lock:
            actor=await reviewer(i)
            row=db.execute('SELECT user_id,faction,rank_code,rank_since,service_since,status FROM rank_registrations WHERE id=?',(request_id,)).fetchone()
            if not row or row[5]!='pending':raise ValueError('Unknown or already reviewed registration.')
            uid,faction,code,rs,ss,_=row
            if uid==actor.id:raise ValueError('Another Server Manager must review your registration.')
            if approve:
                if db.execute('SELECT 1 FROM personnel WHERE user_id=? AND faction=?',(uid,faction)).fetchone():raise ValueError('Member is already registered; deny this stale request.')
                member=await i.guild.fetch_member(uid)
                ranks=held(member,faction)
                if ranks!=[code]:
                    if code!='recruit' or ranks:raise ValueError('Linked rank roles changed. Deny this request and ask the member to resubmit.')
                    # Only initial Recruit roles can be granted here; promotions retain their approval rules.
                    b.check_target(i,member)
                    role=b.role_for(i,key(faction,'recruit'))
                    await member.add_roles(role,reason=f'GUC registration #{request_id} approved by {actor.id}')
            status='approved' if approve else 'denied'
            with db:
                if approve:db.execute('INSERT INTO personnel(user_id,faction,rank_code,rank_since,service_since) VALUES(?,?,?,?,?)',(uid,faction,code,rs,ss))
                db.execute('UPDATE rank_registrations SET status=?,reviewer=?,review_reason=? WHERE id=?',(status,actor.id,reason,request_id))
            b.audit(actor.id,uid,'registration_'+status,f'#{request_id}: {reason}')
        await i.followup.send(f'Registration #{request_id} {status}.',ephemeral=True)

    @b.bot.tree.command(description='Server Manager: confirm an initial rank registration')
    async def rank_confirm(i:discord.Interaction,request_id:int,reason:app_commands.Range[str,3,400]):
        await review(i,request_id,reason,True)

    @b.bot.tree.command(description='Server Manager: deny an initial rank registration')
    async def rank_deny(i:discord.Interaction,request_id:int,reason:app_commands.Range[str,3,400]):
        await review(i,request_id,reason,False)
