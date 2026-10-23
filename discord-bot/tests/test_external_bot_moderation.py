import asyncio,sqlite3,unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
import discord
from discord import app_commands
import external_bot_moderation
class Tests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.db=sqlite3.connect(':memory:');self.client=discord.Client(intents=discord.Intents.default());self.client.tree=app_commands.CommandTree(self.client);self.client._connection.user=NS(id=99)
  self.b=NS(db=self.db,bot=self.client,GUILD_ID=1,CONFIG={'staff_role_ids':['5']},audit=Mock());external_bot_moderation.install(self.b)
  def member(uid,bot,pos):return NS(id=uid,bot=bot,top_role=pos,roles=[NS(id=5)],guild_permissions=NS(ban_members=True,manage_roles=True),ban=AsyncMock())
  self.actor=member(1,False,80);self.me=member(99,True,100);self.target=member(2,True,20);self.human=member(3,False,10);self.other=member(4,False,10)
  members={x.id:x for x in (self.actor,self.me,self.target,self.human,self.other)}
  self.channel=NS(id=10,permissions_for=lambda _:NS(view_channel=True))
  self.guild=NS(id=1,owner_id=50,fetch_member=AsyncMock(side_effect=lambda uid:members[uid]),get_channel_or_thread=lambda _:self.channel)
  self.i=NS(user=self.actor,guild=self.guild,response=NS(defer=AsyncMock()),followup=NS(send=AsyncMock()))
 async def asyncTearDown(self):await self.client.close();self.db.close()
 async def observe(self,uid=3,iid=100):
  await self.client.on_message(NS(guild=self.guild,author=self.target,interaction_metadata=NS(user=NS(id=uid,bot=False),id=iid),channel=self.channel,id=iid+10))
 async def run_command(self,confirm=True):await self.client.tree.get_command('ban_external_bot').callback(self.i,self.target,'Test reason',confirm)
 async def test_newest_interaction_not_latest_followup(self):
  await self.observe(3,100);await self.observe(4,200);await self.observe(3,100)
  await self.run_command();self.target.ban.assert_awaited_once();self.other.ban.assert_awaited_once();self.human.ban.assert_not_called()
 async def test_no_record_and_preview_make_no_bans(self):
  with self.assertRaises(ValueError):await self.run_command()
  await self.observe();await self.run_command(False);self.target.ban.assert_not_called();self.human.ban.assert_not_called()
 async def test_prevalidates_both_targets(self):
  await self.observe();self.human.top_role=100
  with self.assertRaises(ValueError):await self.run_command()
  self.target.ban.assert_not_called()
 async def test_permissions_and_self_protection(self):
  await self.observe();self.actor.guild_permissions.ban_members=False
  with self.assertRaises(ValueError):await self.run_command()
  self.actor.guild_permissions.ban_members=True;await self.observe(1,200)
  with self.assertRaises(ValueError):await self.run_command()
  self.target.ban.assert_not_called()
 async def test_bot_failure_does_not_ban_user(self):
  await self.observe();self.target.ban.side_effect=discord.Forbidden(NS(status=403,reason='Forbidden'),'Blocked')
  await self.run_command();self.human.ban.assert_not_called();self.assertIn('none',self.i.followup.send.call_args.args[0])
 async def test_ignores_messages_without_metadata(self):
  await self.client.on_message(NS(guild=self.guild,author=self.target,interaction_metadata=None))
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM external_bot_usage').fetchone()[0],0)
if __name__=='__main__':unittest.main()
