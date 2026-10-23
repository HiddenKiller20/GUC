import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
import discord
from join_guard import check_join
class JoinGuard(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.me=NS(id=99,top_role=100,guild_permissions=NS(ban_members=True))
  self.member=NS(id=3,bot=False,top_role=10,ban=AsyncMock())
  self.guild=NS(id=1,owner_id=50,fetch_member=AsyncMock(side_effect=lambda uid:self.me if uid==99 else self.member))
  self.member.guild=self.guild
  self.source=NS(unavailable=False,fetch_member=AsyncMock(return_value=NS(id=3)))
  self.b=NS(GUILD_ID=1,bot=NS(user=NS(id=99),get_guild=Mock(return_value=self.source)),audit=Mock())
 async def test_confirmed_membership_bans(self):
  self.assertTrue(await check_join(self.b,self.member));self.member.ban.assert_awaited_once();self.assertEqual(self.member.ban.call_args.kwargs['delete_message_seconds'],0)
 async def test_missing_source_never_bans(self):
  self.b.bot.get_guild.return_value=None
  self.assertFalse(await check_join(self.b,self.member));self.member.ban.assert_not_called()
 async def test_negative_membership_and_api_failure_never_ban(self):
  for error in [discord.NotFound(NS(status=404,reason='Not Found'),{'code':10007,'message':'Unknown Member'}),discord.Forbidden(NS(status=403,reason='Forbidden'),'No access')]:
   self.source.fetch_member.side_effect=error
   self.assertFalse(await check_join(self.b,self.member));self.member.ban.assert_not_called()
 async def test_hierarchy_and_permissions(self):
  self.member.top_role=100
  self.assertFalse(await check_join(self.b,self.member));self.member.ban.assert_not_called()
  self.member.top_role=1;self.me.guild_permissions.ban_members=False
  self.assertFalse(await check_join(self.b,self.member));self.member.ban.assert_not_called()
 async def test_other_guild_bots_and_owner_skipped(self):
  self.guild.id=2;self.assertFalse(await check_join(self.b,self.member))
  self.guild.id=1;self.member.bot=True;self.assertFalse(await check_join(self.b,self.member))
  self.member.bot=False;self.member.id=50;self.assertFalse(await check_join(self.b,self.member))
  self.source.fetch_member.assert_not_called()
