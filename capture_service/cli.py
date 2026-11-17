"""重放冻结来源并显示采集状态、身份关系与覆盖缺口。"""
import argparse
import json
from .transport import Replay
from .ledger import connect,receive,epochs
from .view import overview
COLLECTION='facilities'
def load(manifest):
    replay=Replay(manifest)
    db=connect(':memory:')
    for step in replay.steps:
        req=step['request']
        raw,receipt=replay.request(req['method'],req['url'])
        receive(db,COLLECTION,raw,receipt)
    return db
def main():
    p=argparse.ArgumentParser()
    p.add_argument('command',choices=['inspect','epochs'])
    p.add_argument('manifest')
    p.add_argument('--as-of',type=int,default=None,help='回查指定期次（含）之前的来源状态')
    args=p.parse_args()
    db=load(args.manifest)
    out=epochs(db,COLLECTION) if args.command=='epochs' else overview(db,COLLECTION,as_of=args.as_of)
    print(json.dumps(out,ensure_ascii=False,indent=2))
    db.close()
if __name__=='__main__':main()
