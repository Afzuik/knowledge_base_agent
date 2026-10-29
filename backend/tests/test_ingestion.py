from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
import socket
import time

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from sqlalchemy import text, event, inspect
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.config import Settings
from app.main import create_app
from app.infrastructure.database.connection import build_engine
from app.infrastructure.database.migrate import migrate
from app.infrastructure.database.models import Base
from app.infrastructure.storage.local_files import LocalFiles
from app.infrastructure.tasks.local_runner import process_lock
from app.intelligence.parsing import parse_document, ParseError
from app.intelligence.chunking import chunk_document


def notebook(c, name='研究专题'):
    r = c.post('/api/notebooks', json={'name': name})
    assert r.status_code == 201, r.text
    return r.json()['id']


def upload(c, n, name='note.md', content='资料内容：蓝色是示例颜色。'.encode()):
    return c.post(f'/api/notebooks/{n}/sources', files={'file': (name, content)})


def detail(c, n, sid):
    return c.get(f'/api/notebooks/{n}/sources/{sid}').json()


def chunks(c, n, sid):
    return c.get(f'/api/notebooks/{n}/sources/{sid}/chunks')


def pdf_bytes(texts=('First page fact.', 'Second page fact.'), encrypted=False):
    writer = PdfWriter()
    for value in texts:
        page = writer.add_blank_page(width=300, height=300)
        if value:
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'):
                DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})})
            stream = DecodedStreamObject()
            stream.set_data(f'BT /F1 12 Tf 20 200 Td ({value}) Tj ET'.encode())
            page[NameObject('/Contents')] = writer._add_object(stream)
    if encrypted:
        writer.encrypt('test-password')
    out = BytesIO(); writer.write(out)
    return out.getvalue()


def test_versioned_four_tables_and_constraints(config):
    engine = build_engine(config)
    try:
        migrate(engine); migrate(engine)
        assert set(inspect(engine).get_table_names()) == {'notebooks', 'sources', 'chunks', 'jobs', 'conversations', 'messages', 'citations'}
        for table in Base.metadata.sorted_tables:
            assert {c['name'] for c in inspect(engine).get_columns(table.name)} == set(table.columns.keys())
        with engine.connect() as s:
            assert s.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
            assert s.exec_driver_sql('PRAGMA user_version').scalar_one() == 2
            with pytest.raises(IntegrityError):
                s.execute(text("INSERT INTO chunks VALUES ('x','nonexistent',0,'text',NULL,NULL,0,4)"))
    finally:
        engine.dispose()


@pytest.mark.parametrize('body', [{'name': ''}, {'name': '   '}, {'name': 'x' * 101}, {'name': 'ok', 'owner_id': 'other'}])
def test_invalid_notebook_inputs(client, body):
    assert client.post('/api/notebooks', json=body).status_code == 422


def test_create_list_scope_and_persistence(config):
    with TestClient(create_app(config, run_worker=False)) as c:
        n = notebook(c, '  学习  ')
        notebook(c, '学习')  # same name is allowed
        other = c.app.state.repo.create_notebook('other-owner', 'private')
        rows = c.get('/api/notebooks').json()
        assert len(rows) == 2 and rows[0]['name'] == '学习'
        assert c.get('/api/notebooks/' + other['id']).status_code == 404
        assert upload(c, other['id']).status_code == 404
    with TestClient(create_app(config, run_worker=False)) as c:
        assert c.get('/api/notebooks/' + n).json()['name'] == '学习'
        assert len(c.get('/api/notebooks').json()) == 2


@pytest.mark.parametrize('name,body', [('资料.md', '# 标题\n正文内容。'.encode()), ('说明.TXT', b'\xef\xbb\xbfHello world')])
def test_text_pipeline(client, config, name, body):
    n = notebook(client); result = upload(client, n, name, body)
    assert result.status_code == 202
    src = result.json()['source']; sid = src['id']
    assert 'storage_key' not in src and 'owner_id' not in src
    assert src['status'] == 'queued' and src['index_status'] == 'not_indexed'
    assert chunks(client, n, sid).status_code == 409
    assert client.app.state.ingestion.run_once()
    source = detail(client, n, sid)
    assert source['source']['status'] == 'parsed'
    assert source['jobs'][0]['status'] == 'succeeded'
    rows = chunks(client, n, sid).json()['items']
    assert rows and all(x['page_start'] is None for x in rows)
    assert (config.uploads_dir / sid).read_bytes() == body
    assert not client.app.state.ingestion.run_once()


