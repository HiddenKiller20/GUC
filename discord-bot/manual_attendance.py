"""Command-based attendance. One completed session = one mark, including combat."""
import time
import io
import csv
from datetime import datetime,timezone
import discord
from discord import app_commands

class SessionStore:
    def __init__(self,db):
        self.db=db
        db.executescript('''CREATE TABLE IF NOT EXISTS manual_attendance(id INTEGER PRIMARY KEY,
        user_id INTEGER,faction TEXT,kind TEXT,start REAL,end REAL,status TEXT DEFAULT 'active');
        CREATE UNIQUE INDEX IF NOT EXISTS one_manual_session ON manual_attendance(user_id) WHERE status='active';''')
    def start(self,uid,faction,kind,now):
        if self.db.execute("SELECT 1 FROM manual_attendance WHERE user_id=? AND status='active'",(uid,)).fetchone():
            raise ValueError('You already have an active attendance session. Use the matching /stopcombat or /stoponduty first.')
        with self.db:
            cur=self.db.execute('INSERT INTO manual_attendance(user_id,faction,kind,start) VALUES(?,?,?,?)',(uid,faction,kind,now))
        return cur.lastrowid
    def stop(self,uid,now,expected_kind=None):
        row=self.db.execute("SELECT id,faction,kind,start FROM manual_attendance WHERE user_id=? AND status='active'",(uid,)).fetchone()
        if not row:raise ValueError('No active attendance session. Use /startcombat or /startonduty first. No mark was awarded.')
        sid,faction,kind,start=row
        if expected_kind is not None and kind != expected_kind:
            raise ValueError('Wrong session type. Use /stopcombat for combat or /stoponduty for On-Duty. No mark awarded.')
        with self.db:
            self.db.execute("UPDATE manual_attendance SET end=?,status='completed' WHERE id=?",(now,sid))
            self.db.execute('INSERT OR IGNORE INTO marks VALUES(?,?,?,?,?)',(uid,faction,f'attendance-{sid}',uid,now))
        return row
    def void(self,sid):
        row=self.db.execute('SELECT user_id,faction FROM manual_attendance WHERE id=?',(sid,)).fetchone()
        if not row:raise ValueError('Unknown attendance session.')
        with self.db:
            self.db.execute("UPDATE manual_attendance SET status='void' WHERE id=?",(sid,))
            self.db.execute('DELETE FROM marks WHERE user_id=? AND faction=? AND event=?',(row[0],row[1],f'attendance-{sid}'))
        return row[0]

