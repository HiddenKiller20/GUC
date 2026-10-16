"""Approval-gated rank management. Discord changes cannot be fully transactional."""
import io
import json
import time
from datetime import datetime, timezone
import discord
from discord import app_commands
from promotion_policy import RANKS,CODES,BY_CODE,WAIT_DAYS,requirements,approval_errors

def install(b):
    db=b.db;config=b.CONFIG
    db.executescript('''
    CREATE TABLE IF NOT EXISTS personnel(user_id INTEGER,faction TEXT,rank_code TEXT,rank_since REAL,
      service_since REAL,adult INTEGER DEFAULT 0,commander INTEGER,PRIMARY KEY(user_id,faction));
    CREATE TABLE IF NOT EXISTS marks(user_id INTEGER,faction TEXT,event TEXT,issuer INTEGER,created REAL,
      PRIMARY KEY(user_id,faction,event));
    CREATE TABLE IF NOT EXISTS promotions(id INTEGER PRIMARY KEY,user_id INTEGER,faction TEXT,
      from_code TEXT,to_code TEXT,rank_since REAL,final_code TEXT,jump INTEGER DEFAULT 0,
      status TEXT DEFAULT 'pending',reason TEXT,created REAL);
    CREATE TABLE IF NOT EXISTS approvals(proposal INTEGER,approver INTEGER,kind TEXT,evidence TEXT,
      PRIMARY KEY(proposal,approver,kind));
    ''')
    # Install authoritative ladder while preserving previously linked legacy keys.
    for faction,prefix in [('Republic','rep'),('Empire','emp')]:
        for code,name,tier,marks,evidence in RANKS:
            config['roles'][f'{prefix}_{code}']={'name':f'{faction} | {name}','kind':'rank','faction':faction}
        config.setdefault('rank_ladders',{})[faction]=[f'{prefix}_{code}' for code in CODES]
    # Cancel requests made invalid by the inserted rank immediately below High Commander.
    with db:
        db.execute("UPDATE promotions SET status='cancelled: Marshal Commander added' WHERE status='pending' AND ((from_code='cmdr' AND to_code='hc') OR (from_code='col' AND to_code='mc') OR (from_code='mc' AND to_code='bg'))")
    def key(faction,code):return ('rep_' if faction=='Republic' else 'emp_')+code
    def require_owner(i):
        if not b.owner(i):raise ValueError('Only the Emperor / Discord server owner can do this.')
    def record(uid,faction):
        row=db.execute('SELECT rank_code,rank_since,service_since,adult,commander FROM personnel WHERE user_id=? AND faction=?',(uid,faction)).fetchone()
        if not row:raise ValueError('Owner must run /rank_register for this member first.')
        return row
    def current_keys(member,faction):
        owned={r.id for r in member.roles}
        return [k for k,v in config['roles'].items() if v['kind']=='rank' and v['faction']==faction and
                (row:=db.execute('SELECT role_id FROM bindings WHERE key=?',(k,)).fetchone()) and row[0] in owned]
    def matches(member,faction,code):
        if current_keys(member,faction)!=[key(faction,code)]:
            raise ValueError('Discord ranks and the registered record disagree. Owner must reconcile roles and use /rank_register.')
    def codes_for(member,faction=None):
        found=set()
        for f in ([faction] if faction else ['Republic','Empire']):
            for code in CODES:
                row=db.execute('SELECT role_id FROM bindings WHERE key=?',(key(f,code),)).fetchone()
                if row and any(r.id==row[0] for r in member.roles):found.add(code)
        return found
    def is_commander(member):return bool(codes_for(member)&{'cmdr','mc','hc'})
    def is_co(member,faction):return any(BY_CODE[c][2] in ('officer','high') for c in codes_for(member,faction))
    def proposal(pid):
        row=db.execute('SELECT user_id,faction,from_code,to_code,rank_since,final_code,jump,status,reason FROM promotions WHERE id=?',(pid,)).fetchone()
        if not row:raise ValueError('Unknown promotion ID.')
        return row
    async def check(pid,guild):
        uid,faction,src,dst,since,final,jump,status,reason=proposal(pid)
        if status!='pending':raise ValueError(f'Promotion is {status}, not pending.')
        person=record(uid,faction)
        if person[0]!=src or person[1]!=since:raise ValueError('Stale promotion: rank record changed; submit a new request.')
        member=await guild.fetch_member(uid);matches(member,faction,src)
        mark_count=db.execute('SELECT COUNT(*) FROM marks WHERE user_id=? AND faction=?',(uid,faction)).fetchone()[0]
        errors=requirements(src,dst,since,person[2],mark_count,person[3],time.time(),bool(jump),WAIT_DAYS)
        votes=db.execute('SELECT approver,kind,evidence FROM approvals WHERE proposal=?',(pid,)).fetchall()
        commanders=set();cos=set()
        for aid in {v[0] for v in votes}:
            if aid==uid:continue
            try:approver=await guild.fetch_member(aid)
            except discord.NotFound:continue
            if is_commander(approver):commanders.add(aid)
            if is_co(approver,faction):cos.add(aid)
        errors+=approval_errors(dst,commanders,cos,person[4],votes,guild.owner_id)
        return member,errors

    @b.bot.tree.command(description='Emperor: register an existing rank and verified service/rank start dates')
    @app_commands.choices(faction=b.FACTIONS)
    async def rank_register(i:discord.Interaction,member:discord.Member,faction:str,rank_started:str,service_started:str,reason:app_commands.Range[str,3,400]):
        require_owner(i)
        def parse(s):
            try:dt=datetime.strptime(s,'%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()
            except ValueError:raise ValueError('Use YYYY-MM-DD dates in UTC.')
            if dt>time.time():raise ValueError('Dates cannot be in the future.')
            return dt
        rs,ss=parse(rank_started),parse(service_started)
        if ss>rs:raise ValueError('Service start cannot be after rank start.')
        await i.response.defer(ephemeral=True)
        async with b.lock:
            member=await i.guild.fetch_member(member.id)
            found=current_keys(member,faction)
            canonical={key(faction,c):c for c in CODES}
            if len(found)!=1 or found[0] not in canonical:
                raise ValueError('Member must hold exactly one linked official rank role. Assign it manually in Discord for initial migration, then register.')
            code=canonical[found[0]]
            with db:
                db.execute('INSERT INTO personnel(user_id,faction,rank_code,rank_since,service_since) VALUES(?,?,?,?,?) ON CONFLICT(user_id,faction) DO UPDATE SET rank_code=excluded.rank_code,rank_since=excluded.rank_since,service_since=excluded.service_since',(member.id,faction,code,rs,ss))
                db.execute("UPDATE promotions SET status='cancelled: record changed' WHERE user_id=? AND faction=? AND status='pending'",(member.id,faction))
            b.audit(i.user.id,member.id,'rank_registered',f'{faction} {code}: {reason}')
        await i.followup.send('Rank/service dates registered. Pending requests were cancelled; adult verification and assigned Commander are preserved.',ephemeral=True)

    @b.bot.tree.command(description='Emperor: assign the member’s respective Commander and verify 18+ eligibility')
    @app_commands.choices(faction=b.FACTIONS)
    async def personnel_set(i:discord.Interaction,member:discord.Member,faction:str,commander:discord.Member,verified_adult:bool):
        require_owner(i);record(member.id,faction)
        commander=await i.guild.fetch_member(commander.id)
        if commander.id==member.id or not is_commander(commander):raise ValueError('Choose another member with a linked Commander, Marshal Commander or High Commander rank.')
        with db:db.execute('UPDATE personnel SET commander=?,adult=? WHERE user_id=? AND faction=?',(commander.id,int(verified_adult),member.id,faction))
        b.audit(i.user.id,member.id,'personnel_verified',f'{faction}; Commander {commander.id}; 18+ {verified_adult}')
        await i.response.send_message('Saved assigned Commander and 18+ verification. No birth date or ID document is stored.',ephemeral=True)

    @b.bot.tree.command(description='Staff: award one attendance mark for a unique event ID')
    @app_commands.choices(faction=b.FACTIONS)
    async def mark_award(i:discord.Interaction,member:discord.Member,faction:str,event_id:app_commands.Range[str,3,80]):
        b.staff(i);b.check_target(i,member);record(member.id,faction)
        event_id=event_id.strip().lower()
        if len(event_id)<3:raise ValueError('Use a meaningful shared event ID.')
        with db:
            cur=db.execute('INSERT OR IGNORE INTO marks VALUES(?,?,?,?,?)',(member.id,faction,event_id,i.user.id,time.time()))
        if not cur.rowcount:raise ValueError('This member already has a mark for this event ID.')
        b.audit(i.user.id,member.id,'mark_awarded',f'{faction}: {event_id}')
        await i.response.send_message('One mark awarded. Reusing this event ID cannot double-credit this member.',ephemeral=True)

    @b.bot.tree.command(description='Emperor: remove an incorrectly awarded attendance mark')
    @app_commands.choices(faction=b.FACTIONS)
    async def mark_revoke(i:discord.Interaction,member:discord.Member,faction:str,event_id:str,reason:app_commands.Range[str,3,400]):
        require_owner(i)
        with db:cur=db.execute('DELETE FROM marks WHERE user_id=? AND faction=? AND event=?',(member.id,faction,event_id.strip().lower()))
        b.audit(i.user.id,member.id,'mark_revoked',f'{faction} {event_id}: {reason}')
        await i.response.send_message(f'Removed {cur.rowcount} mark.',ephemeral=True)

    async def request(i,member,faction,reason,target=None):
        b.staff(i)
        await i.response.defer(ephemeral=True)
        async with b.lock:
            member=await i.guild.fetch_member(member.id);b.check_target(i,member)
            src,since,service,adult,commander=record(member.id,faction);matches(member,faction,src)
            n=CODES.index(src)
            if n==len(CODES)-1:raise ValueError('Already at High Commander. Emperor is the server owner, not a promotable rank.')
            dst=CODES[n+1];final=target or dst
            if final not in CODES or CODES.index(final)<=n:raise ValueError('Target must be a higher official rank code.')
            jump=CODES.index(final)>n+1
            if jump and (BY_CODE[src][2]!='enlisted' or BY_CODE[final][2]!='enlisted'):
                raise ValueError('Rank-jump queues are only available within Enlisted, up to Staff Sergeant.')
            count=db.execute('SELECT COUNT(*) FROM marks WHERE user_id=? AND faction=?',(member.id,faction)).fetchone()[0]
            if jump and count<BY_CODE[final][3]:raise ValueError('Insufficient marks for the requested final enlisted rank.')
            if db.execute("SELECT 1 FROM promotions WHERE user_id=? AND faction=? AND status='pending'",(member.id,faction)).fetchone():raise ValueError('This member already has a pending request. Use /promotion_status or cancel it first.')
            with db:cur=db.execute('INSERT INTO promotions(user_id,faction,from_code,to_code,rank_since,final_code,jump,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',(member.id,faction,src,dst,since,final,int(jump),reason,time.time()))
            pid=cur.lastrowid;b.audit(i.user.id,member.id,'promotion_requested',f'#{pid} {src}->{dst}; final {final}')
        await i.followup.send(f'Promotion #{pid} requested: {BY_CODE[src][1]} → {BY_CODE[dst][1]}. Final queued rank: {BY_CODE[final][1]}. Use /promotion_status for requirements.',ephemeral=True)
    b.request_rank_promotion=request

    @b.bot.tree.command(description='Staff: request a staged enlisted rank jump using accumulated marks')
    @app_commands.choices(faction=b.FACTIONS,target=[app_commands.Choice(name=BY_CODE[c][1],value=c) for c in CODES[2:8]])
    async def rank_queue(i:discord.Interaction,member:discord.Member,faction:str,target:str,reason:app_commands.Range[str,3,400]):
        await request(i,member,faction,reason,target)

    @b.bot.tree.command(description='Record a promotion approval, sponsorship or observed assessment')
    @app_commands.choices(kind=[app_commands.Choice(name=n,value=k) for k,n in [('commander','Commander approval'),('sponsor','CO sponsorship'),('combat_shadow','Commander combat shadow'),('emperor_shadow','Emperor On-Duty shadow'),('emperor','Emperor appointment')]])
    async def promotion_approve(i:discord.Interaction,proposal_id:int,kind:str,evidence:app_commands.Range[str,10,800]):
        await i.response.defer(ephemeral=True)
        async with b.lock:
            p=proposal(proposal_id);uid,faction,src,dst=p[:4]
            if p[7]!='pending':raise ValueError('This request is not pending.')
            if uid==i.user.id:raise ValueError('You cannot approve or sponsor yourself.')
            actor=await i.guild.fetch_member(i.user.id)
            if kind.startswith('emperor'):
                require_owner(i)
                if kind=='emperor' and dst not in ('cmdr','mc','hc'):raise ValueError('Appointment approval applies only to Commander / Marshal Commander / High Commander.')
                if kind=='emperor_shadow' and dst!='bg':raise ValueError('Emperor shadow applies only to Brigadier General.')
            elif kind=='sponsor':
                if BY_CODE[dst][2]!='nco' or not is_co(actor,faction):raise ValueError('Requires a same-era commissioned officer; only applies to NCO promotions.')
            else:
                if not is_commander(actor):raise ValueError('Requires a linked Commander, Marshal Commander or High Commander rank.')
                if kind=='combat_shadow' and (dst!='2lt' or record(uid,faction)[4]!=actor.id):raise ValueError('Only the assigned Commander can attest this Second Lieutenant combat shadow.')
            with db:db.execute('INSERT INTO approvals VALUES(?,?,?,?) ON CONFLICT(proposal,approver,kind) DO UPDATE SET evidence=excluded.evidence',(proposal_id,i.user.id,kind,evidence))
            b.audit(i.user.id,uid,'promotion_evidence',f'#{proposal_id} {kind}: {evidence}')
        await i.followup.send('Evidence recorded. It does not bypass wait times or other required approvals.',ephemeral=True)

    @b.bot.tree.command(description='Any Commander or Emperor: deny/challenge a pending promotion')
    async def promotion_deny(i:discord.Interaction,proposal_id:int,reason:app_commands.Range[str,3,800]):
        actor=await i.guild.fetch_member(i.user.id)
        if not b.owner(i) and not is_commander(actor):raise ValueError('Only a Commander, Marshal Commander, High Commander or Emperor may deny a promotion.')
        async with b.lock:
            p=proposal(proposal_id)
            if p[7]!='pending':raise ValueError('Not pending.')
            with db:db.execute("UPDATE promotions SET status='denied' WHERE id=?",(proposal_id,))
            b.audit(i.user.id,p[0],'promotion_denied',f'#{proposal_id}: {reason}')
        await i.response.send_message('Promotion denied; the staged queue stops here. A fresh request and new approvals are required.',ephemeral=True)

    @b.bot.tree.command(description='View promotion progress, remaining requirements and recorded assessments')
    async def promotion_status(i:discord.Interaction,proposal_id:int):
        p=proposal(proposal_id)
        if p[0]!=i.user.id:
            actor=await i.guild.fetch_member(i.user.id)
            if not b.owner(i) and not is_commander(actor):b.staff(i)
        await i.response.defer(ephemeral=True)
        errors=[]
        if p[7]=='pending':
            try:_,errors=await check(proposal_id,i.guild)
            except ValueError as e:errors=[str(e)]
        votes=db.execute('SELECT approver,kind,evidence FROM approvals WHERE proposal=?',(proposal_id,)).fetchall()
        body=f'#{proposal_id} | {p[1]} | {BY_CODE[p[2]][1]} -> {BY_CODE[p[3]][1]} | {p[7]}\nFinal queued rank: {BY_CODE[p[5]][1]}\nRequired evidence: {BY_CODE[p[3]][4] or "attendance / tenure"}\n'
        body+='\n'.join(errors) if errors else 'No remaining policy blockers (execution also checks Discord permissions).'
        body+='\n\nRecorded assessments:\n'+'\n'.join(f'{uid} | {kind} | {e}' for uid,kind,e in votes)
        await i.followup.send(file=discord.File(io.BytesIO(body.encode()),'promotion_status.txt'),ephemeral=True)

    @b.bot.tree.command(description='Staff: execute an eligible approved promotion; all requirements are rechecked')
    async def promotion_execute(i:discord.Interaction,proposal_id:int):
        b.staff(i)
        await i.response.defer(ephemeral=True)
        async with b.lock:
            p=proposal(proposal_id);uid,faction,src,dst,since,final,jump,status,reason=p
            member,errors=await check(proposal_id,i.guild)
            b.check_target(i,member)
            if dst in ('cmdr','mc','hc'):require_owner(i)
            if errors:raise ValueError('\n'.join(errors))
            role=b.role_for(i,key(faction,dst));old=b.role_for(i,key(faction,src))
            b.audit(i.user.id,uid,'promotion_execute_requested',str(proposal_id))
            await member.add_roles(role,reason=f'GUC approved promotion #{proposal_id}')
            try:await member.remove_roles(old,reason=f'GUC approved promotion #{proposal_id}')
            except discord.HTTPException:
                # Best-effort rollback. Failed rollback is visible as conflicting roles and blocks future promotions.
                try:await member.remove_roles(role,reason='GUC failed promotion rollback')
                except discord.HTTPException:pass
                raise
            now=time.time();next_id=None
            with db:
                db.execute('UPDATE personnel SET rank_code=?,rank_since=? WHERE user_id=? AND faction=?',(dst,now,uid,faction))
                db.execute("UPDATE promotions SET status='completed' WHERE id=?",(proposal_id,))
                if dst!=final:
                    nxt=CODES[CODES.index(dst)+1]
                    cur=db.execute('INSERT INTO promotions(user_id,faction,from_code,to_code,rank_since,final_code,jump,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',(uid,faction,dst,nxt,now,final,1,reason,now));next_id=cur.lastrowid
            b.audit(i.user.id,uid,'promotion_completed',f'#{proposal_id} {src}->{dst}')
        await i.followup.send(f'Promoted to {BY_CODE[dst][1]}.'+(f' Next staged request: #{next_id}; 3-day wait applies.' if next_id else ''),ephemeral=True)

    @b.bot.tree.command(description='View your rank, marks and pending requests; staff may inspect another member')
    @app_commands.choices(faction=b.FACTIONS)
    async def rank_status(i:discord.Interaction,faction:str,member:discord.Member|None=None):
        member=member or i.user
        if member.id!=i.user.id:b.staff(i)
        p=record(member.id,faction)
        marks=db.execute('SELECT COUNT(*) FROM marks WHERE user_id=? AND faction=?',(member.id,faction)).fetchone()[0]
        pending=db.execute("SELECT id FROM promotions WHERE user_id=? AND faction=? AND status='pending'",(member.id,faction)).fetchall()
        await i.response.send_message(f'{faction} | **{BY_CODE[p[0]][1]}**\nRank held since <t:{int(p[1])}:F>\nAttendance marks: **{marks}**\nPending requests: {", ".join(str(r[0]) for r in pending) or "None"}',ephemeral=True)

    # Rank ladder edits would invalidate policy; replace the old freeform commands.
    for name in ('rank_add','rank_order','rankdown'):
        b.bot.tree.remove_command(name)

    @b.bot.tree.command(description='Join a faction as Recruit and initialize your rank record')
    @app_commands.choices(faction=b.FACTIONS)
    async def enlist(i:discord.Interaction,faction:str):
        await i.response.defer(ephemeral=True)
        async with b.lock:
            member=await i.guild.fetch_member(i.user.id)
            if member.bot:raise ValueError('Bot accounts cannot enlist.')
            if db.execute('SELECT 1 FROM personnel WHERE user_id=? AND faction=?',(member.id,faction)).fetchone() or current_keys(member,faction):
                raise ValueError('You already have a record or rank in this faction. Ask staff to reconcile it if needed.')
            bound=db.execute('SELECT role_id FROM bindings WHERE key=?',(key(faction,'recruit'),)).fetchone()
            role=i.guild.get_role(bound[0]) if bound else None
            if not role or role.managed or role.is_default() or role.permissions.value or str(role.id) in config['staff_role_ids']:
                raise ValueError('Owner must link a safe Recruit role with /bind first.')
            if role>=i.guild.me.top_role or member.top_role>=i.guild.me.top_role:
                raise ValueError('Bot cannot manage this role/member. Owner should register existing members manually.')
            await member.add_roles(role,reason='GUC faction enlistment as Recruit')
            now=time.time()
            with db:db.execute('INSERT INTO personnel(user_id,faction,rank_code,rank_since,service_since) VALUES(?,?,?,?,?)',(member.id,faction,'recruit',now,now))
            b.audit(member.id,member.id,'enlisted',faction)
        await i.followup.send(f'Enlisted as {faction} Recruit. You can now use /startcombat or /startonduty, and /status create.',ephemeral=True)

    if not config.get('published_rules'):
        config['published_rules']=(
            '**GUC rank and command rules supplied by the owner**\n'
            'Emperor = server/group owner. Only the Emperor grants Commander, Marshal Commander and High Commander.\n'
            'High Command: age 18+; personnel obey High Command regardless of era. General needs 3 distinct Commanders; Lieutenant General needs 2. Brigadier General needs respective Commander approval and an Emperor-shadowed On-Duty assessment.\n'
            'Colonel through First Lieutenant: respective Commander approval with leadership capability and mindset evidence. Second Lieutenant: respective Commander must observe behavior, command and instruction while the candidate hosts combat. Any Commander may challenge or deny.\n'
            'Commissioned officers command their own era only. Warrant ranks require respective Commander approval. NCOs control some troopers in their own era; NCO promotion needs a same-era CO sponsor and evidence of leadership/combat skills (good for First Sergeant/Sergeant Major; amazing for Command Sergeant Major/Sergeant Major of the Era).\n'
            'Enlisted command no one except when appointed acting squad lead or ordered to gather people by higher-ups.\n'
            'Enlisted marks: Private 5 marks or 2 days in group; Private Second Class 10; Private First Class 15; Specialist 20; Corporal 25; Sergeant 30; Staff Sergeant 35. Recruit is the entry rank.\n'
            'One completed combat or On-Duty start/stop attendance earns one mark. Combat attendance also earns one mark. Repeating a stop command does not award extra marks.\n'
            '**Configured timing interpretation — owner confirmation needed:** destination-tier waits: Enlisted 1 day, NCO 3 days, Commissioned Officer 6 days, High Command 10 days. Warrant Officers provisionally use 6 days. Staged enlisted rank jumps hold each current rank for 3 days before the next step. Requests can remain pending, but waits are not silently bypassed.\n'
            'Use /structure for the full low-to-high ladder and /promotion_status for requirements. The owner can publish revised rules with /rules_set; changing displayed text does not change the executable promotion policy.')
