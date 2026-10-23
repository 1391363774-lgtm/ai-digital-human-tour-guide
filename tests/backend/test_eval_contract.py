import argparse
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('guide_eval', Path(__file__).resolve().parents[2] / '评测包/eval.py')
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def arguments(**kw):
    return argparse.Namespace(mode='custom', api_url='http://localhost/test', api_key='', model='test',
                              question_field='question', answer_field='answer', extra_fields='', **kw)


def test_timeout_keeps_refusal_denominator_and_metadata(monkeypatch):
    def timeout(*a, **k):
        raise TimeoutError('offline timeout')
    monkeypatch.setattr(evaluation, 'call_custom_api', timeout)
    report = evaluation.run_eval([{'id':'r1','question':'outside','category':'boundary','difficulty':'hard','should_refuse':True}], arguments())
    assert report['refusal_total'] == 1
    assert report['refusal_accuracy'] == 0
    assert report['results'][0]['should_refuse'] is True
    assert report['results'][0]['difficulty'] == 'hard'


def test_no_applicable_samples_are_na(monkeypatch):
    monkeypatch.setattr(evaluation, 'call_custom_api', lambda *a, **k: '88米')
    report = evaluation.run_eval([{'id':'n','question':'height','expected_keywords':['88']}], arguments())
    assert report['refusal_accuracy'] is None


def test_error_json_is_protocol_failure(monkeypatch):
    monkeypatch.setattr(evaluation, '_post_json', lambda *a, **k: {'error':'contains expected 88'})
    report = evaluation.run_eval([{'id':'n','question':'height','expected_keywords':['88']}], arguments())
    assert report['results'][0]['failure_kind'] == 'protocol'
    assert report['request_success_rate'] == 0


def test_keyword_hit_does_not_hide_wrong_refusal(monkeypatch):
    monkeypatch.setattr(evaluation, 'call_custom_api', lambda *a, **k: '无法回答88米的问题')
    report = evaluation.run_eval([{'id':'n','question':'height','expected_keywords':['88']}], arguments())
    assert report['results'][0]['keyword_ok'] is True
    assert report['results'][0]['wrong_refusal'] is True
    assert report['results'][0]['answer_ok'] is False


def test_backend_disables_tts_and_isolates_questions(monkeypatch):
    sent=[]
    def post(url,payload,headers):
        sent.append((payload,headers))
        return {'answer':'88米','sources':[],'request_id':str(len(sent)),'status':'completed'}
    monkeypatch.setattr(evaluation,'_post_json',post)
    report=evaluation.run_eval([{'id':i,'question':'高度','expected_keywords':['88']} for i in range(2)],
                               argparse.Namespace(mode='backend',api_url='http://localhost/api/chat/send'))
    assert report['request_success']==2
    assert all(payload=={'message':'高度','tts_enabled':False} for payload,_ in sent)
    assert sent[0][1]['X-Visitor-Key']!=sent[1][1]['X-Visitor-Key']
    assert 'X-Visitor-Key' not in str(report)


def test_backend_missing_terminal_and_partial_do_not_score(monkeypatch):
    monkeypatch.setattr(evaluation,'_post_json',lambda *a,**k:{'answer':'88','sources':[],'request_id':'r'})
    args=argparse.Namespace(mode='backend',api_url='http://localhost/api/chat/send')
    data=[{'id':'n','question':'height','expected_keywords':['88']}]
    report=evaluation.run_eval(data,args)
    assert report['results'][0]['failure_kind']=='protocol'
    monkeypatch.setattr(evaluation,'_post_json',lambda *a,**k:{'answer':'88','sources':[],'request_id':'r','status':'partial'})
    report=evaluation.run_eval(data,args)
    assert len(report['results'])==1 and report['keyword_pass_rate']==0
    assert report['results'][0]['failure_kind']=='terminal'


def test_no_keywords_and_numeric_boundaries():
    assert evaluation.score_answer('anything',[])==(None,[])
    assert not evaluation.contains_keyword('1997','9')
    assert evaluation.run_eval([],arguments())['request_success_rate'] is None
