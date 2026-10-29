from concurrent.futures import ThreadPoolExecutor
import json
import socket
import sqlite3
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.main import create_app
from app.infrastructure.database.connection import build_engine
from app.infrastructure.database.migrate import migrate
from app.application.note_export import reference_labels, filename_for
from test_ingestion import notebook


def answer(c, nid, content='预算是 **120 元**。[S1]', status='complete', title='项目预算是多少？'):
    repo=c.app.state.repo
    conv=repo.create_conversation(nid,'notes fixture')
    row,_=repo.reserve_message(conv['id'],'notes-fixture-request','fingerprint',title,['synthetic-source'])
    if status=='complete':
        evidence=dict(label='S1',chunk_id='synthetic-chunk',source_id='synthetic-source',filename='预算资料.md',
            text='原文：预算是120元。',page_start=None,page_end=None,char_start=0,char_end=12,index_revision='snapshot-v1')
        repo.finish_message(row['id'],content,[evidence],[])
    elif status!='running': repo.fail_message(row['id'],status,'test failure')
    return repo.message(row['id'])


def create_note(c,n,m,**kwargs):
    return c.post(f'/api/notebooks/{n}/notes',json={'origin_message_id':m['id'],**kwargs})


def edit(c,n,note,**kwargs):
    body={'title':note['title'],'body_markdown':note['body_markdown'],'revision':note['revision'],**kwargs}
    return c.patch(f"/api/notebooks/{n}/notes/{note['id']}",json=body)


def test_save_snapshot_and_duplicate_preserves_edits(client):
    n=notebook(client);m=answer(client,n)
    first=create_note(client,n,m);assert first.status_code==201
    note=first.json()['note'];assert note['title']=='项目预算是多少？' and note['revision']==1
    assert note['body_markdown']==m['content'] and note['citations'][0]['text']=='原文：预算是120元。'
    changed=edit(client,n,note,title='我的研究笔记',body_markdown='自己的分析 [S1]').json()
    repeated=create_note(client,n,m,title='不要覆盖我的标题')
    assert repeated.status_code==200 and repeated.json()['created'] is False
    assert repeated.json()['note']==changed
    assert client.app.state.repo.message(m['id'])==m
    rows=client.get(f'/api/notebooks/{n}/notes').json()
    assert len(rows)==1 and 'body_markdown' not in rows[0] and 'citations' not in rows[0]


@pytest.mark.parametrize('status',['running','failed','interrupted'])
def test_only_complete_assistant_can_save(client,status):
    n=notebook(client);m=answer(client,n,status=status)
    assert create_note(client,n,m).status_code==409
    user=client.app.state.repo.messages(m['conversation_id'])[0]
    assert create_note(client,n,user).status_code==409
    assert client.get(f'/api/notebooks/{n}/notes').json()==[]


def test_scope_enforced_for_every_note_endpoint(client):
    n=notebook(client);other=notebook(client);m=answer(client,n);note=create_note(client,n,m).json()['note']
    assert create_note(client,other,m).status_code==404
    assert client.get(f"/api/notebooks/{other}/notes/{note['id']}").status_code==404
    assert edit(client,other,note).status_code==404
    assert client.get(f"/api/notebooks/{other}/notes/{note['id']}/export?revision=1").status_code==404
    private=client.app.state.repo.create_notebook('different-owner','private')
    assert client.get(f"/api/notebooks/{private['id']}/notes").status_code==404
    assert client.get('/api/notebooks/missing/notes').status_code==404
    assert client.post(f'/api/notebooks/{n}/notes',json={'origin_message_id':'missing'}).status_code==404


def test_atomic_revision_conflict(client):
    n=notebook(client);note=create_note(client,n,answer(client,n)).json()['note']
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda title:edit(client,n,note,title=title),['first','second']))
    assert sorted(r.status_code for r in responses)==[200,409]
    saved=client.get(f"/api/notebooks/{n}/notes/{note['id']}").json()
    assert saved['revision']==2
    assert saved['title']==next(r.json()['title'] for r in responses if r.status_code==200)
    assert edit(client,n,note,title='stale').status_code==409
    assert client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=1").status_code==409


def test_concurrent_save_is_idempotent(client):
    n=notebook(client);m=answer(client,n)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _:create_note(client,n,m),range(4)))
    assert sorted(r.status_code for r in responses)==[200,200,200,201]
    assert len({r.json()['note']['id'] for r in responses})==1