def test_pdf_pages_and_chunk_offsets(client):
    n = notebook(client); sid = upload(client, n, 'two.pdf', pdf_bytes()).json()['source']['id']
    client.app.state.ingestion.run_once()
    assert detail(client, n, sid)['source']['page_count'] == 2
    rows = chunks(client, n, sid).json()['items']
    assert [r['page_start'] for r in rows] == [1, 2]
    assert 'First page fact' in rows[0]['text'] and 'Second page fact' in rows[1]['text']


@pytest.mark.parametrize('name,content,code', [
    ('bad.txt', b'\xff\xfeabc', 'invalid_encoding'),
    ('binary.txt', b'\x00abc', 'invalid_text'),
    ('empty.md', b'   \n', 'no_text'),
    ('bad.pdf', b'not pdf', 'invalid_pdf'),
    ('broken.pdf', b'%PDF-1.7\nbroken', 'invalid_pdf'),
    ('scan.pdf', pdf_bytes(('',)), 'no_text'),
    ('secret.pdf', pdf_bytes(encrypted=True), 'encrypted_pdf'),
])
def test_parse_failures_and_retry_history(client, name, content, code):
    n = notebook(client); sid = upload(client, n, name, content).json()['source']['id']
    client.app.state.ingestion.run_once()
    row = detail(client, n, sid)
    assert row['source']['status'] == 'failed' and row['source']['error_code'] == code
    assert chunks(client, n, sid).status_code == 409
    assert client.post(f'/api/notebooks/{n}/sources/{sid}/retry').status_code == 202
    assert client.post(f'/api/notebooks/{n}/sources/{sid}/retry').status_code == 409
    client.app.state.ingestion.run_once()
    assert len(detail(client, n, sid)['jobs']) == 2


def test_upload_limits_and_sanitized_name(client, config):
    n = notebook(client)
    assert upload(client, n, 'zero.txt', b'').status_code == 422
    assert upload(client, n, 'app.exe', b'data').status_code == 415
    assert upload(client, n, 'big.txt', b'x' * (config.max_upload_bytes + 1)).status_code == 422
    assert upload(client, n, 'huge.txt', b'x' * (config.max_upload_bytes + 100000)).status_code == 413
    row = upload(client, n, '../../escape.txt', b'safe text').json()['source']
    assert row['filename'] == 'escape.txt'
    assert (config.uploads_dir / row['id']).exists()
    assert not (config.data_dir.parent / 'escape.txt').exists()
    assert list((config.uploads_dir / '.pending').iterdir()) == []


def test_duplicate_and_cross_notebook_content(client, config):
    a = notebook(client); b = notebook(client)
    first = upload(client, a).json()['source']['id']
    duplicate = upload(client, a, 'different-name.txt')
    assert duplicate.status_code == 200 and duplicate.json()['duplicate'] is True
    assert duplicate.json()['source']['id'] == first
    different = upload(client, a, 'note.md', b'different content')
    assert different.status_code == 202
    assert upload(client, b).status_code == 202
    assert len(detail(client, a, first)['jobs']) == 1


def test_concurrent_duplicate_uploads(client, config):
    n = notebook(client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(lambda _: upload(client, n), range(4)))
    assert sorted(r.status_code for r in responses) == [200, 200, 200, 202]
    assert len({r.json()['source']['id'] for r in responses}) == 1
    files = [p for p in config.uploads_dir.iterdir() if p.is_file()]
    assert len(files) == 1


