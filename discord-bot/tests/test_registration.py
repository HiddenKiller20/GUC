import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from test_permissions import bot, Role

class Registration(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for table in ('personnel','rank_registrations','bindings'):
            bot.db.execute(f'DELETE FROM {table}')
        self.manager=Role(500,80)
        self.manager.name='Server Manager'
        self.rank=Role(501,10)
        self.member=NS(id=700,bot=False,roles=[self.rank],top_role=self.rank)
        self.reviewer=NS(id=701,roles=[self.manager],top_role=self.manager)
        self.guild=NS(roles=[self.manager,self.rank],get_role=lambda rid:self.manager if rid==500 else self.rank,fetch_member=AsyncMock(return_value=self.member))
        bot.CONFIG['server_manager_role_id']='500'
        bot.db.execute("INSERT INTO bindings VALUES('rep_cpt',501)")
        bot.db.commit()
    def interaction(self,user):
        return NS(user=user,guild=self.guild,response=NS(defer=AsyncMock(),send_message=AsyncMock()),followup=NS(send=AsyncMock()))
    async def submit(self):
        i=self.interaction(self.member)
        await bot.bot.tree.get_command('rank_register').callback(i,'Republic','2026-01-01','2025-01-01','Existing rank')
        self.assertEqual(bot.db.execute('SELECT COUNT(*) FROM personnel').fetchone()[0],0)
        return bot.db.execute('SELECT id FROM rank_registrations').fetchone()[0]
    async def test_requires_manager_then_confirms_once(self):
        rid=await self.submit()
        i=self.interaction(self.reviewer)
        with self.assertRaises(ValueError):
            await bot.bot.tree.get_command('rank_confirm').callback(i,rid,'Verified')
        self.guild.fetch_member=AsyncMock(side_effect=lambda uid:self.reviewer if uid==701 else self.member)
        await bot.bot.tree.get_command('rank_confirm').callback(i,rid,'Verified')
        self.assertEqual(bot.db.execute('SELECT rank_code FROM personnel').fetchone()[0],'cpt')
        with self.assertRaises(ValueError):await bot.bot.tree.get_command('rank_confirm').callback(i,rid,'Verified')
    async def test_self_review_blocked(self):
        rid=await self.submit()
        self.member.roles.append(self.manager)
        with self.assertRaises(ValueError):await bot.bot.tree.get_command('rank_confirm').callback(self.interaction(self.member),rid,'Verified')
        self.assertEqual(bot.db.execute('SELECT COUNT(*) FROM personnel').fetchone()[0],0)
    async def test_deny_and_enlist_stay_unregistered(self):
        rid=await self.submit()
        self.guild.fetch_member=AsyncMock(return_value=self.reviewer)
        await bot.bot.tree.get_command('rank_deny').callback(self.interaction(self.reviewer),rid,'Not verified')
        self.assertEqual(bot.db.execute('SELECT status FROM rank_registrations').fetchone()[0],'denied')
        self.member.roles=[]
        self.guild.fetch_member=AsyncMock(return_value=self.member)
        await bot.bot.tree.get_command('enlist').callback(self.interaction(self.member),'Republic')
        self.assertEqual(bot.db.execute('SELECT COUNT(*) FROM personnel').fetchone()[0],0)
