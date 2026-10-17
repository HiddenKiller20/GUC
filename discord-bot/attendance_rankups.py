"""Attendance-only promotions, capped at Staff Sergeant, for confirmed personnel."""
import logging
import time
import discord
from discord.ext import tasks
from promotion_policy import RANKS,CODES,BY_CODE

ENLISTED=RANKS[:8]
def earned_rank(current,marks):
    if current not in [r[0] for r in ENLISTED]:return None
    target=next(r[0] for r in reversed(ENLISTED) if marks>=r[3])
    return target if CODES.index(target)>CODES.index(current) else None

async def promote(b,guild,uid,faction):
    async with b.lock:
        row=b.db.execute('SELECT rank_code FROM personnel WHERE user_id=? AND faction=?',(uid,faction)).fetchone()
        if not row:return None
        src=row[0]
        count=b.db.execute('SELECT COUNT(*) FROM marks WHERE user_id=? AND faction=?',(uid,faction)).fetchone()[0]
        dst=earned_rank(src,count)
        if not dst:return None
        member=await guild.fetch_member(uid)
        if member.bot or uid==guild.owner_id:raise ValueError('Protected member.')
        if not guild.me.guild_permissions.manage_roles or member.top_role>=guild.me.top_role:raise ValueError('Bot needs Manage Roles and a role above the member.')
        prefix='rep_' if faction=='Republic' else 'emp_'
        bindings=dict(b.db.execute('SELECT key,role_id FROM bindings'))
        held=[k for k,v in b.CONFIG['roles'].items() if v['kind']=='rank' and v['faction']==faction and bindings.get(k) in {r.id for r in member.roles}]
        if held!=[prefix+src]:raise ValueError('Rank roles disagree with confirmed record; ask staff to reconcile them.')
        old=guild.get_role(bindings.get(prefix+src,0));new=guild.get_role(bindings.get(prefix+dst,0))
        protected=set(map(str,b.CONFIG['staff_role_ids']))|{str(b.CONFIG.get('server_manager_role_id',''))}
        for role in (old,new):
            if not role or role.is_default() or role.managed or role.permissions.value or str(role.id) in protected or role.name.casefold()=='server manager':raise ValueError('Link safe rank roles with /bind first.')
            if role>=guild.me.top_role:raise ValueError('Bot role must be above both rank roles.')
        b.audit(guild.me.id,uid,'attendance_rankup_requested',f'{faction} {src}->{dst}; {count} marks')
        await member.add_roles(new,reason=f'GUC automatic attendance rank: {count} marks')
        try:await member.remove_roles(old,reason='GUC automatic attendance rank replacement')
        except discord.HTTPException:
            try:await member.remove_roles(new,reason='GUC attendance promotion rollback')
            except discord.HTTPException:pass
            raise
        with b.db:
            b.db.execute('UPDATE personnel SET rank_code=?,rank_since=? WHERE user_id=? AND faction=?',(dst,time.time(),uid,faction))
            b.db.execute("UPDATE promotions SET status='cancelled: automatic attendance promotion' WHERE user_id=? AND faction=? AND status='pending'",(uid,faction))
        b.audit(guild.me.id,uid,'attendance_rankup_completed',f'{faction} {src}->{dst}; {count} marks')
        return BY_CODE[dst][1]

def install(b):
    @tasks.loop(seconds=60)
    async def sweep():
        guild=b.bot.get_guild(b.GUILD_ID)
        if not guild:return
        rows=b.db.execute('SELECT user_id,faction,rank_code FROM personnel').fetchall()
        for uid,faction,rank in rows:
            count=b.db.execute('SELECT COUNT(*) FROM marks WHERE user_id=? AND faction=?',(uid,faction)).fetchone()[0]
            if not earned_rank(rank,count):continue
            try:await promote(b,guild,uid,faction)
            except (ValueError,discord.HTTPException) as exc:
                logging.warning('Attendance rankup blocked for %s (%s): %s',uid,faction,exc)
            except Exception:
                logging.exception('Attendance rankup failed for %s (%s)',uid,faction)
    @sweep.before_loop
    async def ready():await b.bot.wait_until_ready()
    b.attendance_rankup_task=sweep
    @b.bot.event
    async def on_ready():
        if not sweep.is_running():sweep.start()
