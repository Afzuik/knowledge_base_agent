from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import re
import socket
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings
from app.main import create_app
from app.infrastructure.models import Providers
from app.infrastructure.models.settings import ModelSettings, Endpoint, load_settings
from app.infrastructure.models.transport import ModelError
from app.infrastructure.vector.chroma import ChromaVectors
from app.infrastructure.database.connection import build_engine
from app.infrastructure.database.migrate import migrate
from app.intelligence.citations import finalize
from app.intelligence.retrieval import tokens
from test_ingestion import notebook, upload, detail


class FakeEmbedding:
    profile = 'test-profile-v1'
    dimension = 3
    fail = False
    calls = 0

    def embed(self, texts):
        self.calls += 1
        if self.fail: raise ModelError('embedding test failure')
        return [[1.0] + [0.2] * (self.dimension-1) for _ in texts]


class FakeLLM:
    mode = 'normal'
    calls = 0
    rewrite_calls = 0
    last_messages = None

    def complete(self, messages, max_tokens=256):
        self.rewrite_calls += 1
        return json.loads(messages[-1]['content'])['question']

    def stream(self, messages):
        self.calls += 1; self.last_messages = messages
        if self.mode == 'empty': return
        if self.mode == 'bad_ref':
            yield '不应可点击 [S99]'; return
        if self.mode == 'fail':
            yield '部分回答'; raise ModelError('generation test failure')
        evidence = json.loads(messages[-1]['content'])['selected_evidence']
        for e in evidence:
            yield e['text'] + ' [' + e['label'] + ']\n'


class FakeReranker:
    enabled = False
    fail = False

    def rank(self, query, texts, top_n):
        if self.fail: raise ModelError('rerank test failure')
        return list(range(min(top_n,len(texts))))


class FakeVectors:
    def __init__(self):
        self.rows = {}; self.fail_write = False; self.last_scopes = None; self.bad_query = False

    def upsert(self,n,p,d,s,r,chunks,embeddings):
        for c in chunks: self.rows[(n,p,d,s+':'+r,c['id'])] = embeddings[0]
        if self.fail_write: raise RuntimeError('partial write')

    def verify(self,n,p,d,s,r,ids):
        return {k[4] for k in self.rows if k[:4] == (n,p,d,s+':'+r)} == set(ids)

    def query(self,n,p,d,scopes,vector,k):
        self.last_scopes = scopes
        if self.bad_query: return ['outside-chunk']
        return [x[4] for x in self.rows if x[:3] == (n,p,d) and x[3] in scopes][:k]


@pytest.fixture
def providers():
    endpoint = Endpoint('https://example.invalid/v1','test-model','unit-test-only')
    return Providers(ModelSettings(endpoint,endpoint,endpoint),FakeLLM(),FakeEmbedding(),FakeReranker())


@pytest.fixture
def research(config, providers):
    vectors = FakeVectors()
    with TestClient(create_app(config,run_worker=False,providers=providers,vectors=vectors)) as c:
        yield c, providers, vectors


def indexed(c, n, value=b'budget 120 yuan', name='a.txt'):
    sid = upload(c,n,name,value).json()['source']['id']
    c.app.state.ingestion.run_once()
    result = c.post(f'/api/notebooks/{n}/sources/{sid}/index',json={})
    assert result.status_code == 202, result.text
    c.app.state.indexing.run_once()
    assert detail(c,n,sid)['source']['index_status'] == 'ready'
    return sid


def conversation(c,n):
    r=c.post(f'/api/notebooks/{n}/conversations',json={'title':'test'})
    assert r.status_code==201,r.text
    return r.json()['id']


def ask(c,n,conv,ids,key='test-request-01',question='预算是多少？'):
    return c.post(f'/api/notebooks/{n}/conversations/{conv}/messages',json={
        'question':question,'source_ids':ids,'request_key':key})


def events(response):
    assert response.status_code == 200,response.text
    out=[]
    for block in response.text.split('\n\n'):
        if not block.strip(): continue
        lines=block.splitlines()
        out.append((next(x[7:] for x in lines if x.startswith('event: ')),json.loads(next(x[6:] for x in lines if x.startswith('data: ')))))
    return out