def test_export_latest_body_and_used_evidence_only(client):
    n=notebook(client);m=answer(client,n);note=create_note(client,n,m).json()['note']
    updated=edit(client,n,note,title='中文 / 标题:研究',body_markdown='## 我的结论\n\n预算需要复核。[S1]\n').json()
    response=client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=2")
    assert response.status_code==200 and response.headers['x-note-revision']=='2'
    assert response.headers['content-type'].startswith('text/markdown')
    assert response.headers['x-content-type-options']=='nosniff'
    assert response.content.decode('utf-8')==response.text
    assert updated['body_markdown'] in response.text
    assert '### S1 · 预算资料' in response.text and '原文：预算是120元。' in response.text
    assert 'synthetic-source' not in response.text and 'synthetic-chunk' not in response.text
    assert '/Users/' not in response.text and '/api/' not in response.text
    name=unquote(response.headers['content-disposition'].split("filename*=UTF-8''")[1])
    assert name.endswith('.md') and '/' not in name and ':' not in name
    removed=edit(client,n,updated,body_markdown='不引用原文的个人笔记').json()
    export=client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=3")
    assert export.status_code==200 and '原文：预算是120元。' not in export.text
    assert removed['citations']==note['citations']  # snapshot is preserved, not deleted


def test_unknown_reference_can_save_but_not_export(client):
    n=notebook(client);note=create_note(client,n,answer(client,n)).json()['note']
    bad=edit(client,n,note,body_markdown='错误引用 [S99]').json()
    assert bad['invalid_labels']==['S99']
    response=client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=2")
    assert response.status_code==422 and response.json()['code']=='invalid_citations'
    good=edit(client,n,bad,body_markdown='字面示例：`[S99]`\n\n```text\n[S98]\n```\n\n真实引用 [S1]').json()
    assert good['invalid_labels']==[] and good['used_labels']==['S1']
    assert client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=3").status_code==200


@pytest.mark.parametrize('title',['','   ','a'*121,'bad\r\nname','bad\x00name'])
def test_invalid_titles(client,title):
    n=notebook(client);m=answer(client,n)
    assert create_note(client,n,m,title=title).status_code==422
    note=create_note(client,n,m).json()['note']
    assert edit(client,n,note,title=title).status_code==422


def test_body_limit_and_snapshot_fields_cannot_be_changed(client):
    n=notebook(client);note=create_note(client,n,answer(client,n)).json()['note']
    assert edit(client,n,note,body_markdown='x'*100001).status_code==422
    assert edit(client,n,note,citations=[]).status_code==422
    assert edit(client,n,note,owner_id='other').status_code==422
    assert edit(client,n,note,revision=0).status_code==422
    assert client.get(f"/api/notebooks/{n}/notes/{note['id']}/export").status_code==422


def test_snapshot_independent_and_persists_after_restart(client,config):
    n=notebook(client);m=answer(client,n);note=create_note(client,n,m).json()['note']
    # Change the original evidence fixture; note must remain a save-time snapshot.
    engine=client.app.state.repo.session.kw['bind']
    with engine.begin() as s:s.execute(text("UPDATE citations SET text='changed' WHERE message_id=:id"),{'id':m['id']})
    assert client.get(f"/api/notebooks/{n}/notes/{note['id']}").json()['citations']==note['citations']


def test_full_restart_and_no_model_or_index_calls(config,monkeypatch):
    def blocked(*args,**kwargs):raise AssertionError('Notes must not make network calls')
    monkeypatch.setattr(socket.socket,'connect',blocked)
    with TestClient(create_app(config,run_worker=False)) as c:
        n=notebook(c);m=answer(c,n);note=create_note(c,n,m).json()['note']
        assert edit(c,n,note,body_markdown='编辑后的笔记 [S1]').status_code==200
    with TestClient(create_app(config,run_worker=False)) as c:
        stored=c.get(f"/api/notebooks/{n}/notes/{note['id']}").json()
        assert stored['revision']==2 and stored['body_markdown']=='编辑后的笔记 [S1]'
        assert c.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=2").status_code==200
        engine=c.app.state.repo.session.kw['bind']
        with engine.connect() as s:
            assert s.execute(text('SELECT COUNT(*) FROM jobs')).scalar_one()==0
            assert s.execute(text('SELECT COUNT(*) FROM sources')).scalar_one()==0
        assert not config.vector_dir.exists()


def test_storage_failure_does_not_claim_saved(client,monkeypatch):
    n=notebook(client);note=create_note(client,n,answer(client,n)).json()['note']
    def fail(*args):raise SQLAlchemyError('simulated local failure')
    monkeypatch.setattr(client.app.state.notes.repo,'update',fail)
    assert edit(client,n,note,title='must not save').status_code==503
    assert client.get(f"/api/notebooks/{n}/notes/{note['id']}").json()['revision']==1


