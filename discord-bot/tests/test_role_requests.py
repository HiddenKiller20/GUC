import asyncio
import sqlite3
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
import discord
from discord import app_commands
import role_requests

class Requests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('CREATE TABLE bindings(key TEXT,role_id INTEGER); INSERT INTO bindings VALUES("cert_test",20); CREATE TABLE certs(user_id INTEGER,key TEXT,issuer INTEGER,reason TEXT,issued TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,key));')
        self.role=NS(id=20,name='Test certification',permissions=NS(value=0),managed=False,is_default=lambda:False)
        self.member=NS(id=100,bot=False,roles=[],add_roles=AsyncMock(),remove_roles=AsyncMock())
        self.actor=NS(id=200)
        self.client=discord.Client(intents=discord.Intents.none());self.client.tree=app_commands.CommandTree(self.client)
        self.b=NS(db=self.db,bot=self.client,lock=asyncio.Lock(),CONFIG={'staff_role_ids':[],'roles':{'cert_test':{'kind':'cert','name':'Test certification','faction':'Shared'},'rank_test':{'kind':'rank','name':'Rank','faction':'Republic'}}},registration_reviewer=AsyncMock(return_value=self.actor),audit=Mock(),check_target=Mock(),role_for=Mock(return_value=self.role))
        role_requests.install(self.b)
        self.guild=NS(get_role=lambda _:self.role,fetch_member=AsyncMock(return_value=self.member))
    async def asyncTearDown(self):self.db.close();await self.client.close()
    def interaction(self,user):return NS(user=user,guild=self.guild,response=NS(defer=AsyncMock(),send_message=AsyncMock()),followup=NS(send=AsyncMock()))
    async def submit(self):
        await self.client.tree.get_command('role_request').callback(self.interaction(self.member),'cert_test','Training completed')
        self.member.add_roles.assert_not_called()
        return self.db.execute('SELECT id FROM role_requests').fetchone()[0]
    async def test_approve_grants_cert_once(self):
        rid=await self.submit();cmd=self.client.tree.get_command('role_approve')
        await cmd.callback(self.interaction(self.actor),rid,'Verified training')
        self.member.add_roles.assert_awaited_once()
        self.assertEqual(self.db.execute('SELECT issuer FROM certs').fetchone()[0],200)
        with self.assertRaises(ValueError):await cmd.callback(self.interaction(self.actor),rid,'Again')
    async def test_no_self_approval_or_unapproved_access(self):
        rid=await self.submit();cmd=self.client.tree.get_command('role_approve')
        self.b.registration_reviewer.return_value=self.member
        with self.assertRaises(ValueError):await cmd.callback(self.interaction(self.member),rid,'Self')
        self.b.registration_reviewer.side_effect=ValueError('Manager required')
        with self.assertRaises(ValueError):await cmd.callback(self.interaction(self.actor),rid,'Unauthorized')
        self.member.add_roles.assert_not_called()
    async def test_rank_privilege_duplicate_and_binding_guards(self):
        cmd=self.client.tree.get_command('role_request');i=self.interaction(self.member)
        with self.assertRaises(ValueError):await cmd.callback(i,'rank_test','Bypass rankup')
        self.role.permissions.value=8
        with self.assertRaises(ValueError):await cmd.callback(i,'cert_test','Privileged')
        self.role.permissions.value=0
        rid=await self.submit()
        with self.assertRaises(ValueError):await cmd.callback(i,'cert_test','Duplicate')
        self.role.id=21
        with self.assertRaises(ValueError):await self.client.tree.get_command('role_approve').callback(self.interaction(self.actor),rid,'Rebound')
        self.member.add_roles.assert_not_called()
    async def test_deny_does_not_grant(self):
        rid=await self.submit()
        await self.client.tree.get_command('role_deny').callback(self.interaction(self.actor),rid,'Training incomplete')
        self.assertEqual(self.db.execute('SELECT status FROM role_requests').fetchone()[0],'denied')
        self.member.add_roles.assert_not_called()
