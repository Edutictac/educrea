// Word search: endpoints, roving keyboard focus, and equivalent coordinate controls.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, P = E.puzzles, entries = E.D.words || []
  var board = P.searchGrid(entries.map(function (entry) { return P.normalize(entry.word) }))
  var found = new Set(), colored = new Set(), start = null, active = [0, 0], buttons = [], marks = []
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function coordinate(r, c) { return E.label('row', 'Fila') + ' ' + (r + 1) + ', ' + E.label('column', 'Columna') + ' ' + (c + 1) }
  function update() {
    buttons.forEach(function (row, r) { row.forEach(function (button, c) {
      button.classList.toggle('encontrada', colored.has(P.key(r, c)))
      button.setAttribute('aria-pressed', start && start[0] === r && start[1] === c ? 'true' : 'false')
    }) })
  }
  function select(a, b) {
    var dr = b[0] - a[0], dc = b[1] - a[1], steps = Math.max(Math.abs(dr), Math.abs(dc)), selected = ''
    if ((!dr && !dc) || (dr && dc && Math.abs(dr) !== Math.abs(dc))) { E.say(E.label('notFound', 'No hay una palabra nueva.')); return }
    dr = Math.sign(dr); dc = Math.sign(dc)
    var cells = []
    for (var i = 0; i <= steps; i++) {
      var r = a[0] + dr * i, c = a[1] + dc * i
      selected += board.grid[r][c]; cells.push(P.key(r, c))
    }
    var index = entries.findIndex(function (entry, n) {
      var word = P.normalize(entry.word)
      return !found.has(n) && (word === selected || word === selected.split('').reverse().join(''))
    })
    if (index < 0) { E.say(E.label('notFound', 'No hay una palabra nueva.')); return }
    found.add(index); cells.forEach(function (k) { colored.add(k) })
    marks[index].textContent = E.label('correct', '¡Correcto!'); marks[index].className = 'bien'
    result.textContent = E.score(found.size, entries.length)
    E.say(E.label('foundWord', 'Palabra encontrada') + ': ' + entries[index].word + '. ' + result.textContent)
    E.report(found.size, entries.length)
  }
  function choose(r, c) {
    if (!start) { start = [r, c]; E.say(E.label('startSelected', 'Inicio seleccionado.')) }
    else { var first = start; start = null; select(first, [r, c]) }
    update()
  }
  function focus(r, c) {
    buttons[active[0]][active[1]].tabIndex = -1; active = [r, c]
    buttons[r][c].tabIndex = 0; buttons[r][c].focus()
  }
  var table = h('table', { class: 'sopa-tablero', 'aria-label': E.label('grid', 'Tablero') })
  var header = h('tr', {}, h('th', { scope: 'col', text: '' }))
  for (var col = 0; col < board.size; col++) header.append(h('th', { scope: 'col', text: col + 1 }))
  table.append(h('thead', {}, header))
  var body = h('tbody')
  board.grid.forEach(function (letters, r) {
    var tr = h('tr', {}, h('th', { scope: 'row', text: r + 1 })); buttons[r] = []
    letters.forEach(function (letter, c) {
      var button = h('button', { type: 'button', text: letter, tabindex: r === 0 && c === 0 ? 0 : -1,
        'data-row': r, 'data-col': c, 'aria-label': coordinate(r, c) + ': ' + letter, 'aria-pressed': 'false',
        onclick: function () { focus(r, c); choose(r, c) },
        onkeydown: function (event) {
          var moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }, d = moves[event.key]
          if (d) { event.preventDefault(); focus(Math.max(0, Math.min(board.size - 1, r + d[0])), Math.max(0, Math.min(board.size - 1, c + d[1]))) }
          if (event.key === 'Escape') { start = null; update(); E.say('') }
        } })
      buttons[r][c] = button; tr.append(h('td', {}, button))
    }); body.append(tr)
  }); table.append(body)
  var list = h('ul', { class: 'lista' })
  entries.forEach(function (entry) {
    var mark = h('span'); marks.push(mark)
    list.append(h('li', {}, h('strong', { text: entry.word }), h('span', { text: ' — ' + entry.clue + ' ' }), mark))
  })
  var coords = h('form', { class: 'coordenadas' }), fields = []
  ;['start', 'end'].forEach(function (kind) {
    var set = h('fieldset', {}, h('legend', { text: E.label(kind, kind) }))
    ;['row', 'column'].forEach(function (axis) {
      var input = h('input', { type: 'number', min: 1, max: board.size, step: 1, value: 1, required: true })
      fields.push(input); set.append(h('label', { text: E.label(axis, axis) }, input))
    }); coords.append(set)
  })
  coords.append(h('button', { type: 'submit', text: E.label('selectWord', 'Seleccionar palabra') }))
  coords.addEventListener('submit', function (event) {
    event.preventDefault()
    if (!coords.reportValidity()) return
    start = null; select([Number(fields[0].value) - 1, Number(fields[1].value) - 1], [Number(fields[2].value) - 1, Number(fields[3].value) - 1]); update()
  })
  function retry() {
    found.clear(); colored.clear(); start = null; coords.reset()
    marks.forEach(function (mark) { mark.textContent = ''; mark.className = '' })
    result.textContent = ''; E.say(''); update(); focus(0, 0)
  }
  function check() { result.textContent = E.score(found.size, entries.length); E.say(result.textContent); E.report(found.size, entries.length) }
  E.app.append(h('p', { text: E.label('searchHelp', '') }), h('p', { class: 'pista', text: E.label('puzzleHint', '') }),
    h('div', { class: 'tablero-scroll' }, table), coords,
    h('h2', { text: E.label('wordList', 'Palabras y pistas') }), list,
    h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
})();
