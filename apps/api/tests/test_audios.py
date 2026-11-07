import base64
import io
import json
import shutil
import wave
import zipfile
import xml.etree.ElementTree as ET

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from educrea_api.main import app
from educrea_api.models import ProjectAudio
from educrea_api.services import audios, templates
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import StubGemini, setup_user
from test_auth_projects import register
from test_templates import BROWSER, inline, run_in_browser


def wav():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b'\x00\x00' * 800)
    return buffer.getvalue()


WAV = wav()
TRANSCRIPT = 'Primero suena una flauta. Después, un tambor.'


def upload(client, base, headers, data=WAV, **overrides):
    return client.post(f'{base}/audios', headers=headers, json={
        'filename': 'Mi Audición.wav', 'description': 'Dos instrumentos', 'transcript': TRANSCRIPT,
        'credit': 'Grabación propia', 'audio_base64': base64.b64encode(data).decode(), **overrides})


def test_audio_library_checks_type_metadata_limits_csrf_and_ownership(client, monkeypatch):
    headers, project_id = setup_user(client)
    base = f'/api/projects/{project_id}'
    created = upload(client, base, headers)
    assert created.status_code == 201, created.text
    audio = created.json()
    assert audio['path'] == 'audios/mi-audicion.wav' and audio['media_type'] == 'audio/wav'
    assert 'data' not in audio and 'audio_base64' not in audio
    assert upload(client, base, headers).status_code == 409
    assert upload(client, base, headers, b'<script>bad</script>', filename='fake.mp3').status_code == 422
    assert upload(client, base, headers, transcript='  ').status_code == 422
    assert upload(client, base, headers, transcript='x' * 12001).status_code == 422
    assert upload(client, base, {}, WAV).status_code == 403
    with monkeypatch.context() as patch:
        patch.setattr(audios, 'MAX_AUDIO_BYTES', 32)
        assert upload(client, base, headers).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(audios, 'MAX_AUDIOS', 1)
        assert upload(client, base, headers, WAV + b'new').status_code == 409
    content = client.get(f"{base}/audios/{audio['id']}/content")
    assert content.content == WAV and content.headers['content-type'] == 'audio/wav'
    assert content.headers['x-content-type-options'] == 'nosniff'
    changed = client.patch(f"{base}/audios/{audio['id']}", headers=headers,
                           json={'description': 'Nueva descripción', 'transcript': TRANSCRIPT + ' Fin.'})
    assert changed.status_code == 200 and changed.json()['transcript'].endswith(' Fin.')
    client.post('/api/auth/logout', headers=headers)
    other = {'X-CSRF-Token': register(client, 'other-audio@example.org')}
    for url in (f'{base}/audios', f"{base}/audios/{audio['id']}/content"):
        assert client.get(url).status_code == 404
    assert upload(client, base, other).status_code == 404
    assert client.patch(f"{base}/audios/{audio['id']}", headers=other,
                        json={'description': 'x', 'transcript': 'x'}).status_code == 404
    assert client.delete(f"{base}/audios/{audio['id']}", headers=other).status_code == 404


@pytest.mark.parametrize('data,media_type', [
    (WAV, 'audio/wav'),
    (b'\xff\xfb\x90\x00' + b'\x00' * 200, 'audio/mpeg'),
    (b'ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x00' + b'\x00' * 200, 'audio/mpeg'),
    (b'OggS' + b'\x00' * 24 + b'OpusHead' + b'\x00' * 20, 'audio/ogg'),
    (b'OggS' + b'\x00' * 24 + b'\x01vorbis' + b'\x00' * 20, 'audio/ogg'),
])
def test_supported_audio_signatures(data, media_type):
    assert audios.sniff(data) == media_type


@pytest.mark.parametrize('data', [b'', b'ID3bad tag', b'OggSnot-an-audio-stream', b'RIFFfakeWAVE', b'\xff\xff\xff\xff'])
def test_rejects_incomplete_or_non_audio_signatures(data):
    with pytest.raises(HTTPException):
        audios.sniff(data)


def test_audio_is_packaged_duplicated_and_deleted_with_project(client):
    from conftest import engine
    headers, project_id = setup_user(client)
    base = f'/api/projects/{project_id}'
    client.post(f'{base}/template', headers=headers, json={'template': 'escucha'})
    audio = upload(client, base, headers).json()
    for suffix in ('export.zip', 'export.scorm.zip'):
        response = client.get(f'{base}/{suffix}')
        assert response.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        assert archive.read(audio['path']) == WAV
        assert 'Grabación propia' in archive.read('audios/CREDITOS.txt').decode()
        if suffix == 'export.scorm.zip':
            root = ET.fromstring(archive.read('imsmanifest.xml'))
            namespace = {'c': 'http://www.imsproject.org/xsd/imscp_rootv1p1p2'}
            listed = {item.get('href') for item in root.findall('c:resources/c:resource/c:file', namespace)}
            assert {audio['path'], 'audios/CREDITOS.txt'} <= listed
            assert 'EduScorm.complete' not in archive.read('index.html').decode()
    copy = client.post(f'{base}/duplicate', headers=headers).json()
    copied = client.get(f"/api/projects/{copy['id']}/audios").json()
    assert len(copied) == 1 and copied[0]['path'] == audio['path']
    assert copied[0]['id'] != audio['id'] and copied[0]['transcript'] == TRANSCRIPT
    assert client.delete(f"{base}/audios/{audio['id']}", headers=headers).status_code == 204
    assert client.get(f"{base}/audios/{audio['id']}/content").status_code == 404
    assert client.delete(f"/api/projects/{copy['id']}", headers=headers).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(ProjectAudio)) == 0


