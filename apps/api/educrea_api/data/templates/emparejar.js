// Plantilla «Emparejar»: cada elemento de la izquierda se relaciona con uno de la derecha mediante un desplegable
// (accesible con teclado y lector de pantalla; sin arrastrar). Varias parejas pueden compartir la misma respuesta
// (por ejemplo, instrumentos de la misma familia): las opciones no se repiten y se corrige por el texto elegido.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, pairs = E.D.pairs || []
  var options = E.shuffle(pairs.map(function (p) { return p.right }).filter(function (text, i, all) { return all.indexOf(text) === i }))
  var rows = []
  var list = h('ol', { class: 'lista' })
  pairs.forEach(function (pair, index) {
    var id = 'e' + index
    var select = h('select', { id: id }, h('option', { value: '', text: E.label('choose', 'Elige…') }))
    options.forEach(function (text) { select.append(h('option', { value: text, text: text })) })
    var mark = h('span', { 'aria-live': 'polite' })
    rows.push({ select: select, mark: mark, answer: pair.right })
    list.append(h('li', { class: 'bloque' }, h('div', { class: 'fila' },
      h('label', { for: id }, E.image(pair), h('strong', { text: pair.left })), select), mark))
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    rows.forEach(function (row) {
      var ok = row.select.value !== '' && row.select.value === row.answer
      if (ok) right++
      row.mark.className = ok ? 'bien' : 'mal'
      row.mark.textContent = ok ? E.label('correct', '¡Correcto!') : E.label('incorrect', 'No es correcto.')
    })
    result.textContent = E.score(right, rows.length)
    E.say(result.textContent)
    E.report(right, rows.length)
  }
  function retry() { rows.forEach(function (row) { row.select.value = ''; row.mark.textContent = '' }); result.textContent = ''; if (rows[0]) rows[0].select.focus() }
  E.app.append(list, h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
})()