def test_cross_notebook_source_requests_rejected(client):
    a = notebook(client); b = notebook(client)
    sid = upload(client, a).json()['source']['id']
    client.app.state.ingestion.run_once()
    for suffix in ['', '/chunks']:
        assert client.get(f'/api/notebooks/{b}/sources/{sid}{suffix}').status_code == 404
    assert client.post(f'/api/notebooks/{b}/sources/{sid}/retry').status_code == 404
    assert client.get('/api/notebooks/missing/sources').status_code == 404
    assert client.get(f'/api/notebooks/{a}/sources/{sid}/chunks?limit=1000').status_code == 422


def test_write_failure_compensates_files(client, config, monkeypatch):
    n = notebook(client)
    def fail(*a, **kw): raise SQLAlchemyError('simulated database failure')
    monkeypatch.setattr(client.app.state.repo, 'register', fail)
    assert upload(client, n).status_code == 503
    assert not [p for p in config.uploads_dir.iterdir() if p.is_file()]
    assert not list((config.uploads_dir / '.pending').iterdir())
    assert client.get(f'/api/notebooks/{n}/sources').json() == []


def test_disk_failure_is_not_success(client, config, monkeypatch):
    n = notebook(client)
    def fail(*a, **kw): raise OSError('simulated disk full')
    monkeypatch.setattr(client.app.state.sources.files, 'promote', fail)
    assert upload(client, n).status_code == 503
    assert list((config.uploads_dir / '.pending').iterdir()) == []