def test_listening_ai_uses_text_only_and_checks_actual_audio_and_transcript(client):
    headers, project_id = setup_user(client)
    base = f'/api/projects/{project_id}'
    client.post(f'{base}/template', headers=headers, json={'template': 'escucha'})
    missing = client.post(f'{base}/ai/from-brief', headers=headers)
    assert missing.status_code == 409
    audio = upload(client, base, headers).json()
    data = templates.parse_data(templates.initial_files('escucha', {})['datos.js'])
    data.update(audio=audio['path'], transcript=TRANSCRIPT)
    data['questions'] = [{'text': '¿Qué suena primero?', 'options': ['Flauta', 'Tambor'], 'answer': 0,
                          'feedback': 'La descripción sitúa la flauta al principio.'}]
    captured = {}
    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured['prompt'] = prompt
            return await super().generate(key, model, prompt)
    def provider():
        return Capture(json.dumps({'summary': 'Audición', 'changes': [
            {'path': 'datos.js', 'content': templates.data_js(data)}]}))
    app.dependency_overrides[get_gemini_provider] = provider
    applied = client.post(f'{base}/ai/from-brief', headers=headers).json()
    assert applied['status'] == 'applied', applied
    assert 'available_audio' in captured['prompt'] and TRANSCRIPT in captured['prompt']
    assert base64.b64encode(WAV).decode() not in captured['prompt']
    data['audio'] = 'audios/inventado.mp3'
    assert client.post(f'{base}/ai/from-brief', headers=headers).json()['status'] == 'pending'
    data['audio'] = audio['path']; data['transcript'] = 'Contenido inventado.'
    assert client.post(f'{base}/ai/from-brief', headers=headers).json()['status'] == 'pending'
    data['audio'] = 'https://example.org/track.mp3'
    assert templates.validate_data('escucha', templates.data_js(data))


@pytest.mark.skipif(not (BROWSER and shutil.which('bwrap')), reason='chromium/bwrap not installed')
@pytest.mark.parametrize('language', ['es', 'va'])
def test_listening_player_transcript_and_scorm_in_browser(language):
    files = templates.initial_files('escucha', {'title': 'Audición', 'language': language})
    data = templates.parse_data(files['datos.js'])
    data.update(audio='data:audio/wav;base64,' + base64.b64encode(WAV).decode(), transcript=TRANSCRIPT)
    files['datos.js'] = templates.data_js(data)
    actions = """
      var audio = document.querySelector('audio');
      audio.onloadedmetadata = function () { document.body.setAttribute('data-audio-loaded', 'yes') };
      if (audio.readyState >= 1) audio.onloadedmetadata();
      if (!audio.controls || audio.autoplay || !audio.getAttribute('aria-label')) throw Error('player');
      if (document.querySelector('details').open) throw Error('transcript visible');
      document.querySelector('summary').click();
      if (!document.querySelector('details').open) throw Error('transcript toggle');
      window.EduScorm = {score: function(n, total) { document.body.setAttribute('data-score', n + '/' + total) }};
      document.querySelector('input[value="0"]').click();
      document.querySelector('button.principal').click();
      document.body.setAttribute('data-tested', 'ok');
    """
    dom = run_in_browser(inline(files).replace('</body>', f'<script>{actions}</script></body>'))
    assert 'data-tested="ok"' in dom and 'data-score="1/1"' in dom
    assert TRANSCRIPT in dom and 'data-audio-loaded="yes"' in dom


def test_audio_migration_is_reversible(tmp_path):
    from sqlalchemy import create_engine, inspect
    import os
    database = f'sqlite:///{tmp_path / "migration.db"}'
    # Alembic env obtains its URL from settings, so use a connection-free subprocess environment.
    import subprocess
    env = {**os.environ, 'EDUCREA_DATABASE_URL': database}
    for target in ('0018_project_videos', 'head'):
        subprocess.run(['.venv/bin/alembic', 'upgrade', target], env=env, check=True, capture_output=True)
    engine = create_engine(database)
    assert 'project_audios' in inspect(engine).get_table_names()
    subprocess.run(['.venv/bin/alembic', 'downgrade', '0018_project_videos'], env=env, check=True, capture_output=True)
    assert 'project_audios' not in inspect(engine).get_table_names()
    subprocess.run(['.venv/bin/alembic', 'upgrade', 'head'], env=env, check=True, capture_output=True)
    assert 'project_audios' in inspect(engine).get_table_names()
    engine.dispose()