def test_safe_export_title_and_evidence_fence(client):
    n=notebook(client);m=answer(client,n)
    engine=client.app.state.repo.session.kw['bind']
    evidence='```\n<script>alert(1)</script>\n````'
    with engine.begin() as s:s.execute(text('UPDATE citations SET text=:t WHERE message_id=:m'),{'t':evidence,'m':m['id']})
    note=create_note(client,n,m,title='<script>标题</script> [test]').json()['note']
    result=client.get(f"/api/notebooks/{n}/notes/{note['id']}/export?revision=1")
    assert result.text.startswith('# &lt;script&gt;标题&lt;/script&gt; \\[test\\]')
    assert '`````text\n'+evidence+'\n`````' in result.text
    assert '\x01' not in result.text
    assert filename_for('CON')=='研究笔记-CON.md'


def test_migrate_v2_to_v3_preserves_messages_and_backup(config):
    config.data_dir.mkdir(parents=True)
    folder=Path(__file__).parents[1]/'app/infrastructure/database/migrations'
    with sqlite3.connect(config.database_path) as db:
        db.executescript((folder/'001_initial.sql').read_text());db.executescript((folder/'002_research.sql').read_text())
        db.execute("INSERT INTO notebooks VALUES ('n','local-demo','existing','time','time')")
        db.execute('PRAGMA user_version=2')
    engine=build_engine(config)
    from app.infrastructure.database.rag_repository import RagRepository
    repo=RagRepository(engine)
    conv=repo.create_conversation('n','old conversation')
    row,_=repo.reserve_message(conv['id'],'old-request','old-fingerprint','old question',[])
    repo.finish_message(row['id'],'old answer',[],[])
    try:
        migrate(engine)
        with engine.connect() as c:
            assert c.execute(text('SELECT COUNT(*) FROM messages')).scalar_one()==2
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one()==3
            assert c.execute(text('SELECT name FROM notebooks')).scalar_one()=='existing'
            assert c.execute(text('SELECT COUNT(*) FROM notes')).scalar_one()==0
        backups=list(config.data_dir.glob('*.v2-backup-*'));assert len(backups)==1
        with sqlite3.connect(backups[0]) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==2
    finally:engine.dispose()


def test_reference_parser_matches_markdown_semantics():
    assert reference_labels('**[S1]** and [S2] `literal [S99]`\n\n```\n[S98]\n```')==['S1','S2']
    assert reference_labels('[link [S8]](https://example.com) ![image [S9]](x)\n\n<script>[S7]</script>')==[]


def test_url_markers_are_not_citations():
    assert reference_labels('https://example.com/[S99]')==[]


def test_v3_migration_failure_rolls_back_existing_v2(config,monkeypatch):
    config.data_dir.mkdir(parents=True)
    folder=Path(__file__).parents[1]/'app/infrastructure/database/migrations'
    with sqlite3.connect(config.database_path) as db:
        db.executescript((folder/'001_initial.sql').read_text());db.executescript((folder/'002_research.sql').read_text())
        db.execute("INSERT INTO notebooks VALUES ('keep','local-demo','kept','time','time')")
        db.execute('PRAGMA user_version=2')
    engine=build_engine(config);original=Path.read_text
    def broken(path,*args,**kwargs):
        if path.name=='003_notes.sql':return 'CREATE TABLE transient (id TEXT); INVALID SQL;'
        return original(path,*args,**kwargs)
    try:
        monkeypatch.setattr(Path,'read_text',broken)
        with pytest.raises(SQLAlchemyError):migrate(engine)
        with engine.connect() as c:
            assert c.exec_driver_sql('PRAGMA user_version').scalar_one()==2
            assert c.execute(text('SELECT name FROM notebooks')).scalar_one()=='kept'
            assert c.execute(text("SELECT name FROM sqlite_master WHERE name='transient'")).all()==[]
    finally:engine.dispose()


def test_create_failure_rolls_back_without_changing_answer(client):
    from sqlalchemy import event
    n=notebook(client);m=answer(client,n);engine=client.app.state.notes.repo.session.kw['bind']
    def fail(_conn,_cursor,statement,_parameters,_context,_executemany):
        if 'INSERT INTO notes' in statement:raise SQLAlchemyError('simulated note write failure')
    event.listen(engine,'before_cursor_execute',fail)
    try:assert create_note(client,n,m).status_code==503
    finally:event.remove(engine,'before_cursor_execute',fail)
    assert client.get(f'/api/notebooks/{n}/notes').json()==[]
    assert client.app.state.repo.message(m['id'])==m
    assert create_note(client,n,m).status_code==201
