import io
import json
import shutil
import subprocess
import zipfile

import pytest

from educrea_api.main import app
from educrea_api.services import templates
from educrea_api.services.ai.providers.gemini import get_gemini_provider
from test_ai import StubGemini, setup_user
from test_templates import BROWSER, inline, run_in_browser

PUZZLES = ['sopa_letras', 'crucigrama']


@pytest.mark.parametrize('template_id', PUZZLES)
@pytest.mark.parametrize('words', [
    [{'word': 'Sol', 'clue': 'Estrella.'}],
    [{'word': 'Sol', 'clue': 'Estrella.'}, {'word': 'Sól', 'clue': 'Duplicado.'}],
    [{'word': 'l·l', 'clue': 'a'}, {'word': 'll', 'clue': 'b'}],
    [{'word': 'a', 'clue': 'a'}, {'word': 'Luna', 'clue': 'b'}],
    [{'word': 'A' * 15, 'clue': 'a'}, {'word': 'Luna', 'clue': 'b'}],
    [{'word': '<script>', 'clue': 'a'}, {'word': 'Luna', 'clue': 'b'}],
    [{'word': 'Sol', 'clue': '  '}, {'word': 'Luna', 'clue': 'b'}],
    [{'word': 'Sol', 'clue': 'a'}] * 13,
])
def test_puzzles_reject_invalid_or_duplicate_vocabulary(template_id, words):
    assert templates.validate_data(template_id, templates.data_js({'title': 'X', 'words': words}))


@pytest.mark.parametrize('word,expected', [
    ('Música', 'MUSICA'), ('cançó', 'CANÇO'), ('Niño', 'NIÑO'), ('l·l', 'LL'),
    ('New York', 'NEWYORK'), ('l’aigua', 'LAIGUA'), ('pin-güí', 'PINGUI'),
    ('nin\u0303o', 'NIÑO'), ('fac\u0327ana', 'FAÇANA'),
])
def test_grid_spelling_normalizes_accents_but_preserves_enye_and_cedilla(word, expected):
    assert templates.puzzle_word(word) == expected


@pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
def test_layouts_keep_every_word_consistent_including_disconnected_and_maximum_sets():
    # Execute only our fixed, reviewed layout helper; no model-generated code.
    script = r"""
      const fs = require('fs'), vm = require('vm');
      global.window = {EDU: {shuffle: words => words.slice().reverse()}};
      vm.runInThisContext(fs.readFileSync(process.argv[1], 'utf8'));
      const P = window.EDU.puzzles;
      const sets = [['SOL', 'LUNA', 'TIERRA'], ['AB', 'CD', 'EF'], ['CASA', 'ASA', 'SALA'],
        ['ABCDEFGHIJKLMNOPQRSTUVWXYZ'.slice(0,14), 'ÑANDU', 'CANÇO', 'PINGUI', 'MUSICA', 'ORQUESTA',
         'TROMPETA', 'VIOLONCELO', 'TAMBOR', 'SAXOFON', 'CLARINETE', 'FLAUTA']];
      for (let n=0; n<20; n++) {
        const words=[];
        for (let w=0; w<12; w++) {
          let word=''; for (let i=0; i<14; i++) word += 'ABCDEÑÇ'[(n*13+w*3+i*i+i*w)%7];
          words.push(word);
        }
        sets.push([...new Set(words)]);
      }
      function assert(ok, msg) { if (!ok) throw Error(msg) }
      for (const words of sets) {
        for (const random of [() => 0, () => .999999, Math.random]) {
          const oldRandom=Math.random; Math.random=random;
          const board=P.searchGrid(words); Math.random=oldRandom;
          assert(board.placements.length===words.length, 'search omitted word');
          for (const p of board.placements) {
            let actual='';
            for (let i=0; i<p.word.length; i++) actual += board.grid[p.row+p.dr*i][p.col+p.dc*i];
            assert(actual===p.word, 'search collision or bounds');
          }
        }
        const layout=P.crossword(words), cells=new Map(), edges=new Set();
        assert(new Set(layout.placements.map(p=>p.index)).size===words.length, 'crossword omitted word');
        for (const p of layout.placements) {
          for (let i=0; i<p.word.length; i++) {
            const r=p.row+p.dr*i,c=p.col+p.dc*i,k=r+','+c;
            assert(r>=0 && c>=0 && r<layout.rows && c<layout.cols, 'crossword bounds');
            if (cells.has(k)) assert(cells.get(k)===p.word[i], 'crossword collision');
            cells.set(k,p.word[i]);
            if (i) {
              const previous=(r-p.dr)+','+(c-p.dc);
              edges.add(previous+'|'+k);edges.add(k+'|'+previous);
            }
          }
        }
        for (const [key] of cells) {
          const [r,c]=key.split(',').map(Number);
          for (const neighbour of [(r+1)+','+c,r+','+(c+1)])
            if(cells.has(neighbour)) assert(edges.has(key+'|'+neighbour),'unintended adjacent words');
        }
        for (const p of layout.placements) {
          assert(!cells.has((p.row-p.dr)+','+(p.col-p.dc)), 'word starts against another');
          assert(!cells.has((p.row+p.dr*p.word.length)+','+(p.col+p.dc*p.word.length)), 'word ends against another');
        }
      }
      assert(P.crossword(['AB','CD','EF']).groups===3,'disconnected groups');
      assert(P.crossword(['FLAUTA','TROMPETA','TAMBOR','VIOLIN']).groups===1,'try alternative starting words');
      const pairs=JSON.parse(process.argv[2]);
      for (const [word,expected] of pairs) assert(P.normalize(word)===expected,'normalization mismatch');
      process.stdout.write('ok');
    """
    pairs = [(word, templates.puzzle_word(word)) for word in ['Música', 'cançó', 'Niño', 'l·l', 'l’aigua', 'pin-güí', 'New York']]
    done = subprocess.run(['node', '-e', script, str(templates.TEMPLATE_DIR / 'pasatiempos.js'), json.dumps(pairs)],
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    assert done.stdout == 'ok'


@pytest.mark.parametrize('template_id', PUZZLES)
def test_puzzle_ai_generates_only_vocabulary_and_scorm_packages_the_engine(client, template_id):
    headers, project_id = setup_user(client)
    base = f'/api/projects/{project_id}'
    assert client.post(f'{base}/template', headers=headers, json={
        'template': template_id, 'brief': {'language': 'en', 'title': 'Instruments'}}).status_code == 201
    data = templates.parse_data(templates.initial_files(template_id, {'language': 'en'})['datos.js'])
    data['words'] = [{'word': 'Flute', 'clue': 'A wind instrument.'}, {'word': 'Drum', 'clue': 'Hit it to make a sound.'}]
    captured = {}
    class Capture(StubGemini):
        async def generate(self, key, model, prompt):
            captured['prompt'] = prompt
            return await super().generate(key, model, prompt)
    def provider():
        return Capture(json.dumps({'summary': 'Vocabulary', 'changes': [
            {'path': 'datos.js', 'content': templates.data_js(data)}]}))
    app.dependency_overrides[get_gemini_provider] = provider
    response = client.post(f'{base}/ai/from-brief', headers=headers).json()
    assert response['status'] == 'applied', response
    assert 'No calcules posiciones' in captured['prompt']
    archive = zipfile.ZipFile(io.BytesIO(client.get(f'{base}/export.scorm.zip').content))
    assert 'EduScorm.complete' not in archive.read('index.html').decode()
    assert 'E.report(' in archive.read('script.js').decode()
    assert 'window.EDU' in archive.read('script.js').decode()
    data['words'][1]['word'] = 'Flúte'
    pending = client.post(f'{base}/ai/from-brief', headers=headers).json()
    assert pending['status'] == 'pending' and pending['grounding']['template_problems']


@pytest.mark.skipif(not (BROWSER and shutil.which('bwrap')), reason='chromium/bwrap not installed')
@pytest.mark.parametrize('language', ['es', 'va', 'en'])
def test_search_mouse_coordinates_keyboard_scoring_and_retry(language):
    files = templates.initial_files('sopa_letras', {'language': language})
    actions = r"""
      const E=window.EDU, P=E.puzzles;
      function assert(ok,msg) { if (!ok) throw Error(msg) }
      const grid=Array.from(document.querySelectorAll('tbody tr')).map(tr=>Array.from(tr.querySelectorAll('button')).map(b=>b.textContent));
      const button=(r,c)=>document.querySelector('button[data-row="'+r+'"][data-col="'+c+'"]');
      let report=[]; window.EduScorm={score:(n,total)=>report.push([n,total])};
      function locate(word) {
        for (let r=0;r<grid.length;r++) for(let c=0;c<grid.length;c++)
          for(const [dr,dc] of [[0,1],[1,0],[1,1],[-1,1],[0,-1],[-1,0],[-1,-1],[1,-1]]) {
            let actual=''; for(let i=0;i<word.length;i++) actual+=(grid[r+dr*i]||[])[c+dc*i]||'?';
            if(actual===word) return [r,c,r+dr*(word.length-1),c+dc*(word.length-1)];
          }
        throw Error('missing word');
      }
      const first=locate(P.normalize(E.D.words[0].word));
      button(first[0],first[1]).click();button(first[2],first[3]).click();
      const once=report.length;
      button(first[2],first[3]).click();button(first[0],first[1]).click();
      assert(report.length===once,'duplicate counts');
      const coordinates=document.querySelector('.coordenadas');
      for(const entry of E.D.words.slice(1)) {
        const points=locate(P.normalize(entry.word));
        coordinates.querySelectorAll('input').forEach((input,i)=>input.value=points[i]+1);
        coordinates.requestSubmit();
      }
      assert(report.at(-1)[0]===E.D.words.length,'score');
      assert(document.querySelectorAll('.encontrada').length>0,'highlight');
      document.querySelector('.acciones button:last-child').click();
      assert(!document.querySelector('.encontrada'),'reset');
      assert(document.activeElement===button(0,0),'reset focus');
      button(0,0).dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
      assert(document.activeElement===button(0,1),'arrow focus');
      assert(document.querySelectorAll('.sopa-tablero button[tabindex="0"]').length===1,'tab stops');
      document.querySelector('button.principal').click();assert(report.at(-1)[0]===0,'reset score');
      document.body.setAttribute('data-tested','ok');
    """
    dom = run_in_browser(inline(files).replace('</body>', f'<script>{actions}</script></body>'))
    assert 'data-tested="ok"' in dom


@pytest.mark.skipif(not (BROWSER and shutil.which('bwrap')), reason='chromium/bwrap not installed')
@pytest.mark.parametrize('language', ['es', 'va', 'en'])
def test_crossword_clues_normalized_answers_wrong_answers_and_retry(language):
    files = templates.initial_files('crucigrama', {'language': language})
    data = templates.parse_data(files['datos.js'])
    data['words'] = [{'word': 'Niño', 'clue': 'Persona de corta edad.'}, {'word': 'Cançó', 'clue': 'Música con palabras.'},
                     {'word': 'Música', 'clue': 'Arte del sonido.'}]
    files['datos.js'] = templates.data_js(data)
    actions = r"""
      function assert(ok,msg) { if (!ok) throw Error(msg) }
      let report=[];window.EduScorm={score:(n,total)=>report.push([n,total])};
      const inputs=Array.from(document.querySelectorAll('input[data-entry]'));
      assert(inputs.every(input=>input.labels.length && input.getAttribute('aria-describedby')),'labels');
      document.querySelector('button.principal').click();assert(report.at(-1)[0]===0,'empty');
      const answers=['  niño  ','CANÇO','musica'];
      inputs.forEach(input=>{input.value=answers[Number(input.dataset.entry)];input.dispatchEvent(new Event('input'))});
      document.querySelector('button.principal').click();assert(report.at(-1)[0]===3,'right');
      assert(Array.from(document.querySelectorAll('.letra')).some(cell=>cell.textContent==='Ñ'),'enye');
      const first=inputs[0];first.value='XXXX';first.dispatchEvent(new Event('input'));
      document.querySelector('button.principal').click();assert(report.at(-1)[0]===2,'wrong');
      assert(first.getAttribute('aria-invalid')==='true','invalid');
      document.querySelector('.acciones button:last-child').click();
      assert(inputs.every(input=>!input.value && !input.hasAttribute('aria-invalid')),'reset');
      assert(document.activeElement===inputs[0],'focus');
      assert(Array.from(document.querySelectorAll('.letra')).every(cell=>!cell.textContent),'reset grid');
      document.body.setAttribute('data-tested','ok');
    """
    dom = run_in_browser(inline(files).replace('</body>', f'<script>{actions}</script></body>'))
    assert 'data-tested="ok"' in dom
