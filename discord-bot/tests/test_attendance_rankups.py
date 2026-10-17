import asyncio
import sqlite3
import unittest
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock,Mock
from attendance_rankups import earned_rank,promote
from test_permissions import Role

class AutoRanks(unittest.IsolatedAsyncioTestCase):
    def test_thresholds_and_cap(self):
        for marks,rank in [(4,None),(5,'pvt'),(10,'psc'),(15,'pfc'),(20,'spc'),(25,'cpl'),(30,'sgt'),(35,'ssg'),(500,'ssg')]:
            self.assertEqual(earned_rank('recruit',marks),rank)
        for current in ('ssg','sfc','cpt','hc'):self.assertIsNone(earned_rank(current,500))
        self.assertIsNone(earned_rank('sgt',5))
    async def test_promotes_confirmed_member_once(self):
        db=sqlite3.connect(':memory:')
        db.executescript("CREATE TABLE personnel(user_id INTEGER,faction TEXT,rank_code TEXT,rank_since REAL); CREATE TABLE marks(user_id INTEGER,faction TEXT); CREATE TABLE bindings(key TEXT,role_id INTEGER); CREATE TABLE promotions(user_id INTEGER,faction TEXT,status TEXT); INSERT INTO personnel VALUES(10,'Republic','recruit',0); INSERT INTO bindings VALUES('rep_recruit',1),('rep_ssg',2); INSERT INTO promotions VALUES(10,'Republic','pending');")
        db.executemany('INSERT INTO marks VALUES(10,?)',[('Republic',)]*35)
        old=Role(1,1);new=Role(2,2);old.name='Recruit';new.name='Staff Sergeant'
        member=NS(bot=False,roles=[old],top_role=old,add_roles=AsyncMock(),remove_roles=AsyncMock())
        guild=NS(owner_id=99,me=NS(id=999,top_role=Role(3,100),guild_permissions=NS(manage_roles=True)),fetch_member=AsyncMock(return_value=member),get_role=lambda rid:{1:old,2:new}.get(rid))
        b=NS(db=db,lock=asyncio.Lock(),CONFIG={'staff_role_ids':[],'roles':{'rep_recruit':{'kind':'rank','faction':'Republic'},'rep_ssg':{'kind':'rank','faction':'Republic'}}},audit=Mock())
        self.assertIsNone(await promote(b,guild,20,'Republic'))
        self.assertIsNone(await promote(b,guild,10,'Empire'))
        new.permissions.value=8
        with self.assertRaises(ValueError):await promote(b,guild,10,'Republic')
        member.add_roles.assert_not_called();new.permissions.value=0
        self.assertEqual(await promote(b,guild,10,'Republic'),'Staff Sergeant')
        self.assertEqual(db.execute('SELECT rank_code FROM personnel').fetchone()[0],'ssg')
        self.assertTrue(db.execute('SELECT status FROM promotions').fetchone()[0].startswith('cancelled'))
        self.assertIsNone(await promote(b,guild,10,'Republic'))
        member.add_roles.assert_awaited_once();member.remove_roles.assert_awaited_once()
        db.close()
