"""Ban a server bot and its latest observed interaction user, without guessing."""
import discord
from discord import app_commands

def install(b):
    b.db.execute('''CREATE TABLE IF NOT EXISTS external_bot_usage(
        guild_id INTEGER,bot_id INTEGER,user_id INTEGER,interaction_id INTEGER,
        channel_id INTEGER,message_id INTEGER,PRIMARY KEY(guild_id,bot_id))''')
    @b.bot.event
    async def on_message(message):
        if not message.guild or message.guild.id!=b.GUILD_ID or not message.author.bot or message.author.id==b.bot.user.id:
            return
        meta=message.interaction_metadata
        if meta is None or meta.user.bot:return
        with b.db:
            b.db.execute('''INSERT INTO external_bot_usage VALUES(?,?,?,?,?,?)
                ON CONFLICT(guild_id,bot_id) DO UPDATE SET user_id=excluded.user_id,
                interaction_id=excluded.interaction_id,channel_id=excluded.channel_id,message_id=excluded.message_id
                WHERE excluded.interaction_id>external_bot_usage.interaction_id''',
                (message.guild.id,message.author.id,meta.user.id,meta.id,message.channel.id,message.id))

    @b.bot.tree.command(description='Ban a server bot and its latest observed interaction user; confirm required')
    @app_commands.default_permissions(ban_members=True)
    async def ban_external_bot(i:discord.Interaction,external_bot:discord.Member,
                               reason:app_commands.Range[str,3,400],confirm:bool=False):
        await i.response.defer(ephemeral=True)
        actor=await i.guild.fetch_member(i.user.id)
        me=await i.guild.fetch_member(b.bot.user.id)
        is_owner=actor.id==i.guild.owner_id
        if not is_owner and not(actor.guild_permissions.ban_members and actor.guild_permissions.manage_roles
                and any(str(r.id) in b.CONFIG['staff_role_ids'] for r in actor.roles)):
            raise ValueError('Requires configured staff access, Manage Roles, and Ban Members.')
        if not me.guild_permissions.ban_members:raise ValueError('GUC bot needs Ban Members permission.')
        target=await i.guild.fetch_member(external_bot.id)
        if not target.bot or target.id==me.id:raise ValueError('Choose an external server bot, not a human or the GUC bot.')
        row=b.db.execute('SELECT user_id,interaction_id,channel_id,message_id FROM external_bot_usage WHERE guild_id=? AND bot_id=?',(i.guild.id,target.id)).fetchone()
        if not row:raise ValueError('No verified interaction usage observed for this bot. No bans made. Private responses, prefix commands, and usage while GUC was offline cannot be identified.')
        uid,interaction_id,cid,mid=row
        evidence=f'https://discord.com/channels/{i.guild.id}/{cid}/{mid}'
        channel=i.guild.get_channel_or_thread(cid)
        if channel is None or not channel.permissions_for(actor).view_channel:
            raise ValueError('You must be able to view the source channel for this usage record.')
        try:human=await i.guild.fetch_member(uid)
        except discord.NotFound:raise ValueError('The latest observed user is no longer a server member. No bans made.')
        if human.bot:raise ValueError('Usage record is not a human. No bans made.')
        for member in (target,human):
            if member.id in (actor.id,me.id,i.guild.owner_id):raise ValueError('Cannot ban yourself, the GUC bot, or the server owner.')
            if member.top_role>=me.top_role:raise ValueError('GUC bot must be above both targets in the role hierarchy.')
            if not is_owner and member.top_role>=actor.top_role:raise ValueError('Both targets must be below your highest role.')
        stamp=int(discord.utils.snowflake_time(interaction_id).timestamp())
        if not confirm:
            await i.followup.send(f'Bot: {target.id}\nLatest observed user: {uid}\nInteraction: <t:{stamp}:F>\nEvidence: {evidence}\nOnly visible interaction responses are tracked; this may not be the latest use overall. Run again with confirm:true to ban the bot and the latest observed user at execution time.',ephemeral=True)
            return
        detail=f'bot={target.id}; user={uid}; interaction={interaction_id}; evidence={evidence}; {reason}'
        b.audit(actor.id,target.id,'external_bot_pair_ban_requested',detail)
        completed=[]
        for member in (target,human):
            try:await member.ban(reason=f'GUC moderator {actor.id}; interaction {interaction_id}: {reason}',delete_message_seconds=0)
            except discord.HTTPException:
                b.audit(actor.id,member.id,'external_bot_pair_ban_failed',detail)
                await i.followup.send(f'Ban failed for {member.id}. Successfully banned: {completed or "none"}. No remaining targets were banned. Message history preserved.',ephemeral=True)
                return
            completed.append(member.id)
            b.audit(actor.id,member.id,'external_bot_pair_ban_completed',detail)
        await i.followup.send(f'Banned bot {target.id} and latest observed interaction user {uid}. Evidence: {evidence}\nMessage history preserved.',ephemeral=True)
