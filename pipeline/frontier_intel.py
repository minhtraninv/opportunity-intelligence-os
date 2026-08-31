#!/usr/bin/env python3
"""Structured-serendipity discovery layer for Opportunity Intelligence OS.

Expands sight into attention/distribution, new technology capabilities, behavior,
talent and revealed capital/ownership footprints. Output is discovery-only: it may
open an investigation, never create a verified thesis by itself.
"""
from __future__ import annotations

import hashlib, json, re, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
SOURCES=ROOT/'pipeline'/'frontier_sources.json'; MISSES=DATA/'miss_log.json'
MEDIA=DATA/'entity_media_history.json'; HISTORY=DATA/'frontier_history.json'; OUTPUT=DATA/'frontier_intelligence.json'
WINDOW_DAYS=90; RECENT_DAYS=14; MAX_HISTORY=4000; QUEUE_LIMIT=5
UA='Mozilla/5.0 (compatible; OpportunityIntelligenceOS/3.0; +https://github.com/)'

RULES={
'attention_distribution':('monthly active','active users','user growth','người dùng','users','traffic','lưu lượng','downloads','download','creator','creators','kol','influencer','followers','algorithm','thuật toán','feed','recommendation','distribution','phân phối','reach','community','cộng đồng','adoption','tăng trưởng người dùng'),
'technology_frontier':('ai agent','tác nhân ai','foundation model','large language model','llm','robot','robotics','humanoid','chip','semiconductor','bán dẫn','quantum','autonomous','self-driving','drone','satellite','biotech','gene editing','battery','solid-state','computer use','multimodal','open source model','open-source model','mô hình ai','ai model'),
'capital_ownership':('raises','raised','funding','fundraise','series a','series b','series c','venture capital','investment','invests','đầu tư','rót vốn','huy động vốn','tăng vốn','acquire','acquisition','mua lại','thâu tóm','stake','cổ phần','ownership','billionaire','tỷ phú','family office','insider','mua vào','mua đất','data center','trung tâm dữ liệu','factory','nhà máy','capex'),
'behavior_change':('adoption','usage','spending','chi tiêu','subscription','subscribers','thói quen','hành vi','gen z','creator economy','livestream','payment adoption','thanh toán số','e-commerce adoption'),
'talent_migration':('hiring','hire','tuyển dụng','tuyển nhân sự','engineers','kỹ sư','researchers','talent','nhân tài','brain drain','relocate','mở văn phòng','new office')}
ANCHORS={'threads':('threads','meta threads'),'tiktok':('tiktok','tik tok'),'youtube':('youtube',),'instagram':('instagram',),'facebook':('facebook',),'x-twitter':('twitter','x.com','platform x','mạng xã hội x'),'reddit':('reddit',),'substack':('substack',),'discord':('discord',),'chatgpt':('chatgpt',),'openai':('openai',),'anthropic':('anthropic','claude'),'gemini':('gemini','google deepmind'),'nvidia':('nvidia',),'tesla':('tesla',)}
VIETNAM=('việt nam','vietnam','vietnamese','hà nội','hanoi','tp.hcm','tp hcm','hồ chí minh','ho chi minh','đà nẵng','da nang')
ATTENTION_NEG=('vụ kiện','lawsuit','dàn xếp','khởi kiện','lấy lại tài khoản','bảo vệ tài khoản','hack','bị hack','lừa đảo','scam','antitrust','phạt tiền','fine')
MAG=(r'\b\d+(?:[\.,]\d+)?\s*(?:million|billion|triệu|tỷ)\b',r'\b\d+(?:[\.,]\d+)?%',r'\btop\s*\d+\b',r'\brecord\b',r'kỷ lục',r'tăng gấp',r'double',r'triple')
STOP={'the','and','for','with','from','that','this','into','over','after','before','about','more','new','says','will','its','are','was','has','have','của','và','cho','với','trong','trên','tại','đang','được','một','những','các','này','sau','trước','về','theo','khi','mới','sẽ','đến','từ','nhiều','người','công','ty','tech','technology','business','startup','news','company'}
WHY={'attention_distribution':'Sự chú ý hoặc quyền phân phối có thể đang dịch chuyển trước khi monetization và creator hierarchy ổn định.','technology_frontier':'Một capability công nghệ mới có thể làm thay đổi chi phí, tốc độ hoặc thứ một cá nhân/doanh nghiệp nhỏ có thể làm.','capital_ownership':'Hành động bỏ vốn/quyền sở hữu là revealed preference; lặp lại có thể báo hiệu nơi người có nguồn lực đang đặt cược.','behavior_change':'Hành vi người dùng thay đổi thường đi trước value migration sang sản phẩm, kênh phân phối hoặc business model mới.','talent_migration':'Dòng nhân tài và tuyển dụng có thể là tín hiệu sớm cho nơi capability và hoạt động thật đang tích tụ.'}
QUEST={'attention_distribution':'Distribution ở đây còn rẻ bất thường không, và ai đang tích lũy audience/reputation trước khi thị trường đông lên?','technology_frontier':'Điều gì vừa trở nên khả thi hoặc rẻ hơn rõ rệt, và bottleneck tiếp theo sẽ chuyển sang đâu?','capital_ownership':'Đây là giao dịch đơn lẻ hay một chuỗi revealed preference từ nhiều người/tổ chức độc lập?','behavior_change':'Thay đổi này có đủ bền để kéo theo doanh thu/quyền lực thị trường hay chỉ là novelty ngắn hạn?','talent_migration':'Nhân tài đang dịch chuyển vì hype hay vì workload, vốn và nhu cầu vận hành thực sự đã xuất hiện?'}

