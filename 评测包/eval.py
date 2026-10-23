"""Keyword/refusal diagnostics, not semantic accuracy. Backend mode uses fresh
visitor capabilities per question and disables TTS. Credentials are env-only.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PASS_THRESHOLD = .6
REFUSAL_MARKERS = ['无法提供','无法回答','不能回答','不能帮','暂未找到','暂时没有','超出我的','超出了我','不在我的','不在讲解范围','不涉及景区','换个景点','换一个景点','没有找到可靠依据']

class ProtocolError(ValueError): pass

def _post_json(url,payload,headers=None,timeout=60):
    req=urllib.request.Request(url,json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json',**(headers or {})},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as response:
        try: value=json.loads(response.read().decode('utf-8'))
        except (ValueError,UnicodeError) as exc: raise ProtocolError('not JSON') from exc
    if not isinstance(value,dict): raise ProtocolError('not object')
    return value

def answer_at(value,path):
    for part in path.split('.'):
        if not isinstance(value,dict) or part not in value: raise ProtocolError('missing answer')
        value=value[part]
    if not isinstance(value,str) or not value.strip(): raise ProtocolError('empty answer')
    return value

def call_openai_api(url,key,model,question):
    response=_post_json(url,{'model':model,'messages':[{'role':'system','content':'只回答有依据的灵山景区问题，无关或无依据时请拒答。'},{'role':'user','content':question}],'temperature':.1,'max_tokens':800},{'Authorization':f'Bearer {key}'} if key else {})
    try:
        choice=response['choices'][0]
        if choice.get('finish_reason')!='stop': raise ProtocolError('incomplete model answer')
        return answer_at(choice,'message.content')
    except (KeyError,IndexError,TypeError) as exc: raise ProtocolError('invalid model fields') from exc

def call_custom_api(url,question_field,answer_field,extra_fields,question):
    payload={question_field:question}
    for pair in extra_fields.split(','):
        if '=' in pair:
            key,value=pair.split('=',1); payload[key.strip()]=value.strip()
    return answer_at(_post_json(url,payload),answer_field)

def call_backend_api(url,question):
    # Never persist or reuse this capability: each question gets a new session.
    response=_post_json(url,{'message':question,'tts_enabled':False},{'X-Visitor-Key':secrets.token_hex(32)})
    if not isinstance(response.get('request_id'),str) or not response['request_id']: raise ProtocolError('missing request_id')
    if response.get('status') not in ('completed','refused','partial','failed','cancelled'): raise ProtocolError('invalid terminal')
    if not isinstance(response.get('sources'),list) or not isinstance(response.get('answer'),str): raise ProtocolError('missing fields')
    return response

def contains_keyword(answer,keyword):
    if not keyword: return False
    if re.fullmatch(r'\d+(?:\.\d+)?',keyword): return re.search(rf'(?<![\d.]){re.escape(keyword)}(?![\d.])',answer) is not None
    return keyword in answer

def score_answer(answer,expected_keywords,expected_keyword_groups=None):
    groups=expected_keyword_groups or [[w] for w in expected_keywords]
    groups=[g for g in groups if any(g)]
    if not groups: return None,[]
    matched=[next((w for w in g if contains_keyword(answer,w)),None) for g in groups]
    return sum(w is not None for w in matched)/len(groups),[w for w in matched if w]

def check_refusal(answer): return any(m in answer for m in REFUSAL_MARKERS)
def ratio(n,d): return round(n/d,4) if d else None

def run_eval(dataset,args):
    results=[]
    for item in dataset:
        started=time.perf_counter()
        groups=item.get('expected_keyword_groups') or [[w] for w in item.get('expected_keywords',[])]
        eligible=not item.get('should_refuse',False) and any(any(g) for g in groups)
        row={**item,'should_refuse':bool(item.get('should_refuse',False)),'category':item.get('category','unknown'),'difficulty':item.get('difficulty',''),
             'answer':'','request_success':False,'failure_kind':None,'failure_reason':None,'keyword_applicable':eligible,
             'keyword_score':0 if eligible else None,'keyword_ok':False if eligible else None,'answer_matched':[],
             'answer_ok':False,'refusal_correct':False,'wrong_refusal':False,'is_refusal':None,'factual_correctness':None,'citation_support':None}
        try:
            if args.mode=='backend':
                response=call_backend_api(args.api_url,item['question'])
                row.update({k:response.get(k) for k in ('request_id','status','sources','mode','provenance','timings','knowledge_revision')})
                answer=response['answer']
                if response['status'] not in ('completed','refused'):
                    row.update(answer=answer,failure_kind='terminal',failure_reason='backend_'+response['status'])
                    continue
            elif args.mode=='openai': answer=call_openai_api(args.api_url,getattr(args,'api_key',''),args.model,item['question'])
            else: answer=call_custom_api(args.api_url,args.question_field,args.answer_field,args.extra_fields,item['question'])
            if not isinstance(answer,str) or not answer.strip(): raise ProtocolError('empty answer')
            row.update(answer=answer,request_success=True)
            refused=row.get('status')=='refused' or check_refusal(answer)
            row.update(is_refusal=refused,wrong_refusal=refused and not row['should_refuse'],refusal_correct=refused==row['should_refuse'])
            if eligible:
                score,matched=score_answer(answer,item.get('expected_keywords',[]),item.get('expected_keyword_groups'))
                row.update(keyword_score=round(score,4),keyword_ok=score>=PASS_THRESHOLD,answer_matched=matched)
            row['answer_ok']=refused if row['should_refuse'] else bool(row['keyword_ok']) and not refused
        except (urllib.error.URLError,TimeoutError,ValueError,OSError,ConnectionError) as exc:
            # Exception text/HTTP bodies can contain credentials; keep safe codes only.
            row.update(failure_kind='protocol' if isinstance(exc,(ProtocolError,json.JSONDecodeError)) else 'request',failure_reason=type(exc).__name__)
            if isinstance(exc,urllib.error.HTTPError): row['http_status']=exc.code
        finally:
            row['elapsed_ms']=round((time.perf_counter()-started)*1000,2)
            results.append(row)
        print(f"{item['id']}: {'OK' if row['answer_ok'] else 'FAIL'} {row['failure_kind'] or ''}")
    refusal=[r for r in results if r['should_refuse']]; normal=[r for r in results if not r['should_refuse']]; keywords=[r for r in results if r['keyword_applicable']]
    summary={'total':len(results),'request_success':sum(r['request_success'] for r in results),
        'request_success_rate':ratio(sum(r['request_success'] for r in results),len(results)),
        'keyword_total':len(keywords),'keyword_pass':sum(bool(r['keyword_ok']) for r in keywords),
        'keyword_pass_rate':ratio(sum(bool(r['keyword_ok']) for r in keywords),len(keywords)),
        'refusal_total':len(refusal),'refusal_pass':sum(r['request_success'] and r['refusal_correct'] for r in refusal),
        'refusal_accuracy':ratio(sum(r['request_success'] and r['refusal_correct'] for r in refusal),len(refusal)),
        'wrong_refusal_total':sum(r['wrong_refusal'] for r in normal),'wrong_refusal_rate':ratio(sum(r['wrong_refusal'] for r in normal),len(normal)),
        'factual_accuracy':None,'citation_support_rate':None,'recall_at_k':None,'mrr':None}
    summary['category_breakdown']={cat:{'total':sum(r['category']==cat for r in results),'request_failures':sum(r['category']==cat and not r['request_success'] for r in results),'heuristic_pass':sum(r['category']==cat and r['answer_ok'] for r in results)} for cat in sorted({r['category'] for r in results})}
    return {**summary,'results':results}

def write_reports(report,output):
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with output.with_suffix('.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f); writer.writerow(['metric','value'])
        for k,v in report['summary'].items():
            if not isinstance(v,(dict,list)): writer.writerow([k,'N/A' if v is None else v])
    output.with_name(output.stem+'-failures.json').write_text(json.dumps([r for r in report['summary']['results'] if not r['answer_ok']],ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['backend','openai','custom'],default='backend')
    parser.add_argument('--api-url',default='http://127.0.0.1:8080/api/chat/send')
    parser.add_argument('--api-key-env',default='EVAL_API_KEY'); parser.add_argument('--model',default='')
    parser.add_argument('--question-field',default='question'); parser.add_argument('--answer-field',default='answer'); parser.add_argument('--extra-fields',default='')
    parser.add_argument('--dataset',type=Path,default=SCRIPT_DIR/'qa_testset.json'); parser.add_argument('--output',type=Path,default=Path('eval-report.json')); parser.add_argument('--limit',type=int,default=0)
    args=parser.parse_args(); url=urllib.parse.urlsplit(args.api_url)
    if url.username or url.password or url.query or url.fragment: parser.error('use credential-free URL without query or fragment')
    args.api_key=os.environ.get(args.api_key_env,''); raw=args.dataset.read_bytes(); dataset=json.loads(raw)
    if args.limit>0: dataset=dataset[:args.limit]
    try:
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SCRIPT_DIR,text=True,stderr=subprocess.DEVNULL).strip()
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=SCRIPT_DIR,text=True))
    except (OSError,subprocess.CalledProcessError): sha,dirty=None,None
    summary=run_eval(dataset,args)
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'git_sha':sha,'working_tree_dirty':dirty,'dataset_sha256':hashlib.sha256(raw).hexdigest(),'dataset_size':len(dataset),
        'scope':{'backend':'backend_rag_http','openai':'direct_model','custom':'custom_http'}[args.mode],'browser_offline_evaluated':False,'api_url':args.api_url,
        'tts_enabled':False if args.mode=='backend' else None,'session_isolation':'fresh_capability_per_question' if args.mode=='backend' else 'independent_request',
        'scoring_rules':{'keyword_threshold':PASS_THRESHOLD,'keywords_are_semantic_accuracy':False,'request_failures_remain_in_denominators':True,'refusal':'refused terminal or text markers','no_applicable_samples':None,'factual_review':'not performed','relevance_labels':'not provided'},
        'knowledge_revisions':sorted({s.get('revision') for r in summary['results'] for s in (r.get('sources') or []) if s.get('revision') is not None}),'summary':summary}
    write_reports(report,args.output)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False))

if __name__=='__main__': main()
