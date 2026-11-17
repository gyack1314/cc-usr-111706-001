"""核对同一来源链上的接收、解释、账本和缺口。"""
import unittest
from pathlib import Path
from capture_service.transport import Replay
from capture_service.ledger import connect,receive,epochs
from capture_service.view import overview
ROOT=Path(__file__).resolve().parents[1]
COLLECTION='facilities'
def replay_all(manifest):
    replay=Replay(ROOT/manifest)
    db=connect(':memory:')
    for step in replay.steps:
        req=step['request']
        raw,receipt=replay.request(req['method'],req['url'])
        receive(db,COLLECTION,raw,receipt)
    return db
class Integration(unittest.TestCase):
    def test_complete_receipt_chain(self):
        replay=Replay(ROOT/'data/normal.json')
        db=connect(':memory:')
        for step in replay.steps:
            req=step['request']
            raw,receipt=replay.request(req['method'],req['url'])
            receive(db,COLLECTION,raw,receipt)
        view=overview(db,COLLECTION)
        self.assertGreaterEqual(len(view['records']),2)
        self.assertFalse(view['publishable'])
        self.assertTrue(view['reasons'])
        self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],len(replay.steps))
        db.close()
    def test_credential_scope(self):
        replay=Replay(ROOT/'data/normal.json')
        req=replay.steps[0]['request']
        with self.assertRaises(ValueError):replay.request(req['method'],req['url'],credential_scope='https://other.example.test')
        self.assertEqual(replay.position,0)
    def test_same_version_conflict_rolls_back(self):
        replay=Replay(ROOT/'data/conflict.json')
        db=connect(':memory:')
        req=replay.steps[0]['request']
        raw,receipt=replay.request(req['method'],req['url'])
        receive(db,COLLECTION,raw,receipt)
        before=overview(db,COLLECTION)
        req=replay.steps[1]['request']
        raw,receipt=replay.request(req['method'],req['url'])
        with self.assertRaises(ValueError):receive(db,COLLECTION,raw,receipt)
        self.assertEqual(overview(db,COLLECTION),before)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0],1)
        db.close()
class IdentityResolution(unittest.TestCase):
    def test_insufficient_facilities_not_counted(self):
        db=replay_all('data/identity.json')
        view=overview(db,COLLECTION)
        self.assertEqual(view['coverage']['covered'],['F-1'])
        self.assertEqual(view['coverage']['covered_count'],1)
        lacking={i['facility'] for i in view['coverage']['insufficient']}
        self.assertEqual(lacking,{'F-2','F-3'})
        reasons={i['facility']:i['reasons'] for i in view['coverage']['insufficient']}
        self.assertIn('缺少运营主体依据',reasons['F-2'])
        self.assertFalse(view['publishable'])
        db.close()
    def test_permit_correction_shifts_coverage_by_epoch(self):
        db=replay_all('data/identity.json')
        early=overview(db,COLLECTION,as_of=2)
        self.assertEqual(early['coverage']['covered'],['F-1'])
        corrected=overview(db,COLLECTION,as_of=4)
        self.assertEqual(corrected['coverage']['covered'],[])
        lacking={i['facility'] for i in corrected['coverage']['insufficient']}
        self.assertIn('F-1',lacking)
        final=overview(db,COLLECTION)
        self.assertEqual(final['coverage']['covered'],['F-1'])
        db.close()
    def test_late_footprint_verifies_building(self):
        db=replay_all('data/identity.json')
        before=overview(db,COLLECTION,as_of=2)
        b2=[r for r in before['relations']['buildings'] if r['building']=='B-2'][0]
        self.assertEqual(b2['status'],'candidate')
        after=overview(db,COLLECTION,as_of=3)
        b2=[r for r in after['relations']['buildings'] if r['building']=='B-2'][0]
        self.assertEqual(b2['status'],'verified')
        self.assertIn('outline',b2['kinds'])
        db.close()
    def test_superseded_versions_and_epochs_queryable(self):
        db=replay_all('data/identity.json')
        view=overview(db,COLLECTION)
        sup={(s['type'],s['id'],s['version']) for s in view['superseded']}
        self.assertIn(('support','F-1','r1'),sup)
        self.assertIn(('candidate','F-1','r1'),sup)
        eps=epochs(db,COLLECTION)
        self.assertEqual([e['epoch'] for e in eps],[1,2,3,4,5,6,7,8])
        self.assertTrue(all(e['acquired_at'] for e in eps))
        self.assertEqual(view['epoch'],8)
        db.close()
    def test_conflicts_colocation_and_unlinked_outline(self):
        db=replay_all('data/identity.json')
        view=overview(db,COLLECTION)
        b1=[r for r in view['relations']['buildings'] if r['building']=='B-1']
        self.assertEqual(len(b1),2)
        self.assertTrue(all(r['status']=='conflict' for r in b1))
        alias=[r for r in view['relations']['aliases'] if r['alias']=='甲一中心']
        self.assertTrue(all(r['status']=='conflict' for r in alias))
        colo=view['relations']['colocated']
        self.assertEqual(len(colo),1)
        self.assertEqual(colo[0]['parcel'],'P-1')
        self.assertEqual(set(colo[0]['facilities']),{'F-1','F-3'})
        self.assertEqual(colo[0]['status'],'candidate')
        self.assertEqual(view['unlinked_outlines'],['FP-10'])
        db.close()
    def test_missing_acquired_at_rejected(self):
        replay=Replay(ROOT/'data/normal.json')
        replay.steps[0]['response'].pop('acquired_at')
        req=replay.steps[0]['request']
        with self.assertRaises(ValueError):replay.request(req['method'],req['url'])
        self.assertEqual(replay.position,0)
if __name__=='__main__':unittest.main()