def load(p,d):
    try:return json.loads(p.read_text(encoding='utf-8')) if p.exists() else d
    except Exception:return d

def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def norm(x):return re.sub(r'\s+',' ',unescape(re.sub(r'<[^>]+>',' ',x or ''))).strip()
def fold(x):return norm(x).casefold()
def parse_date(x):
    if not x:return None
    for f in (lambda v:parsedate_to_datetime(v),lambda v:datetime.fromisoformat(v.replace('Z','+00:00'))):
        try:
            d=f(x); return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except Exception:pass
    return None

def session():
    s=requests.Session(); r=Retry(total=2,connect=2,read=2,status=2,backoff_factor=.8,status_forcelist=(429,500,502,503,504),allowed_methods=frozenset({'GET'}),raise_on_status=False); a=HTTPAdapter(max_retries=r); s.mount('https://',a); s.mount('http://',a); s.headers.update({'User-Agent':UA,'Accept-Language':'vi-VN,vi;q=0.9,en;q=0.8'}); return s
SESSION=session()

def shifts(text):
    t=fold(text); hits=[]
    for k,phr in RULES.items():
        n=sum(1 for p in phr if p.casefold() in f' {t} ')
        if not n:continue
        if k=='attention_distribution' and any(x in t for x in ATTENTION_NEG):continue
        # Behavior needs more than one generic cue unless a strong structural phrase is present.
        if k=='behavior_change' and n<2 and not any(x in t for x in ('adoption','thói quen','hành vi','gen z','creator economy')):continue
        hits.append((k,n))
    return [k for k,_ in sorted(hits,key=lambda x:(-x[1],x[0]))[:3]]
def anchors(text):
    t=fold(text); return [k for k,opts in ANCHORS.items() if any(o.casefold() in t for o in opts)][:3]
def tokens(title):
    out=[]
    for t in re.findall(r'[\wÀ-ỹ-]+',fold(title),flags=re.UNICODE):
        t=t.strip('-_')
        if len(t)>=4 and t not in STOP and not t.isdigit() and t not in out:out.append(t)
    return out[:7]
