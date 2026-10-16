"""Member role requests reviewed by Server Managers."""
import time
import discord
from discord import app_commands


def install(b):
    db=b.db
    db.executescript('''CREATE TABLE IF NOT EXISTS role_requests(
        id INTEGER PRIMARY KEY,user_id INTEGER,role_key TEXT,role_id INTEGER,reason TEXT,
        status TEXT DEFAULT 'pending',reviewer INTEGER,review_reason TEXT,created REAL);
        CREATE UNIQUE INDEX IF NOT EXISTS pending_role_request ON role_requests(user_id,role_key) WHERE status='pending';''')
    def spec(key):
        info=b.CONFIG['roles'].get(key)
        if not info:raise ValueError('Unknown role. Use /catalog to find a role key.')
        if info['kind']=='rank':raise ValueError('Ranks require /rank_register, /enlist, or the /rankup approval workflow.')
        return info
    async def choices(i,current):
        return [app_commands.Choice(name=f'{v["name"]} ({k})'[:100],value=k) for k,v in b.CONFIG['roles'].items() if v['kind']!='rank' and current.casefold() in (k+' '+v['name']).casefold()][:25]

    @b.bot.tree.command(description='Request a battalion, certification, or other catalog role for yourself')
    @app_commands.autocomplete(key=choices)
    async def role_request(i:discord.Interaction,key:str,reason:app_commands.Range[str,3,400]):
        spec(key)
        if i.user.bot:raise ValueError('Bot accounts cannot request roles.')
        await i.response.defer(ephemeral=True)
        async with b.lock:
            bound=db.execute('SELECT role_id FROM bindings WHERE key=?',(key,)).fetchone()
            role=i.guild.get_role(bound[0]) if bound else None
            protected={str(x) for x in b.CONFIG['staff_role_ids']}|{str(b.CONFIG.get('server_manager_role_id',''))}
            if not role or role.is_default() or role.managed or role.permissions.value or str(role.id) in protected or role.name.casefold()=='server manager':
                raise ValueError('This role is not requestable. Ask the owner to link a safe catalog role.')
            member=await i.guild.fetch_member(i.user.id)
            if role in member.roles:raise ValueError('You already hold this role.')
            if db.execute("SELECT 1 FROM role_requests WHERE user_id=? AND role_key=? AND status='pending'",(member.id,key)).fetchone():raise ValueError('You already have a pending request for this role.')
            with db:cur=db.execute('INSERT INTO role_requests(user_id,role_key,role_id,reason,created) VALUES(?,?,?,?,?)',(member.id,key,role.id,reason,time.time()))
            b.audit(member.id,member.id,'role_requested',f'#{cur.lastrowid} {key}: {reason}')
        await i.followup.send(f'Role request #{cur.lastrowid} submitted for {role.name}. A Server Manager must approve it. Use /role_request_status to check progress.',ephemeral=True)

    async def show(i,own,page):
        if not own:await b.registration_reviewer(i)
        where='user_id=?' if own else "status='pending'"
        args=[i.user.id] if own else []
        count=db.execute('SELECT COUNT(*) FROM role_requests WHERE '+where,args).fetchone()[0]
        pages=max(1,(count+4)//5)
        if page>pages:raise ValueError(f'Choose a page between 1 and {pages}.')
        rows=db.execute('SELECT id,user_id,role_key,reason,status,review_reason FROM role_requests WHERE '+where+' ORDER BY id DESC LIMIT 5 OFFSET ?',[*args,(page-1)*5]).fetchall()
        embed=discord.Embed(title='Your role requests' if own else 'Pending role requests',color=0x2459a6)
        for rid,uid,key,reason,status,review_reason in rows:
            embed.add_field(name=f'#{rid} • {key} • {status}',value=f'Member: <@{uid}>\nReason: {reason}\nReview: {review_reason or "Pending"}',inline=False)
        if not rows:embed.description='No requests found.'
        embed.set_footer(text=f'Page {page}/{pages}')
        await i.response.send_message(embed=embed,ephemeral=True)

    @b.bot.tree.command(description='Check your own role requests and review results')
    async def role_request_status(i:discord.Interaction,page:app_commands.Range[int,1,10000]=1):await show(i,True,page)

    @b.bot.tree.command(description='Server Manager: view pending role requests')
    async def role_requests(i:discord.Interaction,page:app_commands.Range[int,1,10000]=1):await show(i,False,page)

    async def review(i,request_id,reason,approve):
        await i.response.defer(ephemeral=True)
        async with b.lock:
            actor=await b.registration_reviewer(i)
            row=db.execute('SELECT user_id,role_key,role_id,status FROM role_requests WHERE id=?',(request_id,)).fetchone()
            if not row or row[3]!='pending':raise ValueError('Unknown or already reviewed request.')
            uid,key,rid,_=row
            if uid==actor.id:raise ValueError('Another Server Manager must review your request.')
            if approve:
                info=spec(key)
                member=await i.guild.fetch_member(uid)
                b.check_target(i,member)
                role=b.role_for(i,key)
                if role.id!=rid:raise ValueError('Role binding changed. Deny this request and ask the member to resubmit.')
                if str(role.id)==str(b.CONFIG.get('server_manager_role_id','')) or role.name.casefold()=='server manager':raise ValueError('Server Manager roles cannot be granted through requests.')
                removals=[]
                if info['kind']=='battalion':
                    for other,meta in b.CONFIG['roles'].items():
                        if other!=key and (meta['kind'],meta['faction'])==('battalion',info['faction']):
                            bound=db.execute('SELECT role_id FROM bindings WHERE key=?',(other,)).fetchone()
                            old=i.guild.get_role(bound[0]) if bound else None
                            if old in member.roles:b.check_role(i,old);removals.append(old)
                await member.add_roles(role,reason=f'GUC role request #{request_id}: {reason}')
                if removals:await member.remove_roles(*removals,reason=f'GUC role request #{request_id} battalion replacement')
            status='approved' if approve else 'denied'
            with db:
                if approve and info['kind']=='cert':
                    db.execute('INSERT INTO certs(user_id,key,issuer,reason) VALUES(?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET issuer=excluded.issuer,reason=excluded.reason,issued=CURRENT_TIMESTAMP',(uid,key,actor.id,reason))
                db.execute('UPDATE role_requests SET status=?,reviewer=?,review_reason=? WHERE id=?',(status,actor.id,reason,request_id))
            b.audit(actor.id,uid,'role_request_'+status,f'#{request_id} {key}: {reason}')
        await i.followup.send(f'Role request #{request_id} {status}.',ephemeral=True)

    @b.bot.tree.command(description='Server Manager: approve a role request and grant the role')
    async def role_approve(i:discord.Interaction,request_id:int,reason:app_commands.Range[str,3,400]):await review(i,request_id,reason,True)

    @b.bot.tree.command(description='Server Manager: deny a role request')
    async def role_deny(i:discord.Interaction,request_id:int,reason:app_commands.Range[str,3,400]):await review(i,request_id,reason,False)
