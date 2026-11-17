"""按来源身份原子登记原文、取得时间与领域记录；各期状态可回查。"""
import hashlib
import json
import sqlite3
from .domain import decode
SCHEMA="""
CREATE TABLE IF NOT EXISTS receipts(collection TEXT NOT NULL,acq_seq INTEGER NOT NULL,body_sha256 TEXT NOT NULL,source_url TEXT NOT NULL,status INTEGER NOT NULL,acquired_at TEXT NOT NULL,raw BLOB NOT NULL,PRIMARY KEY(collection,body_sha256));
CREATE UNIQUE INDEX IF NOT EXISTS receipts_seq ON receipts(collection,acq_seq);
CREATE TABLE IF NOT EXISTS entities(collection TEXT NOT NULL,entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,version TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(collection,entity_type,entity_id,version),FOREIGN KEY(collection,receipt_sha256) REFERENCES receipts(collection,body_sha256));
"""
def connect(path):
    c=sqlite3.connect(path)
    c.execute('PRAGMA foreign_keys=ON')
    c.executescript(SCHEMA)
    return c
def receive(c,collection,raw,receipt):
    if receipt['status']!=200:raise ValueError('来源未返回成功正文')
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=receipt['body_sha256']:raise ValueError('收据与原文不符')
    acquired_at=receipt.get('acquired_at')
    if not acquired_at:raise ValueError('来源取得时间不明')
    rows=decode(raw,receipt)
    with c:
        seq=c.execute('SELECT COALESCE(MAX(acq_seq),0)+1 FROM receipts WHERE collection=?',(collection,)).fetchone()[0]
        c.execute('INSERT OR IGNORE INTO receipts(collection,acq_seq,body_sha256,source_url,status,acquired_at,raw) VALUES(?,?,?,?,?,?,?)',
                  (collection,seq,sha,receipt['url'],receipt['status'],acquired_at,raw))
        for row in rows:
            payload=json.dumps(row['payload'],ensure_ascii=False,sort_keys=True)
            key=(collection,row['type'],row['id'],row['version'])
            prior=c.execute('SELECT receipt_sha256,payload_json FROM entities WHERE collection=? AND entity_type=? AND entity_id=? AND version=?',key).fetchone()
            if prior and prior!=(sha,payload):raise ValueError('同一实体版本原文冲突')
            c.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?,?,?,?)',(*key,sha,payload))
    return sha
def entities(c,collection,as_of=None):
    q=('SELECT e.entity_type,e.entity_id,e.version,e.receipt_sha256,e.payload_json,r.acq_seq,r.acquired_at,r.source_url'
       ' FROM entities e JOIN receipts r ON r.collection=e.collection AND r.body_sha256=e.receipt_sha256'
       ' WHERE e.collection=?')
    args=[collection]
    if as_of is not None:
        q+=' AND r.acq_seq<=?'
        args.append(as_of)
    q+=' ORDER BY e.entity_type,e.entity_id,e.version'
    return [dict(type=t,id=i,version=v,source=s,payload=json.loads(p),epoch=seq,acquired_at=at,url=u)
            for t,i,v,s,p,seq,at,u in c.execute(q,args)]
def current(c,collection,as_of=None):
    latest={}
    for r in entities(c,collection,as_of):
        key=(r['type'],r['id'])
        if key not in latest or (r['epoch'],r['version'])>(latest[key]['epoch'],latest[key]['version']):
            latest[key]=r
    return sorted(latest.values(),key=lambda r:(r['type'],r['id']))
def superseded(c,collection,as_of=None):
    live={(r['type'],r['id'],r['version']) for r in current(c,collection,as_of)}
    return [r for r in entities(c,collection,as_of) if (r['type'],r['id'],r['version']) not in live]
def epochs(c,collection):
    return [dict(epoch=r[0],acquired_at=r[1],url=r[2],sha256=r[3])
            for r in c.execute('SELECT acq_seq,acquired_at,source_url,body_sha256 FROM receipts WHERE collection=? ORDER BY acq_seq',(collection,))]
