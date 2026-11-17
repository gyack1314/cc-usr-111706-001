"""从本地冻结响应中恢复来源、请求身份与取得时间。"""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

def origin(url):
    x=urlsplit(url)
    if x.scheme not in ('http','https') or not x.netloc or x.username or x.password:
        raise ValueError('来源地址不合法')
    return x.scheme+'://'+x.netloc.lower()

def acquired_at(meta):
    ts=meta.get('acquired_at')
    if not isinstance(ts,str) or not ts:
        raise ValueError('来源取得时间不明')
    try:
        datetime.fromisoformat(ts)
    except ValueError:
        raise ValueError('来源取得时间不明')
    return ts

class Replay:
    def __init__(self,path):
        p=Path(path)
        doc=json.loads(p.read_text(encoding='utf-8'))
        self.root=p.parent.resolve()
        self.allowed=set(doc['allowed_origins'])
        self.steps=doc['steps']
        self.position=0
        self.receipts=[]
    def request(self,method,url,body=b'',credential_scope=''):
        if origin(url) not in self.allowed or credential_scope and credential_scope!=origin(url):
            raise ValueError('请求或凭据跨越来源范围')
        if self.position>=len(self.steps):raise EOFError('冻结来源已结束')
        step=self.steps[self.position]
        req=step['request']
        if (method,url,hashlib.sha256(body).hexdigest())!=(req['method'],req['url'],req['body_sha256']):
            raise ValueError('请求与来源清单不符')
        p=(self.root/step['response']['file']).resolve()
        if not p.is_relative_to(self.root):raise ValueError('来源文件越界')
        raw=p.read_bytes()
        meta=step['response']
        if len(raw)!=meta['bytes'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:
            raise ValueError('原文字节身份不符')
        ts=acquired_at(meta)
        self.position+=1
        receipt={'method':method,'url':url,'status':meta['status'],'body_sha256':meta['sha256'],
                 'bytes':len(raw),'acquired_at':ts,
                 'credential_scope':credential_scope,'step':self.position}
        self.receipts.append(receipt)
        return raw,receipt