def magnitude(text):return sum(1 for p in MAG if re.search(p,fold(text),flags=re.UNICODE))
def make(source,title,summary,url,published,captured):
    text=f'{title} {summary}'; ss=shifts(text)
    if not ss:return None
    sid=source.get('id','unknown'); eid=hashlib.sha1(f'{sid}|{url}|{fold(title)}'.encode()).hexdigest()[:18]
    return {'id':eid,'source_id':sid,'publisher':source.get('name'),'scope':source.get('scope'),'title':norm(title),'summary':norm(summary)[:420],'source_url':url,'published_at':published.isoformat(),'captured_at':captured.isoformat(),'shift_types':ss,'anchors':anchors(text),'topic_tokens':tokens(title),'magnitude_cues':magnitude(text),'vietnam_relevance':source.get('scope')=='vietnam' or any(x in fold(text) for x in VIETNAM),'evidence_grade':'discovery_only'}

def parse_feed(source,captured):
    try:
        r=SESSION.get(source['url'],timeout=(10,30)); r.raise_for_status(); root=ET.fromstring(r.content)
    except Exception as e:return [],f"{source.get('name')}: {type(e).__name__}: {e}"
    rows=[]
    for item in root.findall('.//item')[:100]:
        title=norm(item.findtext('title') or ''); summary=norm(item.findtext('description') or ''); url=norm(item.findtext('link') or source['url']); published=parse_date(item.findtext('pubDate')) or captured
        row=make(source,title,summary,url,published,captured)
        if row:rows.append(row)
    ns={'a':'http://www.w3.org/2005/Atom'}
    for item in root.findall('.//a:entry',ns)[:100]:
        title=norm(item.findtext('a:title',default='',namespaces=ns)); summary=norm(item.findtext('a:summary',default='',namespaces=ns) or item.findtext('a:content',default='',namespaces=ns)); link=item.find('a:link',ns); url=(link.get('href') if link is not None else source['url']); published=parse_date(item.findtext('a:published',default='',namespaces=ns) or item.findtext('a:updated',default='',namespaces=ns)) or captured
        row=make(source,title,summary,url,published,captured)
        if row:rows.append(row)
    return rows,None

def inherited_media(captured):
    out=[]
    for x in load(MEDIA,{}).get('events',[]):
        d=parse_date(x.get('published_at') or x.get('first_seen_at'))
        if not d or d<captured-timedelta(days=WINDOW_DAYS):continue
        source={'id':f"media:{x.get('publisher','unknown')}",'name':x.get('publisher'),'scope':'vietnam'}
        row=make(source,x.get('title',''),x.get('summary',''),x.get('source_url',''),d,captured)
        if row:
            row['entity_label']=x.get('entity_label') or x.get('label')
            row['entity_id']=x.get('entity_id')
            out.append(row)
    return out

def merge_history(old,fresh,captured):
    items={str(x.get('id')):dict(x) for x in old.get('events',[]) if isinstance(x,dict) and x.get('id')}
    for x in fresh:items[x['id']]={**items.get(x['id'],{}),**x}
    cutoff=captured-timedelta(days=WINDOW_DAYS); rows=[]
    for x in items.values():
        d=parse_date(x.get('published_at') or x.get('captured_at'))
        if d and d>=cutoff:rows.append(x)
    rows.sort(key=lambda x:x.get('published_at') or '',reverse=True)
    return {'meta':{'version':'3.0.0','updated_at':captured.isoformat(),'discovery_only':True},'events':rows[:MAX_HISTORY]}

def sim(a,b):
    if not a or not b:return 0.0
    return len(a&b)/max(1,len(a|b))