def install(b):
    db=b.db;store=SessionStore(db)
    kinds=[app_commands.Choice(name='Attendance / On-Duty',value='attendance'),app_commands.Choice(name='Combat attendance',value='combat')]
    async def log(i,message):
        channel=i.guild.get_channel(int(b.CONFIG.get('attendance_log_channel_id') or 0))
        if channel:
            try:await channel.send(message)
            except discord.HTTPException:pass  # database remains authoritative

    async def start_session(i,faction,kind):
        if i.user.bot:raise ValueError('Bot accounts cannot log attendance.')
        # Every human server member may log their own attendance, even before rank registration.
        async with b.lock:
            now=time.time();sid=store.start(i.user.id,faction,kind,now)
            b.audit(i.user.id,i.user.id,'attendance_start',f'#{sid} {faction} {kind}')
        await i.response.send_message(f'Attendance #{sid} started at <t:{int(now)}:F> ({faction}, {kind}). Use {'/stopcombat' if kind=='combat' else '/stoponduty'} when finished. One completed session earns one mark.',ephemeral=True)
        await log(i,f'Attendance #{sid} | Member {i.user.id} | {kind} START <t:{int(now)}:F>')

    async def stop_session(i,kind):
        async with b.lock:
            now=time.time();sid,faction,kind,started=store.stop(i.user.id,now,kind)
            b.audit(i.user.id,i.user.id,'attendance_stop',f'#{sid}; one {faction} mark')
        minutes=max(0,now-started)/60
        message=f'Attendance #{sid} | Member {i.user.id} | {kind}\nStart: <t:{int(started)}:F>\nStop: <t:{int(now)}:F>\nDuration: {minutes:.1f} minutes\n**1 {faction} attendance mark awarded.**'
        await i.response.send_message(message,ephemeral=True)
        await log(i,message)

    @b.bot.tree.command(description='Start combat attendance; finish with /stopcombat for one mark')
    @app_commands.choices(faction=b.FACTIONS)
    async def startcombat(i:discord.Interaction,faction:str):
        await start_session(i,faction,'combat')

    @b.bot.tree.command(description='Finish your combat attendance and receive one mark')
    async def stopcombat(i:discord.Interaction):
        await stop_session(i,'combat')

    @b.bot.tree.command(description='Start On-Duty attendance; finish with /stoponduty for one mark')
    @app_commands.choices(faction=b.FACTIONS)
    async def startonduty(i:discord.Interaction,faction:str):
        await start_session(i,faction,'attendance')

    @b.bot.tree.command(description='Finish your On-Duty attendance and receive one mark')
    async def stoponduty(i:discord.Interaction):
        await stop_session(i,'attendance')

    @b.bot.tree.command(description='Check your active command-based attendance session')
    async def attendance_active(i:discord.Interaction):
        row=db.execute("SELECT id,faction,kind,start FROM manual_attendance WHERE user_id=? AND status='active'",(i.user.id,)).fetchone()
        await i.response.send_message(f'#{row[0]} | {row[1]} | {row[2]} | Started <t:{int(row[3])}:F>. Use the matching /stopcombat or /stoponduty to finish.' if row else 'No active session. Use /startcombat or /startonduty.',ephemeral=True)

    @b.bot.tree.command(description='Owner: choose the text channel receiving attendance start/stop logs')
    async def attendance_setup(i:discord.Interaction,log_channel:discord.TextChannel):
        if not b.owner(i):raise ValueError('Only the owner can configure attendance logging.')
        p=log_channel.permissions_for(i.guild.me)
        if not (p.view_channel and p.send_messages):raise ValueError('Bot must be able to view and send in the selected log channel.')
        b.setting('attendance_log_channel_id',str(log_channel.id))
        await i.response.send_message('Log channel saved. Attendance uses /startcombat + /stopcombat or /startonduty + /stoponduty; voice-channel activity is ignored.',ephemeral=True)

    @b.bot.tree.command(description='Staff: void a mistaken attendance session and remove its mark if awarded')
    async def attendance_void(i:discord.Interaction,session_id:int,reason:app_commands.Range[str,3,400]):
        b.staff(i)
        async with b.lock:
            uid=store.void(session_id)
            b.audit(i.user.id,uid,'attendance_void',f'#{session_id}: {reason}')
        await i.response.send_message('Session voided. Its attendance mark, if present, was removed. Original timestamps remain in the audit data.',ephemeral=True)

    async def report(i,uid,days):
        now=time.time();cutoff=now-days*86400
        sql='SELECT id,user_id,faction,kind,start,end,status FROM manual_attendance WHERE COALESCE(end,?)>=?'
        args=[now,cutoff]
        if uid is not None:sql+=' AND user_id=?';args.append(uid)
        sql+=' ORDER BY id DESC LIMIT 10000'
        out=io.StringIO();w=csv.writer(out)
        w.writerow(['session_id','user_id','faction','kind','start_utc','stop_utc','total_minutes','status','mark_present'])
        fmt=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
        for sid,user,faction,kind,start,end,status in db.execute(sql,args):
            mark=db.execute('SELECT 1 FROM marks WHERE user_id=? AND faction=? AND event=?',(user,faction,f'attendance-{sid}')).fetchone()
            w.writerow([sid,user,faction,kind,fmt(start),fmt(end) if end else '',round(max(0,(end or now)-start)/60,2) if status!='void' else '',status,bool(mark)])
        await i.response.send_message('Command-based attendance; timestamps in UTC. Up to 10,000 sessions overlapping the requested window; durations show full sessions.',file=discord.File(io.BytesIO(out.getvalue().encode()),'attendance.csv'),ephemeral=True)

    @b.bot.tree.command(description='Export your command-based attendance logs; staff may select another member')
    async def attendance(i:discord.Interaction,member:discord.Member|None=None,days:app_commands.Range[int,1,365]=30):
        member=member or i.user
        if member.id!=i.user.id:b.staff(i)
        await report(i,member.id,days)

    @b.bot.tree.command(description='Staff: export all command-based attendance logs')
    async def attendance_export(i:discord.Interaction,days:app_commands.Range[int,1,365]=30):
        b.staff(i);await report(i,None,days)

    @b.bot.tree.command(description='View attendance start/stop logs in Discord; staff may select another member')
    async def attendance_logs(i:discord.Interaction,member:discord.Member|None=None,days:app_commands.Range[int,1,365]=30,page:app_commands.Range[int,1,10000]=1):
        member=member or i.user
        if member.id!=i.user.id:b.staff(i)
        now=time.time();cutoff=now-days*86400
        where='user_id=? AND COALESCE(end,?)>=?'
        args=(member.id,now,cutoff)
        count=db.execute('SELECT COUNT(*) FROM manual_attendance WHERE '+where,args).fetchone()[0]
        pages=max(1,(count+4)//5)
        if page>pages:raise ValueError(f'Choose a page between 1 and {pages}.')
        rows=db.execute('SELECT id,faction,kind,start,end,status FROM manual_attendance WHERE '+where+' ORDER BY id DESC LIMIT 5 OFFSET ?',(*args,(page-1)*5)).fetchall()
        embed=discord.Embed(title='Attendance logs',description=f'Member: <@{member.id}> • Last {days} days\n{count} sessions overlapping this period.',color=0x2459a6)
        for sid,faction,kind,start,end,status in rows:
            mark=db.execute('SELECT 1 FROM marks WHERE user_id=? AND faction=? AND event=?',(member.id,faction,f'attendance-{sid}')).fetchone()
            stop=f'<t:{int(end)}:F>' if end is not None else ('Still active' if status=='active' else 'Not recorded')
            duration=f'{max(0,(end if end is not None else now)-start)/60:.1f} minutes' if status!='void' else 'Voided'
            embed.add_field(name=f'#{sid} • {faction} • {"Combat" if kind=="combat" else "On-Duty"} • {status}',value=f'Start: <t:{int(start)}:F>\nStop: {stop}\nDuration: {duration}\nMarks: {1 if mark else 0}',inline=False)
        if not rows:embed.add_field(name='No attendance found',value='Use /startcombat or /startonduty to begin.',inline=False)
        embed.set_footer(text=f'Page {page}/{pages} • Use page to see older entries. /attendance downloads a CSV.')
        await i.response.send_message(embed=embed,ephemeral=True)
