"""Local setup only. Never paste a bot token into a chat."""
from pathlib import Path
from getpass import getpass
import discord
from urllib.parse import urlencode

root=Path(__file__).parent
print('GUC Bot Setup — create your app at https://discord.com/developers/applications')
app=input('Application ID (General Information): ').strip()
guild=input('Discord server ID: ').strip()
if not app.isdigit() or not guild.isdigit():
    raise SystemExit('IDs must contain digits only.')
perms=discord.Permissions(view_channel=True,send_messages=True,embed_links=True,
    attach_files=True,read_message_history=True,manage_roles=True,manage_channels=True,
    moderate_members=True,kick_members=True,ban_members=True)
url='https://discord.com/oauth2/authorize?'+urlencode({'client_id':app,'scope':'bot applications.commands','permissions':perms.value,'guild_id':guild,'disable_guild_select':'true'})
print('\nInvite your bot:\n'+url)
path=root/'.env'
if path.exists():
    raise SystemExit('.env already exists. Edit it locally if needed; not overwritten.')
token=getpass('\nBot token (hidden input; saved locally in .env): ').strip()
if not token or any(c.isspace() for c in token):
    raise SystemExit('Invalid empty token or whitespace.')
path.write_text(f'DISCORD_TOKEN={token}\nDISCORD_GUILD_ID={guild}\n')
try:
    path.chmod(0o600)
except OSError:
    pass
print('\nSaved. Enable Server Members Intent in the Developer Portal, then run python bot.py.')
