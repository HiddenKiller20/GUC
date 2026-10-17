"""Staff announcements with a saved default channel and event templates."""
import discord
from discord import app_commands


def install(b):
    def destination(i,channel):
        channel=channel or i.guild.get_channel(int(b.CONFIG.get('announcement_channel_id') or 0))
        if not isinstance(channel,discord.TextChannel) or channel.guild.id!=i.guild.id:
            raise ValueError('Choose a text channel or ask the owner to use /announcement_setup.')
        actor=channel.permissions_for(i.user);bot=channel.permissions_for(i.guild.me)
        if not(actor.view_channel and actor.send_messages):raise ValueError('You must be able to view and send in the announcement channel.')
        if not(bot.view_channel and bot.send_messages and bot.embed_links):raise ValueError('Bot needs View Channel, Send Messages, and Embed Links there.')
        return channel

    async def post(i,title,message,channel,preview,color=0x2459a6):
        b.staff(i)
        channel=destination(i,channel)
        embed=discord.Embed(title=title,description=message,color=color,timestamp=discord.utils.utcnow())
        embed.set_footer(text='The Galactic Unification Corps')
        if preview:
            await i.response.send_message(content=f'Preview for {channel.mention}. Run again with preview:false to post.',embed=embed,ephemeral=True,allowed_mentions=discord.AllowedMentions.none())
            return
        await i.response.defer(ephemeral=True)
        sent=await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
        b.audit(i.user.id,channel.id,'announcement',f'{title} | message {sent.id}')
        await i.followup.send(f'Announcement posted: {sent.jump_url}',ephemeral=True)

    b.bot.tree.remove_command('announce')
    @b.bot.tree.command(description='Staff: post a general announcement, or preview it privately')
    async def announce(i:discord.Interaction,title:app_commands.Range[str,1,200],message:app_commands.Range[str,1,1800],channel:discord.TextChannel|None=None,preview:bool=False):
        await post(i,title,message,channel,preview)

    @b.bot.tree.command(description='Owner: choose the default announcement channel')
    async def announcement_setup(i:discord.Interaction,channel:discord.TextChannel):
        if not b.owner(i):raise ValueError('Only the owner can configure the announcement channel.')
        destination(i,channel)
        b.setting('announcement_channel_id',str(channel.id))
        await i.response.send_message(f'Default announcement channel: {channel.mention}',ephemeral=True)

    async def event(i,faction,details,channel,preview,kind):
        title=f'{faction} — {kind}'
        instructions={'Combat':'Report for combat. Log your attendance with /startcombat when you arrive and /stopcombat when you leave.',
                      'On-Duty':'Report for duty. Log your attendance with /startonduty when you arrive and /stoponduty when you leave.',
                      'Training':'Report for training and follow your instructor’s directions. Certifications are granted after staff verification.'}
        await post(i,title,f'{details}\n\n{instructions[kind]}',channel,preview,0x2459a6 if faction=='Republic' else 0xc0392b)

    @b.bot.tree.command(description='Staff: announce a combat event with attendance instructions')
    @app_commands.choices(faction=b.FACTIONS)
    async def announce_combat(i:discord.Interaction,faction:str,details:app_commands.Range[str,1,1800],channel:discord.TextChannel|None=None,preview:bool=False):
        await event(i,faction,details,channel,preview,'Combat')

    @b.bot.tree.command(description='Staff: announce On-Duty with attendance instructions')
    @app_commands.choices(faction=b.FACTIONS)
    async def announce_onduty(i:discord.Interaction,faction:str,details:app_commands.Range[str,1,1800],channel:discord.TextChannel|None=None,preview:bool=False):
        await event(i,faction,details,channel,preview,'On-Duty')

    @b.bot.tree.command(description='Staff: announce a faction training session')
    @app_commands.choices(faction=b.FACTIONS)
    async def announce_training(i:discord.Interaction,faction:str,details:app_commands.Range[str,1,1800],channel:discord.TextChannel|None=None,preview:bool=False):
        await event(i,faction,details,channel,preview,'Training')
