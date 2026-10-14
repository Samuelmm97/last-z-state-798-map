import unittest
import shared_power as power

class SharedPowerTests(unittest.TestCase):
    def setUp(self):
        self.players=[[798,'Helm','renamed',200,1,28,'123','456','Helm']]
        self.parts=[[798,'Helm','old','123',100,10,20,30,25,15,100,0,'2026-10-09T10:00:00Z']]
    def test_dates_and_metrics_remain_separate(self):
        data=power.project(self.players,[],self.parts,'2026-10-14T10:00:00Z',1)
        p=data['players'][0]
        self.assertEqual(p['personalPower']['value'],200)
        self.assertEqual(p['components']['hero']['value'],25)
        self.assertEqual(p['components']['hero']['observedAt'],'2026-10-09T10:00:00Z')
        self.assertEqual(p['name'],'renamed')
    def test_partial_rosters_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):power.project(self.players,[],[],'2026-10-14',2)
        with self.assertRaises(ValueError):power.project(self.players*2,[],[],'2026-10-14',2)
    def test_bad_component_sum_is_rejected(self):
        self.parts[0][8]+=1
        with self.assertRaises(ValueError):power.project(self.players,[],self.parts,'2026-10-14',1)

if __name__=='__main__':unittest.main()
