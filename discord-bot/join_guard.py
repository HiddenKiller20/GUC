"""Check new GUC arrivals against one explicitly configured external guild."""
import logging
import discord

BLOCKED_GUILD_ID=1524825517344292977

async def check_join(b,member):
    if member.guild.id!=b.GUILD_ID or member.bot or member.id==member.guild.owner_id:
        return False
    source=b.bot.get_guild(BLOCKED_GUILD_ID)
    if source is None or source.unavailable:
        b.audit(b.bot.user.id,member.id,'join_guard_unverified','Source guild unavailable; no ban')
        logging.warning('Join guard: source guild %s unavailable; no ban',BLOCKED_GUILD_ID)
        return False
    try:
        await source.fetch_member(member.id)
    except discord.NotFound as exc:
        if exc.code==10007:  # Unknown Member is the only definitive negative.
            return False
        b.audit(b.bot.user.id,member.id,'join_guard_unverified',f'Source lookup error {exc.code}; no ban')
        return False
    except discord.HTTPException as exc:
        b.audit(b.bot.user.id,member.id,'join_guard_unverified',f'Source lookup error {exc.status}; no ban')
        logging.warning('Join guard: membership lookup failed; no ban (%s)',exc.status)
        return False
    try:
        current=await member.guild.fetch_member(member.id)
        me=await member.guild.fetch_member(b.bot.user.id)
        if not me.guild_permissions.ban_members or current.top_role>=me.top_role:
            b.audit(me.id,current.id,'join_guard_blocked','Missing Ban Members permission or role hierarchy')
            return False
        reason=f'GUC join policy: confirmed current member of guild {BLOCKED_GUILD_ID}'
        b.audit(me.id,current.id,'join_guard_ban_requested',reason)
        await current.ban(reason=reason,delete_message_seconds=0)
        b.audit(me.id,current.id,'join_guard_ban_completed',reason)
        logging.info('Join guard banned member %s after confirmed membership in %s',current.id,BLOCKED_GUILD_ID)
        return True
    except discord.HTTPException as exc:
        b.audit(b.bot.user.id,member.id,'join_guard_ban_failed',f'Discord error {exc.status}')
        logging.warning('Join guard: ban failed (%s)',exc.status)
        return False

def install(b):
    previous_join=b.bot.on_member_join
    previous_ready=b.bot.on_ready
    @b.bot.event
    async def on_member_join(member):
        if await check_join(b,member):
            return
        await previous_join(member)
    @b.bot.event
    async def on_ready():
        await previous_ready()
        source=b.bot.get_guild(BLOCKED_GUILD_ID)
        if source is None or source.unavailable:
            logging.warning('Join guard INACTIVE: bot cannot access source guild %s. No membership-based bans until access is available.',BLOCKED_GUILD_ID)
        else:
            logging.warning('Join guard READY: source guild %s visible; new arrivals will be checked via REST.',BLOCKED_GUILD_ID)
