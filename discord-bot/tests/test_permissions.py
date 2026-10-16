import os
import sys
import tempfile
import unittest
from types import SimpleNamespace as NS
from pathlib import Path

_tmp=tempfile.TemporaryDirectory()
os.environ['DATA_DIR']=_tmp.name
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bot

class Role:
    def __init__(self,id,pos,permissions=0):
        self.id=id
        self.pos=pos
        self.managed=False
        self.permissions=NS(value=permissions)
    def __ge__(self,other): return self.pos>=other.pos
    def is_default(self): return False

class Guards(unittest.TestCase):
    def setUp(self):
        self.i=NS(user=NS(id=2,top_role=Role(2,50),roles=[Role(10,50)],guild_permissions=NS(manage_roles=True)),
                  guild=NS(owner_id=1,me=NS(top_role=Role(99,100))))
        bot.CONFIG['staff_role_ids']=['10']
    def test_staff_requires_permission_and_allowlist(self):
        bot.staff(self.i)
        self.i.user.guild_permissions.manage_roles=False
        with self.assertRaises(ValueError):bot.staff(self.i)
        self.i.user.guild_permissions.manage_roles=True
        self.i.user.roles=[]
        with self.assertRaises(ValueError):bot.staff(self.i)
    def test_self_and_equal_target_blocked(self):
        for uid,pos in [(2,1),(3,50),(3,51),(1,1)]:
            with self.assertRaises(ValueError):bot.check_target(self.i,NS(id=uid,bot=False,top_role=Role(4,pos)))
        bot.check_target(self.i,NS(id=3,bot=False,top_role=Role(4,10)))
    def test_privileged_and_high_roles_blocked(self):
        for role in [Role(5,1,8),Role(5,50),Role(5,101),Role(10,1)]:
            with self.assertRaises(ValueError):bot.check_role(self.i,role)
        bot.check_role(self.i,Role(5,10))
    def test_all_command_payloads(self):
        commands=bot.bot.tree.get_commands()
        self.assertEqual(len(commands),64)
        for command in commands: self.assertIsInstance(command.to_dict(bot.bot.tree),dict)

if __name__=='__main__':unittest.main()

class RankBypass(unittest.IsolatedAsyncioTestCase):
    async def test_generic_assign_and_revoke_cannot_change_ranks(self):
        from unittest.mock import AsyncMock,patch
        i=NS(response=NS(defer=AsyncMock()),guild=NS(fetch_member=AsyncMock(return_value=NS(id=3))),user=NS(id=2))
        member=NS(id=3)
        bot.CONFIG['roles']['test_rank']={'kind':'rank','faction':'Republic','name':'test'}
        try:
            with patch.object(bot,'staff'),patch.object(bot,'check_target'),patch.object(bot,'role_for',return_value=NS(name='test')):
                with self.assertRaises(ValueError):await bot.assign.callback(i,member,'test_rank','test reason')
                with self.assertRaises(ValueError):await bot.revoke.callback(i,member,'test_rank','test reason')
        finally:bot.CONFIG['roles'].pop('test_rank',None)

    async def test_no_voice_tracking_and_status_commands_exist(self):
        self.assertFalse(hasattr(bot.bot,'on_voice_state_update'))
        self.assertIsNotNone(bot.bot.tree.get_command('startcombat'))
        self.assertIsNotNone(bot.bot.tree.get_command('stopcombat'))
        self.assertIsNotNone(bot.bot.tree.get_command('startonduty'))
        self.assertIsNotNone(bot.bot.tree.get_command('stoponduty'))
        self.assertIsNone(bot.bot.tree.get_command('start'))
        self.assertIsNone(bot.bot.tree.get_command('stop'))
        self.assertIsNotNone(bot.bot.tree.get_command('status').get_command('create'))
