"""Visible external bot/application activity, with an on-disk delivery queue."""
import logging
import discord
from discord.ext import tasks

LOG_CHANNEL_ID=1554625091520823366

def capture(b,message):
    if not message.guild or message.guild.id!=b.GUILD_ID:return
    if message.author.id==b.bot.user.id or message.channel.id==LOG_CHANNEL_ID:return
    app_id=getattr(message,'application_id',None)
    webhook_id=getattr(message,'webhook_id',None)
    if not (message.author.bot or app_id or webhook_id):return
    meta=getattr(message,'interaction_metadata',None)
    user=getattr(meta,'user',None)
    interaction_id=getattr(meta,'id',None)
    kind='App interaction' if meta else ('Webhook message' if webhook_id else 'Bot message')
    with b.db:
        b.db.execute('''INSERT OR IGNORE INTO external_activity_log
            (message_id,channel_id,author_id,author_name,application_id,user_id,interaction_id,kind,created)
            VALUES(?,?,?,?,?,?,?,?,?)''',(message.id,message.channel.id,message.author.id,
            str(message.author)[:200],app_id,user.id if user else None,interaction_id,kind,message.created_at.timestamp()))

async def deliver(b):
    rows=b.db.execute('''SELECT message_id,channel_id,author_id,author_name,application_id,user_id,interaction_id,kind,created FROM external_activity_log WHERE delivered=0 ORDER BY message_id LIMIT 10''').fetchall()
    if not rows:return
    guild=b.bot.get_guild(b.GUILD_ID)
    channel=guild.get_channel(LOG_CHANNEL_ID) if guild else None
    if not channel:
        logging.warning('External activity logging: channel %s unavailable; queued entries retained',LOG_CHANNEL_ID)
        return
    permissions=channel.permissions_for(guild.me)
    if not(permissions.view_channel and permissions.send_messages and permissions.embed_links):
        logging.warning('External activity logging: missing View Channel, Send Messages or Embed Links; queued entries retained')
        return
    for mid,cid,aid,name,app,uid,iid,kind,created in rows:
        embed=discord.Embed(title='External bot / app activity',color=0xe6a23c,
            description=f'**{kind}**\nAuthor: {discord.utils.escape_markdown(name)} (`{aid}`)')
        embed.add_field(name='Application ID',value=str(app) if app else 'Not supplied by Discord',inline=False)
        embed.add_field(name='Invoked by',value=f'<@{uid}> (`{uid}`)' if uid else 'Unknown — no interaction user supplied by Discord',inline=False)
        if iid:embed.add_field(name='Interaction ID',value=str(iid),inline=False)
        embed.add_field(name='Source',value=f'<#{cid}> • [View message](https://discord.com/channels/{b.GUILD_ID}/{cid}/{mid})\n<t:{int(created)}:F>',inline=False)
        embed.set_footer(text='Visible activity only • No automatic moderation action')
        try:
            sent=await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            logging.exception('External activity log delivery failed; queued entries retained')
            return
        with b.db:b.db.execute('UPDATE external_activity_log SET delivered=1,log_message_id=? WHERE message_id=?',(sent.id,mid))

def install(b):
    b.db.executescript('''CREATE TABLE IF NOT EXISTS external_activity_log(
        message_id INTEGER PRIMARY KEY,channel_id INTEGER,author_id INTEGER,author_name TEXT,
        application_id INTEGER,user_id INTEGER,interaction_id INTEGER,kind TEXT,created REAL,
        delivered INTEGER NOT NULL DEFAULT 0,log_message_id INTEGER);
        CREATE INDEX IF NOT EXISTS external_activity_pending ON external_activity_log(delivered,message_id);''')
    previous_message=b.bot.on_message
    previous_ready=b.bot.on_ready
    @b.bot.event
    async def on_message(message):
        capture(b,message)
        await previous_message(message)
    @tasks.loop(seconds=10)
    async def flush():
        try:await deliver(b)
        except Exception:logging.exception('External activity logging worker error')
    @flush.before_loop
    async def ready():await b.bot.wait_until_ready()
    b.external_activity_log_task=flush
    @b.bot.event
    async def on_ready():
        await previous_ready()
        if not flush.is_running():flush.start()
        logging.warning('External activity logging enabled for channel %s',LOG_CHANNEL_ID)
