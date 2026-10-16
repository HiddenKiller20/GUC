import sqlite3
import unittest
from strikes import StrikeStore

class Strikes(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:');self.store=StrikeStore(self.db)
    def test_cap_three_and_other_member_independent(self):
        for n in range(1,4):self.assertEqual(self.store.add(1,9,'reason',n)[1],n)
        with self.assertRaises(ValueError):self.store.add(1,9,'fourth',4)
        self.assertEqual(self.store.active_count(1),3)
        self.assertEqual(self.store.add(2,9,'another member',5)[1],1)
    def test_remove_preserves_history_and_frees_slot(self):
        ids=[self.store.add(1,9,'reason',n)[0] for n in range(3)]
        self.store.remove(ids[1],9,'appeal accepted',5)
        self.assertEqual(self.store.active_count(1),2)
        sid,count=self.store.add(1,9,'new violation',6)
        self.assertEqual(count,3)
        self.assertGreater(sid,max(ids))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM strikes').fetchone()[0],4)
        with self.assertRaises(ValueError):self.store.remove(ids[1],9,'repeat',7)
    def test_survives_restart(self):
        self.store.add(1,9,'reason',1)
        self.assertEqual(StrikeStore(self.db).active_count(1),1)
    def test_no_empty_reason(self):
        with self.assertRaises(ValueError):self.store.add(1,9,' ',1)
