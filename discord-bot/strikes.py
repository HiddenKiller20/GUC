"""Three active strikes per member, with permanent removal history."""
import io
import time
from datetime import datetime,timezone
import discord
from discord import app_commands

HANDBOOK_URL='https://docs.google.com/document/d/1CtAVvPZMJGQDYdTCUMrYyhG6QPJYxMEiiStpgLkUULM/edit?usp=drivesdk'
HANDBOOK_TITLE='The Galactic Unification Corp — Galactic Republic Handbook — Revised Draft'

class StrikeStore:
    def __init__(self,db):
        self.db=db
        db.executescript('''CREATE TABLE IF NOT EXISTS strikes(
        id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,slot INTEGER NOT NULL CHECK(slot BETWEEN 1 AND 3),
        issuer INTEGER NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL,
        removed REAL,removed_by INTEGER,removal_reason TEXT);
        CREATE UNIQUE INDEX IF NOT EXISTS active_strike_slot ON strikes(user_id,slot) WHERE removed IS NULL;''')
    def active_count(self,uid):
        return self.db.execute('SELECT COUNT(*) FROM strikes WHERE user_id=? AND removed IS NULL',(uid,)).fetchone()[0]
    def add(self,uid,issuer,reason,now):
        if not reason.strip():raise ValueError('A strike requires a reason.')
        # Slot constraint and unique index enforce the cap even with an accidental second writer.
        with self.db:
            cur=self.db.execute('''INSERT INTO strikes(user_id,slot,issuer,reason,created)
            SELECT ?,n,?,?,? FROM (SELECT 1 AS n UNION ALL SELECT 2 UNION ALL SELECT 3)
            WHERE n NOT IN (SELECT slot FROM strikes WHERE user_id=? AND removed IS NULL)
            ORDER BY n LIMIT 1''',(uid,issuer,reason.strip(),now,uid))
            if cur.rowcount!=1:raise ValueError('Member already has 3/3 active strikes. No additional strike was added; staff review is required.')
        return cur.lastrowid,self.active_count(uid)
    def remove(self,sid,actor,reason,now):
        if not reason.strip():raise ValueError('A removal requires a reason.')
        with self.db:
            cur=self.db.execute('UPDATE strikes SET removed=?,removed_by=?,removal_reason=? WHERE id=? AND removed IS NULL',(now,actor,reason.strip(),sid))
            if cur.rowcount!=1:raise ValueError('Strike is missing or already removed.')
    def member_for(self,sid):
        row=self.db.execute('SELECT user_id FROM strikes WHERE id=?',(sid,)).fetchone()
        if not row:raise ValueError('Unknown strike ID.')
        return row[0]

def install(b):
    store=StrikeStore(b.db)
    group=app_commands.Group(name='strike',description='Manage GUC strikes: maximum three active strikes per member')

    @group.command(name='add',description='Staff: issue a strike with a reason; maximum 3 active strikes')
    async def add(i:discord.Interaction,member:discord.Member,reason:app_commands.Range[str,3,1000]):
        b.staff(i)
        await i.response.defer(ephemeral=True)
        async with b.lock:
            member=await i.guild.fetch_member(member.id)
            b.check_target(i,member)
            sid,count=store.add(member.id,i.user.id,reason,time.time())
            b.audit(i.user.id,member.id,'strike_added',f'#{sid} ({count}/3): {reason}')
        text=f'Strike #{sid} recorded for {member.display_name}. **{count}/3 active strikes.**'
        if count==3:text+='\n**Maximum reached — staff review required.** No automatic kick, ban or demotion was performed.'
        await i.followup.send(text,ephemeral=True)

    @group.command(name='remove',description='Staff: remove an active strike by ID while preserving its history')
    async def remove(i:discord.Interaction,strike_id:int,reason:app_commands.Range[str,3,1000]):
        b.staff(i)
        await i.response.defer(ephemeral=True)
        async with b.lock:
            uid=store.member_for(strike_id)
            try:member=await i.guild.fetch_member(uid)
            except discord.NotFound:
                if not b.owner(i):raise ValueError('Only the owner may remove strikes for a member who left the server.')
            else:b.check_target(i,member)
            store.remove(strike_id,i.user.id,reason,time.time())
            count=store.active_count(uid)
            b.audit(i.user.id,uid,'strike_removed',f'#{strike_id}: {reason}')
        await i.followup.send(f'Strike #{strike_id} removed. Member now has **{count}/3 active strikes**. History preserved.',ephemeral=True)

    @group.command(name='list',description='View your strikes and history; staff may choose another member')
    async def list_strikes(i:discord.Interaction,member:discord.Member|None=None):
        member=member or i.user
        if member.id!=i.user.id:b.staff(i)
        count=store.active_count(member.id)
        rows=b.db.execute('SELECT id,issuer,reason,created,removed,removed_by,removal_reason FROM strikes WHERE user_id=? ORDER BY id DESC LIMIT 500',(member.id,)).fetchall()
        lines=[f'GUC strikes for {member.display_name} ({member.id})',f'Active: {count}/3','Maximum reached — staff review required.' if count==3 else '', 'Most recent 500 records; full history retained in database.']
        fmt=lambda ts:datetime.fromtimestamp(ts,timezone.utc).isoformat()
        for sid,issuer,reason,created,removed,remover,removal_reason in rows:
            lines.append(f'\n#{sid} | {"REMOVED" if removed is not None else "ACTIVE"} | Issuer {issuer} | {fmt(created)}\nReason: {reason}')
            if removed is not None:lines.append(f'Removed by {remover} at {fmt(removed)}\nRemoval reason: {removal_reason}')
        if not rows:lines.append('No strikes recorded.')
        await i.response.send_message(f'**{count}/3 active strikes.**',file=discord.File(io.BytesIO('\n'.join(lines).encode()),'GUC_strikes.txt'),ephemeral=True)

    b.bot.tree.add_command(group)

    @b.bot.tree.command(description='Open the Galactic Republic Handbook in Google Drive')
    async def handbook(i:discord.Interaction):
        embed=discord.Embed(title=HANDBOOK_TITLE,url=HANDBOOK_URL,color=0x2459a6,
            description=f'[Open the Galactic Republic Handbook]({HANDBOOK_URL})\nGoogle Drive access permissions apply. This links the document; it does not automatically import its rules into bot policy.')
        view=discord.ui.View()
        view.add_item(discord.ui.Button(label='Open Handbook',url=HANDBOOK_URL))
        await i.response.send_message(embed=embed,view=view,ephemeral=True)
