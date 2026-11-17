"""按领域解释结果展示已接收证据、身份关系及缺口；可指定期次回查。"""
from .ledger import current,superseded,epochs
from .domain import resolve
def overview(c,collection,as_of=None):
    rows=current(c,collection,as_of)
    result=resolve(rows)
    eps=epochs(c,collection)
    result['collection']=collection
    result['epoch']=as_of if as_of is not None else (eps[-1]['epoch'] if eps else 0)
    result['records']=[{'type':r['type'],'id':r['id'],'version':r['version'],
                        'source_sha256':r['source'],'epoch':r['epoch'],'acquired_at':r['acquired_at']}
                       for r in rows]
    result['superseded']=[{'type':r['type'],'id':r['id'],'version':r['version'],'epoch':r['epoch']}
                          for r in superseded(c,collection,as_of)]
    return result