def test_partial_chunk_write_rolls_back_and_retry_is_idempotent(client):
    n = notebook(client)
    sid = upload(client, n, content=('many words ' * 300).encode()).json()['source']['id']
    engine = client.app.state.repo.session.kw['bind']
    failed = False
    def inject(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal failed
        if 'INSERT INTO chunks' in statement and not failed:
            failed = True
            raise SQLAlchemyError('simulated chunk transaction failure')
    event.listen(engine, 'before_cursor_execute', inject)
    try:
        client.app.state.ingestion.run_once()
    finally:
        event.remove(engine, 'before_cursor_execute', inject)
    assert detail(client, n, sid)['source']['status'] == 'failed'
    assert client.app.state.repo.chunks(sid, 0, 100) == []
    assert client.post(f'/api/notebooks/{n}/sources/{sid}/retry').status_code == 202
    client.app.state.ingestion.run_once()
    rows = chunks(client, n, sid).json()['items']
    assert len(rows) > 1 and len({r['id'] for r in rows}) == len(rows)
    assert detail(client, n, sid)['source']['chunk_count'] == len(rows)
    assert client.post(f'/api/notebooks/{n}/sources/{sid}/retry').status_code == 409


def test_restart_recovers_jobs_missing_files_and_orphans(config):
    with TestClient(create_app(config, run_worker=False)) as c:
        n = notebook(c)
        running = upload(c, n, content=b'running').json()['source']['id']
        c.app.state.repo.claim()
        waiting = upload(c, n, content=b'waiting').json()['source']['id']
        missing = upload(c, n, content=b'missing').json()['source']['id']
        (config.uploads_dir / missing).unlink()
        (config.uploads_dir / ('a' * 32)).write_text('orphan')
        (config.uploads_dir / '.pending' / 'abandoned.part').write_text('temporary')
    with TestClient(create_app(config, run_worker=False)) as c:
        assert detail(c, n, running)['source']['error_code'] == 'interrupted'
        assert detail(c, n, waiting)['source']['status'] == 'queued'
        assert detail(c, n, missing)['source']['error_code'] == 'missing_file'
        assert c.post(f'/api/notebooks/{n}/sources/{missing}/retry').status_code == 409
        assert not (config.uploads_dir / ('a' * 32)).exists()
        assert not list((config.uploads_dir / '.pending').iterdir())
        c.app.state.ingestion.run_once()
        assert detail(c, n, waiting)['source']['status'] == 'parsed'
        assert c.post(f'/api/notebooks/{n}/sources/{running}/retry').status_code == 202
        c.app.state.ingestion.run_once()
    with TestClient(create_app(config, run_worker=False)) as c:
        assert chunks(c, n, running).status_code == 200
        assert chunks(c, n, waiting).status_code == 200


def test_real_background_worker_and_no_model_network(config, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('Unexpected network/model call')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    with TestClient(create_app(config)) as c:
        n = notebook(c); sid = upload(c, n).json()['source']['id']
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            assert c.get('/api/health').status_code == 200
            if detail(c, n, sid)['source']['status'] == 'parsed': break
            time.sleep(0.05)
        assert detail(c, n, sid)['source']['status'] == 'parsed'


def test_slow_parser_does_not_block_api(config, monkeypatch):
    from threading import Event
    import app.application.ingestion as ingestion
    entered, release = Event(), Event()
    original = ingestion.parse_document
    def slow(*args):
        entered.set(); assert release.wait(3)
        return original(*args)
    monkeypatch.setattr(ingestion, 'parse_document', slow)
    with TestClient(create_app(config)) as c:
        n = notebook(c); upload(c, n)
        try:
            assert entered.wait(2)
            assert c.get('/api/notebooks').status_code == 200
            assert c.get('/api/health').status_code == 200
        finally:
            release.set()


def test_parser_limits_and_stable_chunks():
    with pytest.raises(ParseError, match='字符数'):
        parse_document(b'hello world', 'txt', max_chars=4)
    with pytest.raises(ParseError, match='页数'):
        parse_document(pdf_bytes(), 'pdf', max_pages=1)
    doc = parse_document(('甲乙丙丁' * 100).encode(), 'txt')
    a = chunk_document('source-a', doc, size=80, overlap=10)
    assert a == chunk_document('source-a', doc, size=80, overlap=10)
    assert a[0]['id'] != chunk_document('source-b', doc, size=80, overlap=10)[0]['id']
    for item in a:
        assert item['text'] == doc.pages[0].text[item['char_start']:item['char_end']]


def test_storage_rejects_paths_and_symlinks(config, tmp_path):
    files = LocalFiles(config.uploads_dir)
    with pytest.raises(ValueError): files.path('../../bad')
    key = 'b' * 32
    (config.uploads_dir / key).symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError): files.path(key)


def test_second_process_lock_rejected(config):
    with process_lock(config.data_dir):
        with pytest.raises(RuntimeError, match='already used'):
            with process_lock(config.data_dir): pass


def test_unknown_schema_is_not_overwritten(config):
    engine = build_engine(config)
    try:
        with engine.begin() as c: c.exec_driver_sql('PRAGMA user_version=999')
        with pytest.raises(RuntimeError, match='Unsupported'): migrate(engine)
        with engine.connect() as c: assert c.exec_driver_sql('PRAGMA user_version').scalar_one() == 999
    finally: engine.dispose()


def test_changed_original_is_rejected(client, config):
    n = notebook(client)
    sid = upload(client, n).json()['source']['id']
    (config.uploads_dir / sid).write_text('tampered')
    client.app.state.ingestion.run_once()
    assert detail(client, n, sid)['source']['error_code'] == 'file_changed'
    assert chunks(client, n, sid).status_code == 409


def test_chunk_pagination(client):
    n = notebook(client)
    sid = upload(client, n, content=('内容' * 3000).encode()).json()['source']['id']
    client.app.state.ingestion.run_once()
    url = f'/api/notebooks/{n}/sources/{sid}/chunks'
    first = client.get(url + '?limit=2').json()
    second = client.get(url + '?offset=2&limit=2').json()
    assert first['total'] > 4
    assert [x['ordinal'] for x in first['items']] == [0, 1]
    assert [x['ordinal'] for x in second['items']] == [2, 3]


def test_failed_migration_rolls_back(config, monkeypatch):
    from pathlib import Path
    engine = build_engine(config)
    original = Path.read_text
    def broken(path, *args, **kwargs):
        if path.name == '001_initial.sql':
            return 'CREATE TABLE transient (id TEXT); THIS IS INVALID SQL;'
        return original(path, *args, **kwargs)
    try:
        monkeypatch.setattr(Path, 'read_text', broken)
        with pytest.raises(SQLAlchemyError): migrate(engine)
        assert inspect(engine).get_table_names() == []
        with engine.connect() as c: assert c.exec_driver_sql('PRAGMA user_version').scalar_one() == 0
    finally: engine.dispose()
