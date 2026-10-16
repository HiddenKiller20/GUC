import unittest
import sqlite3
from promotion_policy import DAY,requirements,approval_errors
from manual_attendance import SessionStore

class Policy(unittest.TestCase):
    def test_private_alternate_tenure_and_marks(self):
        self.assertEqual(requirements('recruit','pvt',0,0,0,False,2*DAY),[])
        self.assertEqual(requirements('recruit','pvt',0,0,5,False,DAY),[])
        self.assertTrue(requirements('recruit','pvt',0,0,4,False,DAY))
    def test_threshold_and_jump_wait(self):
        self.assertTrue(requirements('pvt','psc',0,0,9,False,10*DAY))
        self.assertTrue(requirements('pvt','psc',0,0,35,False,2*DAY,True))
        self.assertEqual(requirements('pvt','psc',0,0,35,False,3*DAY,True),[])
    def test_marshal_commander_directly_below_high_commander(self):
        from promotion_policy import CODES
        self.assertEqual(CODES[CODES.index('cmdr')+1], 'mc')
        self.assertEqual(CODES[CODES.index('mc')+1], 'hc')
        self.assertEqual(requirements('cmdr','mc',0,0,100,True,10*DAY), [])
        self.assertTrue(requirements('cmdr','mc',0,0,100,True,9*DAY))
        self.assertTrue(requirements('cmdr','mc',0,0,100,False,10*DAY))
        self.assertTrue(requirements('cmdr','hc',0,0,100,True,20*DAY))
        self.assertTrue(approval_errors('mc',{1},set(),1,[(1,'commander','reviewed')],99))
        self.assertEqual(approval_errors('mc',set(),set(),1,[(99,'emperor','appointed')],99), [])

    def test_age_and_high_wait(self):
        self.assertTrue(requirements('col','bg',0,0,100,False,10*DAY))
        self.assertTrue(requirements('col','bg',0,0,100,True,9*DAY))
        self.assertEqual(requirements('col','bg',0,0,100,True,10*DAY),[])
    def test_three_distinct_commanders(self):
        repeated=[(1,'commander','yes')]*3
        self.assertTrue(approval_errors('gen',{1,2,3},set(),1,repeated,99))
        votes=[(n,'commander','reviewed') for n in [1,2,3]]
        self.assertEqual(approval_errors('gen',{1,2,3},set(),1,votes,99),[])
        self.assertTrue(approval_errors('gen',{1,2},set(),1,votes,99))
    def test_shadow_and_emperor_appointments(self):
        votes=[(1,'commander','review'),(99,'emperor_shadow','observed')]
        self.assertEqual(approval_errors('bg',{1},set(),1,votes,99),[])
        self.assertTrue(approval_errors('bg',{1},set(),1,votes[:1],99))
        self.assertTrue(approval_errors('cmdr',{1},set(),1,[(1,'emperor','yes')],99))
        self.assertEqual(approval_errors('cmdr',set(),set(),1,[(99,'emperor','yes')],99),[])
    def test_second_lieutenant_and_nco(self):
        self.assertTrue(approval_errors('2lt',{1},set(),1,[(1,'commander','yes')],99))
        self.assertEqual(approval_errors('2lt',{1},set(),1,[(1,'commander','yes'),(1,'combat_shadow','observed')],99),[])
        self.assertEqual(approval_errors('sfc',set(),{2},1,[(2,'sponsor','skills verified')],99),[])
        self.assertTrue(approval_errors('sfc',set(),set(),1,[(2,'sponsor','skills verified')],99))

class ManualAttendance(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE marks(user_id INTEGER,faction TEXT,event TEXT,issuer INTEGER,created REAL,PRIMARY KEY(user_id,faction,event))')
        self.s=SessionStore(self.db)
    def test_regular_and_combat_each_one_mark(self):
        for kind in ('attendance','combat'):
            self.s.start(1,'Republic',kind,100);self.s.stop(1,160)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM marks').fetchone()[0],2)
    def test_duplicates_and_cross_faction_active(self):
        self.s.start(1,'Republic','attendance',100)
        with self.assertRaises(ValueError):self.s.start(1,'Empire','combat',120)
        self.s.stop(1,160)
        with self.assertRaises(ValueError):self.s.stop(1,180)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM marks').fetchone()[0],1)
    def test_restart_preserves_start_and_void_removes_mark(self):
        sid=self.s.start(1,'Republic','attendance',100)
        reopened=SessionStore(self.db);reopened.stop(1,500)
        self.assertEqual(self.db.execute('SELECT start,end FROM manual_attendance').fetchone(),(100,500))
        reopened.void(sid)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM marks').fetchone()[0],0)

    def test_wrong_stop_cannot_award_mark_or_close_session(self):
        self.s.start(1,'Republic','combat',100)
        with self.assertRaises(ValueError):self.s.stop(1,160,'attendance')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM marks').fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM manual_attendance WHERE status='active'").fetchone()[0],1)
        self.s.stop(1,180,'combat')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM marks').fetchone()[0],1)