def clusters(events,captured):
    recent=[x for x in events if (parse_date(x.get('published_at')) or captured)>=captured-timedelta(days=RECENT_DAYS)]; recent.sort(key=lambda x:x.get('published_at') or '',reverse=True); out=[]
    for row in recent:
        ra=set(row.get('anchors') or []); rt=set(row.get('topic_tokens') or []); best=None; score=0
        for i,c in enumerate(out):
            ca=set().union(*(set(x.get('anchors') or []) for x in c)); ct=set().union(*(set(x.get('topic_tokens') or []) for x in c)); same_anchor=bool(ra and ca and ra&ca); token_sim=sim(rt,ct)
            # Named entities with different anchors must not merge just because they share a generic word like chip/AI.
            if ra and ca and not same_anchor: s=token_sim if token_sim>=.68 else 0
            else: s=(.75 if same_anchor else 0)+token_sim
            if s>score:best,score=i,s
        if best is not None and score>=.50:out[best].append(row)
        else:out.append([row])
    return out

def miss_ids(text,misses):
    t=fold(text); out=[]
    for m in misses:
        terms=[fold(str(x)) for x in m.get('detection_terms',[]) if str(x).strip()]
        if terms and sum(1 for x in terms if x in t)>=min(2,len(terms)):out.append(str(m.get('id')))
    return out

def label(cluster):
    entities=Counter(str(x.get('entity_label')) for x in cluster if x.get('entity_label'))
    if entities:return entities.most_common(1)[0][0]
    ac=Counter(a for x in cluster for a in x.get('anchors',[]))
    if ac:return ac.most_common(1)[0][0].replace('-',' ').title()
    tc=Counter(t for x in cluster for t in x.get('topic_tokens',[])); words=[x for x,_ in tc.most_common(3)]
    return ' · '.join(x.title() for x in words) or norm(cluster[0].get('title'))[:72]
def candidate(cluster,misses):
    sources={x.get('source_id') for x in cluster}; pubs=sorted({x.get('publisher') for x in cluster if x.get('publisher')}); sc=Counter(s for x in cluster for s in x.get('shift_types',[])); ss=[x for x,_ in sc.most_common(3)]; vn=any(x.get('vietnam_relevance') for x in cluster); mag=sum(int(x.get('magnitude_cues') or 0) for x in cluster); text=' '.join(f"{x.get('title','')} {x.get('summary','')}" for x in cluster); mm=miss_ids(text,misses); ds=[parse_date(x.get('published_at')) for x in cluster]; ds=[x for x in ds if x]
    score=min(100,22+min(20,len(cluster)*4)+min(18,max(0,len(sources)-1)*8)+min(18,len(ss)*6)+min(12,mag*4)+(8 if vn else 0)+(4 if mm else 0)); state='investigate' if score>=74 and len(sources)>=2 and (mag>=1 or len(ss)>=2 or len(cluster)>=3) else 'watch' if score>=56 else 'background'; lab=label(cluster); cid=hashlib.sha1((lab.casefold()+'|'+'|'.join(ss)).encode()).hexdigest()[:16]
    return {'id':cid,'label':lab,'state':state,'score':score,'shift_types':ss,'evidence_count':len(cluster),'source_count':len(sources),'publishers':pubs,'vietnam_relevance':vn,'surprise':not vn,'first_seen_at':min(ds).isoformat() if ds else None,'last_seen_at':max(ds).isoformat() if ds else None,'matched_miss_ids':mm,'why_now':' '.join(WHY[x] for x in ss[:2] if x in WHY) or 'Có nhiều discovery signal cùng hội tụ quanh một thay đổi đáng theo dõi.','opportunity_surface':'Mở hồ sơ để xác định capability/attention/capital đang dịch chuyển ở đâu, ai capture distribution hoặc ownership, và một cá nhân có thể tiếp cận bằng information, audience, service, small bet hay ownership nào.','questions':[QUEST[x] for x in ss[:3] if x in QUEST],'evidence':[{'title':x.get('title'),'publisher':x.get('publisher'),'source_url':x.get('source_url'),'published_at':x.get('published_at'),'shift_types':x.get('shift_types'),'evidence_grade':'discovery_only'} for x in sorted(cluster,key=lambda x:x.get('published_at') or '',reverse=True)[:6]],'discovery_only':True}
