// Accessible crossword: answer fields next to clues, synchronised with a numbered visual grid.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, P = E.puzzles, entries = E.D.words || []
  var layout = P.crossword(entries.map(function (entry) { return P.normalize(entry.word) }))
  var inputs = [], marks = [], cells = {}, solutions = {}, numbers = {}
  layout.placements.forEach(function (p) {
    numbers[P.key(p.row, p.col)] = p.number
    for (var i = 0; i < p.word.length; i++) solutions[P.key(p.row + p.dr * i, p.col + p.dc * i)] = p.word[i]
  })
  var table = h('table', { class: 'crucigrama-tablero', 'aria-hidden': 'true' })
  for (var r = 0; r < layout.rows; r++) {
    var tr = h('tr')
    for (var c = 0; c < layout.cols; c++) {
      var k = P.key(r, c), td = h('td', { class: solutions[k] ? 'casilla' : 'negra' })
      if (solutions[k]) {
        var letter = h('span', { class: 'letra' }); cells[k] = { td: td, letter: letter }
        if (numbers[k]) td.append(h('small', { text: numbers[k] }))
        td.append(letter)
      }
      tr.append(td)
    }
    table.append(tr)
  }
  function update() {
    var values = {}
    layout.placements.forEach(function (p) {
      var answer = P.normalize(inputs[p.index].value)
      for (var i = 0; i < p.word.length; i++) {
        if (!answer[i]) continue
        var k = P.key(p.row + p.dr * i, p.col + p.dc * i)
        if (!values[k]) values[k] = new Set()
        values[k].add(answer[i])
      }
    })
    Object.keys(cells).forEach(function (k) {
      var letters = values[k], conflict = letters && letters.size > 1
      cells[k].letter.textContent = letters ? conflict ? '?' : Array.from(letters)[0] : ''
      cells[k].td.classList.toggle('conflicto', !!conflict)
    })
  }
  var list = h('ol', { class: 'lista pistas-crucigrama' })
  layout.placements.forEach(function (p) {
    var id = 'respuesta-' + p.index, mark = h('p', { id: id + '-resultado', 'aria-live': 'polite' })
    var detail = p.number + '. ' + E.label(p.dr ? 'downWord' : 'across', '') + '. ' + entries[p.index].clue
      + ' (' + p.word.length + ' ' + E.label('letters', 'letras') + ').'
    var input = h('input', { id: id, type: 'text', maxlength: 60, autocomplete: 'off', spellcheck: 'false',
      class: 'respuesta-hueco', 'aria-describedby': mark.id, 'data-entry': p.index,
      oninput: function () { mark.textContent = ''; input.removeAttribute('aria-invalid'); result.textContent = ''; update() } })
    inputs[p.index] = input; marks[p.index] = mark
    list.append(h('li', { class: 'bloque' }, h('label', { for: id, text: detail }), input, mark))
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    entries.forEach(function (entry, index) {
      var answer = P.normalize(inputs[index].value), ok = answer === P.normalize(entry.word)
      if (ok) right++
      inputs[index].setAttribute('aria-invalid', ok ? 'false' : 'true')
      marks[index].textContent = ok ? E.label('correct', '¡Correcto!') : answer ? E.label('incorrect', 'No es correcto.') : E.label('unanswered', 'Sin responder.')
      marks[index].className = ok ? 'bien' : 'mal'
    })
    result.textContent = E.score(right, entries.length); E.say(result.textContent); E.report(right, entries.length)
  }
  function retry() {
    inputs.forEach(function (input, index) { input.value = ''; input.removeAttribute('aria-invalid'); marks[index].textContent = ''; marks[index].className = '' })
    result.textContent = ''; E.say(''); update()
    list.querySelector('input').focus()
  }
  E.app.append(h('p', { text: E.label('crossHelp', '') }), h('p', { class: 'pista', text: E.label('puzzleHint', '') }))
  if (layout.groups > 1) E.app.append(h('p', { class: 'pista', text: E.label('separateGroups', '') }))
  E.app.append(h('div', { class: 'tablero-scroll' }, table), list,
    h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
})();
