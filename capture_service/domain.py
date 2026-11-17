"""解释来源记录并解析设施身份关系；待核来源不转换成确认结论。

来源记录分三条线：candidate（商业名单等线索）、support（地方许可）、outline（卫星轮廓）。
同一线内新版次取代旧版次；跨线同一身份同一版次原文冲突由账本拒绝。
关系（地块、运营主体、建筑归属、别名、同址）需两种以上来源线佐证方为已核实，
否则保持候选；来源不足的设施只列入缺口，不计入覆盖总体。
"""
import json
FACILITY_LINES=('candidate','support')
def decode(raw,receipt):
    d=json.loads(raw.decode('utf-8'))
    revision=d.get('revision')
    if not isinstance(revision,str) or not revision:raise ValueError('来源版次不明')
    typ='candidate'
    if 'permit' in d:typ='support'
    elif 'footprint' in d:typ='outline'
    identity=d.get('facility')
    if not identity and typ=='outline' and d.get('building'):
        identity='building:'+str(d['building'])
    if not identity or identity=='None':raise ValueError('来源身份不明')
    return [{'type':typ,'id':str(identity),'version':revision,'payload':d}]
def _claims(records):
    claims={'site':{},'operator':{},'building':{},'alias':{}}
    def add(slot,key,kind):
        claims[slot].setdefault(key,set()).add(kind)
    for r in records:
        p=r['payload']
        if r['type']=='outline' and not p.get('facility'):continue
        fid=r['id']
        if p.get('site'):add('site',(fid,p['site']),r['type'])
        if p.get('operator'):add('operator',(fid,p['operator']),r['type'])
        for b in p.get('buildings') or []:add('building',(fid,b),r['type'])
        for a in p.get('aliases') or []:add('alias',(fid,a),r['type'])
    return claims
def _status(kinds):
    return 'verified' if len(kinds)>=2 else 'candidate'
def resolve(records):
    facilities=sorted({r['id'] for r in records if r['type'] in FACILITY_LINES})
    claims=_claims(records)
    unlinked=sorted(r['payload'].get('footprint') for r in records
                    if r['type']=='outline' and not r['payload'].get('facility'))
    building_holders={}
    for (fid,b) in claims['building']:building_holders.setdefault(b,set()).add(fid)
    contested_b={b for b,fs in building_holders.items() if len(fs)>1}
    alias_holders={}
    for (fid,a) in claims['alias']:alias_holders.setdefault(a,set()).add(fid)
    contested_a={a for a,fs in alias_holders.items() if len(fs)>1}
    relations={'sites':[],'operators':[],'buildings':[],'aliases':[],'colocated':[]}
    conflicts=[]
    for (fid,v),kinds in sorted(claims['site'].items()):
        relations['sites'].append({'facility':fid,'parcel':v,'kinds':sorted(kinds),'status':_status(kinds)})
    for (fid,v),kinds in sorted(claims['operator'].items()):
        relations['operators'].append({'facility':fid,'operator':v,'kinds':sorted(kinds),'status':_status(kinds)})
    for (fid,b),kinds in sorted(claims['building'].items()):
        st='conflict' if b in contested_b else _status(kinds)
        relations['buildings'].append({'facility':fid,'building':b,'kinds':sorted(kinds),'status':st})
    for b in sorted(contested_b):
        conflicts.append({'kind':'building','key':b,'facilities':sorted(building_holders[b])})
    for (fid,a),kinds in sorted(claims['alias'].items()):
        st='conflict' if a in contested_a else _status(kinds)
        relations['aliases'].append({'facility':fid,'alias':a,'kinds':sorted(kinds),'status':st})
    for a in sorted(contested_a):
        conflicts.append({'kind':'alias','key':a,'facilities':sorted(alias_holders[a])})
    parcel_fs={}
    for (fid,p) in claims['site']:
        if fid in facilities:parcel_fs.setdefault(p,set()).add(fid)
    for p,fs in sorted(parcel_fs.items()):
        if len(fs)<2:continue
        st='verified' if all(len(claims['site'][(f,p)])>=2 for f in fs) else 'candidate'
        relations['colocated'].append({'parcel':p,'facilities':sorted(fs),'status':st})
    covered=[]
    insufficient=[]
    for fid in facilities:
        gaps=[]
        sites=[k for (f,_),k in claims['site'].items() if f==fid]
        ops=[k for (f,_),k in claims['operator'].items() if f==fid]
        if not sites:gaps.append('缺少地块依据')
        elif len(sites)>1:gaps.append('地块依据存在冲突，仍待核')
        elif not any(len(k)>=2 for k in sites):gaps.append('地块依据仅单一来源类型，仍待核')
        if not ops:gaps.append('缺少运营主体依据')
        elif len(ops)>1:gaps.append('运营主体依据存在冲突，仍待核')
        elif not any(len(k)>=2 for k in ops):gaps.append('运营主体依据仅单一来源类型，仍待核')
        if gaps:insufficient.append({'facility':fid,'reasons':gaps})
        else:covered.append(fid)
    reasons=[]
    if not facilities:reasons.append('缺少来源记录')
    for ins in insufficient:
        reasons+=['设施 %s %s'%(ins['facility'],g) for g in ins['reasons']]
    for b in sorted(contested_b):
        reasons.append('建筑 %s 被多个设施主张，归属待核'%b)
    for a in sorted(contested_a):
        reasons.append('别名 %s 被多个设施使用，身份待核'%a)
    for rel in relations['buildings']:
        if rel['status']=='candidate':reasons.append('建筑 %s 归属设施 %s 仍待核'%(rel['building'],rel['facility']))
    for rel in relations['aliases']:
        if rel['status']=='candidate':reasons.append('别名 %s 归属设施 %s 仍待核'%(rel['alias'],rel['facility']))
    for rel in relations['colocated']:
        if rel['status']=='candidate':reasons.append('地块 %s 同址设施 %s 关系仍待核'%(rel['parcel'],'、'.join(rel['facilities'])))
    for fp in unlinked:
        reasons.append('卫星轮廓 %s 尚未关联到设施线索'%fp)
    return {'publishable':not reasons,'reasons':reasons,
            'coverage':{'covered_count':len(covered),'covered':covered,'insufficient':insufficient},
            'relations':relations,'conflicts':conflicts,'unlinked_outlines':unlinked}