def queue(cands):
    ranked=sorted(cands,key=lambda x:(x.get('state')=='investigate',x.get('score',0),x.get('source_count',0)),reverse=True); out=[]; global_count=0
    for x in ranked:
        if x.get('state')=='background':continue
        # A lone media headline is not enough for the public attention queue.
        if x.get('source_count',0)<2 and x.get('score',0)<78:continue
        if x.get('surprise'):
            if global_count>=1 and x.get('score',0)<86:continue
            global_count+=1
        out.append(x)
        if len(out)>=QUEUE_LIMIT:break
    return out

def benchmarks(misses,events,cands):
    text=fold(' '.join(f"{x.get('title','')} {x.get('summary','')}" for x in events)); matched={mid for c in cands for mid in c.get('matched_miss_ids',[])}; out=[]
    for m in misses:
        terms=[fold(str(x)) for x in m.get('detection_terms',[]) if str(x).strip()]; out.append({'id':m.get('id'),'label':m.get('label'),'status':'detectable_now' if m.get('id') in matched else 'coverage_debt','matched_terms':[x for x in terms if x in text][:8],'required_shift_types':m.get('shift_types') or [],'lesson':m.get('lesson')})
    return out

def main():
    now=datetime.now(timezone.utc); cfg=load(SOURCES,{'sources':[]}); misses=[x for x in load(MISSES,{'misses':[]}).get('misses',[]) if isinstance(x,dict)]; fresh=[]; health=[]
    for s in cfg.get('sources',[]):
        rows,err=parse_feed(s,now); fresh+=rows; health.append({'source_id':s.get('id'),'name':s.get('name'),'scope':s.get('scope'),'status':'error' if err else 'ok','items_this_run':len(rows),'error':err})
    inherited=inherited_media(now); fresh+=inherited; hist=merge_history(load(HISTORY,{}),fresh,now); write(HISTORY,hist); cs=[candidate(c,misses) for c in clusters(hist.get('events',[]),now) if c]; cs.sort(key=lambda x:(x.get('score',0),x.get('source_count',0),x.get('evidence_count',0)),reverse=True); q=queue(cs); recent=[x for x in hist.get('events',[]) if (parse_date(x.get('published_at')) or now)>=now-timedelta(days=RECENT_DAYS)]; counts=Counter(s for x in hist.get('events',[]) for s in x.get('shift_types',[])); healthy=sum(x.get('status')=='ok' for x in health)
    payload={'meta':{'version':'3.0.0','generated_at':now.isoformat(),'mode':'discovery_frontier','principle':'structured_serendipity_broad_discovery_narrow_conclusion','discovery_only':True},'thesis':'Tìm structural-shift candidates ngoài vùng policy/money-flow quen thuộc: attention/distribution, capability công nghệ, behavior, talent và revealed capital/ownership footprints. Không candidate nào ở lớp này tự trở thành kết luận verified.','coverage':{'configured_frontier_sources':len(cfg.get('sources',[])),'healthy_frontier_sources':healthy,'source_errors':sum(x.get('status')=='error' for x in health),'inherited_vietnam_media_events':len(inherited),'recent_discovery_events':len(recent),'shift_counts':dict(counts)},'attention_queue':q,'candidates':cs[:30],'miss_benchmarks':benchmarks(misses,hist.get('events',[]),cs),'source_health':health,'reading_rule':'Frontier candidate = đáng điều tra, không phải recommendation. Media/RSS chỉ tạo discovery evidence; conviction phải quay về primary evidence, dữ liệu định lượng hoặc hành động vốn/hành vi đã xác minh.'}
    write(OUTPUT,payload); print(f"frontier sources={healthy}/{len(cfg.get('sources',[]))} recent={len(recent)} candidates={len(cs)} queue={len(q)} misses={len(misses)}")
if __name__=='__main__':main()