def test_index_stream_and_persisted_citation(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    ev=events(ask(c,n,conv,[sid]));assert ev[0][0]=='start' and ev[-1][0]=='done'
    message=ev[-1][1]['message'];assert '120' in message['content']
    assert message['citations'][0]['source_id']==sid
    assert message['citations'][0]['text']=='budget 120 yuan'
    rows=c.get(f'/api/notebooks/{n}/conversations/{conv}/messages').json()
    assert len(rows)==2 and rows[-1]['citations']==message['citations']
    assert 'request_fingerprint' not in rows[-1]


def test_selected_scope_and_revision_both_retrievers(research):
    c,p,v=research;n=notebook(c)
    a=indexed(c,n,b'budget 120 yuan','a.txt');b=indexed(c,n,b'budget 350 yuan','b.txt')
    conv=conversation(c,n);ev=events(ask(c,n,conv,[a]))
    m=ev[-1][1]['message'];assert '120' in m['content'] and '350' not in m['content']
    assert {x['source_id'] for x in m['citations']}=={a}
    assert all(s.startswith(a+':') for s in v.last_scopes)
    evidence=json.loads(p.llm.last_messages[-1]['content'])['selected_evidence']
    assert len(evidence)==1 and '350' not in evidence[0]['text']


def test_cross_notebook_not_ready_empty_and_foreign_conversation(research):
    c,p,v=research;a=notebook(c);b=notebook(c)
    sid=indexed(c,a);conv=conversation(c,a)
    assert ask(c,b,conv,[sid]).status_code==404
    other=conversation(c,b);assert ask(c,b,other,[sid]).status_code==404
    assert ask(c,a,conv,[]).status_code==422
    pending=upload(c,a,'pending.txt',b'pending').json()['source']['id']
    assert ask(c,a,conv,[pending]).status_code==409
    assert c.post(f'/api/notebooks/{a}/sources/{pending}/index',json={}).status_code==409
    assert p.llm.calls==0


def test_index_partial_failure_retry_same_revision_and_no_duplicates(research):
    c,p,v=research;n=notebook(c)
    sid=upload(c,n,content=b'a long document').json()['source']['id'];c.app.state.ingestion.run_once()
    url=f'/api/notebooks/{n}/sources/{sid}/index'
    assert c.post(url,json={}).status_code==202
    assert c.post(url,json={}).status_code==409
    v.fail_write=True;c.app.state.indexing.run_once()
    row=detail(c,n,sid);assert row['source']['status']=='parsed' and row['source']['index_status']=='failed'
    revision=c.app.state.repo.jobs('local-demo',n,sid)[0]['target_revision']
    count=len(v.rows);v.fail_write=False
    assert c.post(url,json={}).status_code==202;c.app.state.indexing.run_once()
    row=detail(c,n,sid)['source'];assert row['index_revision']==revision and row['index_status']=='ready'
    assert len(v.rows)==count


def test_profile_change_and_dimension_mismatch(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    p.embedding.profile='different-model'
    assert ask(c,n,conv,[sid]).status_code==409
    p.embedding.profile='test-profile-v1';p.embedding.dimension=4
    ev=events(ask(c,n,conv,[sid]));assert ev[-1][0]=='error'
    assert p.llm.calls==0


def test_configured_profile_changed_before_job_runs(research):
    c,p,v=research;n=notebook(c);sid=upload(c,n).json()['source']['id'];c.app.state.ingestion.run_once()
    c.post(f'/api/notebooks/{n}/sources/{sid}/index',json={})
    c.app.state.indexing.profile='new-profile'
    c.app.state.indexing.run_once()
    assert detail(c,n,sid)['source']['index_status']=='failed'
    assert not v.rows


def test_rebuild_switches_revision_after_success(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n)
    old=detail(c,n,sid)['source']['index_revision'];url=f'/api/notebooks/{n}/sources/{sid}/index'
    assert c.post(url,json={}).status_code==409
    assert c.post(url,json={'force':True}).status_code==202
    assert detail(c,n,sid)['source']['index_revision']==old
    c.app.state.indexing.run_once();new=detail(c,n,sid)['source']['index_revision'];assert new!=old
    conv=conversation(c,n);events(ask(c,n,conv,[sid]));assert v.last_scopes==[sid+':'+new]


def test_rerank_fallback_bad_reference_and_empty_answer(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    p.reranker.enabled=True;p.reranker.fail=True
    first=events(ask(c,n,conv,[sid]))[-1];assert first[0]=='done'
    assert any('精排' in x for x in first[1]['message']['warnings'])
    p.llm.mode='bad_ref'
    bad=events(ask(c,n,conv,[sid],'test-bad-ref'))[-1][1]['message']
    assert not bad['citations'] and '[无效引用]' in bad['content']
    p.llm.mode='empty'
    empty=events(ask(c,n,conv,[sid],'test-empty'))[-1]
    assert empty[0]=='error' and empty[1]['message']['status']=='failed'


def test_llm_failure_and_message_commit_failure(research,monkeypatch):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    p.llm.mode='fail'
    failed=events(ask(c,n,conv,[sid]))[-1]
    assert failed[0]=='error' and failed[1]['message']['content']=='部分回答'
    assert not failed[1]['message']['citations']
    p.llm.mode='normal'
    def broken(*args): raise SQLAlchemyError('simulated commit failure')
    monkeypatch.setattr(c.app.state.repo,'finish_message',broken)
    failed=events(ask(c,n,conv,[sid],'test-commit-failure'))
    assert not any(e=='done' for e,_ in failed)
    assert failed[-1][1]['message']['status']=='failed'


def test_idempotent_replay_and_conflict(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    first=events(ask(c,n,conv,[sid]))[-1][1]['message'];calls=p.llm.calls
    second=events(ask(c,n,conv,[sid]))[-1]
    assert second[1]['replayed'] is True and second[1]['message']['id']==first['id']
    assert p.llm.calls==calls
    assert ask(c,n,conv,[sid],question='different').status_code==409
    assert len(c.get(f'/api/notebooks/{n}/conversations/{conv}/messages').json())==2


def test_followup_history_is_not_evidence(research):
    c,p,v=research;n=notebook(c);a=indexed(c,n,b'budget 120','a.txt');b=indexed(c,n,b'budget 350','b.txt');conv=conversation(c,n)
    events(ask(c,n,conv,[a]));events(ask(c,n,conv,[b],'followup-01','它的预算是什么？'))
    assert p.llm.rewrite_calls==0
    payload=json.loads(p.llm.last_messages[-1]['content'])
    assert payload['history_for_reference_only'] == []
    assert all('120' not in x['text'] for x in payload['selected_evidence'])


def test_generator_close_marks_interrupted_and_busy_guard(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n);svc=c.app.state.chat
    row,prepared,replay=svc.prepare('local-demo',n,conv,'预算？',[sid],'interrupt-01')
    assert ask(c,n,conv,[sid],'second-request').status_code==409
    iterator=svc.events(row,prepared,replay,'local-demo',n,'预算？')
    while next(iterator)['event']!='delta': pass
    iterator.close()
    result=c.app.state.repo.message(row['id'])
    assert result['status']=='interrupted' and result['content'] and not result['citations']


def test_chroma_real_metadata_filter_and_persistence(tmp_path):
    vectors=ChromaVectors(tmp_path/'vectors')
    a={'id':'chunk-a'};b={'id':'chunk-b'}
    vectors.upsert('n','profile',3,'a','v1',[a],[[1.,0.,0.]])
    vectors.upsert('n','profile',3,'b','v1',[b],[[1.,0.,0.]])
    vectors.upsert('n','profile',3,'a','v2',[{'id':'chunk-a-new'}],[[1.,0.,0.]])
    assert vectors.verify('n','profile',3,'a','v1',['chunk-a'])
    reopened=ChromaVectors(tmp_path/'vectors')
    assert reopened.query('n','profile',3,['a:v1'],[1.,0.,0.],20)==['chunk-a']
    with pytest.raises(ValueError): reopened.query('n','profile',3,[],[1.,0.,0.],20)


def test_restart_index_and_message_recovery(config,providers):
    vectors=FakeVectors()
    with TestClient(create_app(config,run_worker=False,providers=providers,vectors=vectors)) as c:
        n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
        done=events(ask(c,n,conv,[sid]))[-1][1]['message']
        c.post(f'/api/notebooks/{n}/sources/{sid}/index',json={'force':True});c.app.state.repo.claim('index')
        c.app.state.repo.reserve_message(conv,'pending-request','fingerprint','pending',[sid])
    with TestClient(create_app(config,run_worker=False,providers=providers,vectors=vectors)) as c:
        assert detail(c,n,sid)['source']['index_status']=='failed'
        rows=c.get(f'/api/notebooks/{n}/conversations/{conv}/messages').json()
        assert rows[-1]['status']=='interrupted'
        previous=next(x for x in rows if x['id']==done['id']);assert previous['citations']==done['citations']
        assert c.post(f'/api/notebooks/{n}/sources/{sid}/index',json={}).status_code==202
        c.app.state.indexing.run_once();assert detail(c,n,sid)['source']['index_status']=='ready'


def test_migration_v1_preserves_content_and_creates_backup(config):
    config.data_dir.mkdir(parents=True)
    path=Path(__file__).parents[1]/'app/infrastructure/database/migrations/001_initial.sql'
    with sqlite3.connect(config.database_path) as db:
        db.executescript(path.read_text())
        db.execute("INSERT INTO notebooks VALUES ('old','local-demo','original','time','time')")
        db.execute('PRAGMA user_version=1')
    engine=build_engine(config)
    try:
        migrate(engine)
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one()==2
            assert c.execute(text('SELECT name FROM notebooks')).scalar_one()=='original'
        backup=list(config.data_dir.glob('*.v1-backup-*'));assert len(backup)==1
        with sqlite3.connect(backup[0]) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==1
    finally: engine.dispose()


def test_chinese_tokenizer_and_citation_variants():
    assert '预算' in tokens('项目预算是多少？')
    evidence=[dict(id='c',label='S1',source_id='s',filename='f',text='budget',page_start=None,page_end=None,char_start=0,char_end=6,index_revision='v')]
    for marker in ['[S1]','（S1）','(S1)','【S1】']:
        content,citations,warnings=finalize('预算 '+marker,evidence)
        assert content=='预算 [S1]' and len(citations)==1 and not warnings


def test_out_of_scope_vector_output_is_rejected(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n);v.bad_query=True
    ev=events(ask(c,n,conv,[sid]));assert ev[-1][0]=='error' and p.llm.calls==0


def test_missing_model_config_is_explicit(client):
    n=notebook(client);sid=upload(client,n).json()['source']['id'];client.app.state.ingestion.run_once()
    assert client.post(f'/api/notebooks/{n}/sources/{sid}/index',json={}).status_code==503


def test_configuration_does_not_expose_secrets(tmp_path,monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith(('WORKBENCH_MODEL','LLM_','OPENAI_','SILICONFLOW_','EMBEDDING_','RERANKER_')):monkeypatch.delenv(key)
    (tmp_path/'backend').mkdir()
    (tmp_path/'backend/.env').write_text('LLM_PROVIDER=siliconflow\nSILICONFLOW_API_KEY=unit-test-secret\n')
    config=load_settings(tmp_path)
    assert config.llm.configured
    assert 'unit-test-secret' not in repr(config) and 'unit-test-secret' not in json.dumps(config.public())


def test_embedding_response_validation(providers, monkeypatch):
    import app.infrastructure.models.embedding as module
    from app.infrastructure.models.embedding import Embedding
    for response in [
        {'data': []}, {'data': [{'index': 1, 'embedding': [1,2]}]},
        {'data': [{'index': 0, 'embedding': [0,0]}]},
        {'data': [{'index': 0, 'embedding': [float('nan'),1]}]},
    ]:
        monkeypatch.setattr(module, 'post', lambda *args, value=response: value)
        with pytest.raises(ModelError): Embedding(providers.settings).embed(['x'])


def test_llm_stream_requires_completion_and_sanitizes_http(providers, monkeypatch):
    import httpx
    import app.infrastructure.models.llm as module
    cases = [
        (200, 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n', '中断'),
        (200, 'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n', '截断'),
        (402, 'secret provider response should not leak', '402'),
    ]
    for status, body, expected in cases:
        monkeypatch.setattr(module, 'client', lambda settings, status=status, body=body:
            httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status,text=body))))
        with pytest.raises(ModelError) as exc: list(module.LLM(providers.settings).stream([{'role':'user','content':'x'}]))
        assert expected in str(exc.value) and 'secret provider' not in str(exc.value)


def test_failed_idempotent_request_is_not_rebilled(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n);p.llm.mode='fail'
    first=events(ask(c,n,conv,[sid]));calls=p.llm.calls
    second=events(ask(c,n,conv,[sid]));assert second[-1][0]=='error' and second[-1][1]['replayed']
    assert p.llm.calls==calls and first[-1][1]['message']['id']==second[-1][1]['message']['id']


def test_client_supplied_owner_and_oversized_scope_are_rejected(research):
    c,p,v=research;n=notebook(c);conv=conversation(c,n)
    url=f'/api/notebooks/{n}/conversations/{conv}/messages'
    assert c.post(url,json={'question':'x','source_ids':['a'],'request_key':'test-key-001','owner_id':'other'}).status_code==422
    assert ask(c,n,conv,['a']*11).status_code==422


def test_same_scope_followup_uses_bounded_history(research):
    c,p,v=research;n=notebook(c);sid=indexed(c,n);conv=conversation(c,n)
    events(ask(c,n,conv,[sid]))
    events(ask(c,n,conv,[sid],'same-source-followup','它的预算是多少？'))
    assert p.llm.rewrite_calls==1
    assert len(json.loads(p.llm.last_messages[-1]['content'])['history_for_reference_only'])==2


def test_cross_provider_keys_are_not_forwarded(tmp_path, monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith(('WORKBENCH_MODEL','LLM_','OPENAI_','SILICONFLOW_','EMBEDDING_','RERANKER_')): monkeypatch.delenv(key)
    (tmp_path/'backend').mkdir()
    config_file=tmp_path/'backend/.env'
    config_file.write_text('LLM_PROVIDER=siliconflow\nSILICONFLOW_API_KEY=unit-test-secret\nLLM_BASE_URL=https://api.deepseek.com\nLLM_MODEL=deepseek-flash\n')
    config=load_settings(tmp_path)
    assert not config.llm.configured and config.embedding.configured and config.reranker.configured
    config_file.write_text('LLM_PROVIDER=openai\nOPENAI_API_KEY=unit-test-secret\nEMBEDDING_BASE_URL=https://example.invalid/v1\nRERANKER_BASE_URL=https://example.invalid/v1\n')
    config=load_settings(tmp_path)
    assert config.llm.configured and not config.embedding.configured and not config.reranker.configured


def test_deepseek_thinking_payload_and_dimension_identity(providers):
    from app.infrastructure.models.llm import LLM
    settings=replace(providers.settings,llm=Endpoint('https://api.deepseek.com','deepseek-flash','test'),enable_thinking=False)
    payload=LLM(settings).payload([{'role':'user','content':'x'}],64,True)
    assert payload['thinking']=={'type':'disabled'} and 'enable_thinking' not in payload
    base=Endpoint('https://api.siliconflow.cn/v1','Qwen/Qwen3-Embedding-8B','test')
    assert replace(base,dimensions=4096).profile != replace(base,dimensions=1024).profile


def test_retrieval_citations_bind_to_snapshot_revision(research):
    from app.intelligence.retrieval import retrieve
    c,p,v=research;n=notebook(c);sid=indexed(c,n)
    src=detail(c,n,sid)['source'];chunks=c.app.state.repo.selected_chunks([sid])
    for chunk in chunks: chunk['index_revision']='a-later-revision'
    evidence,_=retrieve('预算',n,[src],chunks,p,v)
    assert evidence and all(x['index_revision']==src['index_revision'] for x in evidence)
