import time
import io
import discord
from discord import app_commands
from promotion_policy import BY_CODE

def install(b):
    db=b.db
    @b.bot.tree.command(description='Create a copyable status using your registered rank, e.g. CT-7567 Captain "Rex"')
    @app_commands.choices(faction=b.FACTIONS,prefix=[app_commands.Choice(name=v,value=v) for v in ['CT','CC','TK','CX']])
    async def member_status(i:discord.Interaction,faction:str,prefix:str,number:app_commands.Range[int,0,9999],nickname:app_commands.Range[str,1,50],member:discord.Member|None=None):
        member=member or i.user
        if member.id!=i.user.id:b.staff(i)
        row=db.execute('SELECT rank_code FROM personnel WHERE user_id=? AND faction=?',(member.id,faction)).fetchone()
        if not row:raise ValueError('Owner must register this member’s rank with /rank_register first.')
        nickname=nickname.strip()
        if not nickname or any(c in nickname for c in '\n\r"`') or any(ord(c)<32 for c in nickname):raise ValueError('Nickname cannot contain quotes, backticks or control characters.')
        text=f'{prefix}-{number:04d} {BY_CODE[row[0]][1]} "{nickname}"'
        await i.response.send_message(f'Copy this member status:\n```\n{text}\n```\nThis creates text for you to paste; Discord bots cannot set a user’s personal custom status.',ephemeral=True)

    db.execute('CREATE TABLE IF NOT EXISTS member_status_profiles(user_id INTEGER PRIMARY KEY,faction TEXT,prefix TEXT,number INTEGER,nickname TEXT)')
    status_group=app_commands.Group(name='status',description='Create and view your personal GUC member status')
    def render(uid,faction,prefix,number,nickname):
        row=db.execute('SELECT rank_code FROM personnel WHERE user_id=? AND faction=?',(uid,faction)).fetchone()
        if not row:raise ValueError('Your rank must be registered first. Ask staff to help you enlist or register.')
        return f'{prefix}-{number:04d} {BY_CODE[row[0]][1]} "{nickname}"'

    @status_group.command(name='create',description='Save your identity and create a copyable status for your account')
    @app_commands.choices(faction=b.FACTIONS,prefix=[app_commands.Choice(name=v,value=v) for v in ['CT','CC','TK','CX']])
    async def create(i:discord.Interaction,faction:str,prefix:str,number:app_commands.Range[int,0,9999],nickname:app_commands.Range[str,1,50]):
        nickname=nickname.strip()
        if not nickname or any(c in nickname for c in '\n\r"`') or any(ord(c)<32 for c in nickname):raise ValueError('Use a nickname without quotes, backticks or control characters.')
        text=render(i.user.id,faction,prefix,number,nickname)
        with db:db.execute('INSERT INTO member_status_profiles VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET faction=excluded.faction,prefix=excluded.prefix,number=excluded.number,nickname=excluded.nickname',(i.user.id,faction,prefix,number,nickname))
        await i.response.send_message(f'Your GUC status is saved:\n```\n{text}\n```\nCopy it into your account status. Use /status show after promotions to get your updated rank.',ephemeral=True)

    @status_group.command(name='show',description='Show your saved status with your current registered rank')
    async def show(i:discord.Interaction):
        row=db.execute('SELECT faction,prefix,number,nickname FROM member_status_profiles WHERE user_id=?',(i.user.id,)).fetchone()
        if not row:raise ValueError('Create your status first with /status create.')
        text=render(i.user.id,*row)
        await i.response.send_message(f'```\n{text}\n```\nCopy this into your account status; the bot cannot edit your personal account status.',ephemeral=True)

    b.bot.tree.add_command(status_group)
