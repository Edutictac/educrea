// Completar huecos: banco de palabras o escritura libre, sin HTML generado.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, items = E.D.items || [], rows = []
  var bank = E.D.mode !== 'text'
  function normalize(value) { return value.normalize('NFC').trim().replace(/\s+/g, ' ').toLocaleLowerCase(E.D.language === 'va' ? 'ca' : 'es') }
  var words = E.shuffle(Array.from(new Set(items.map(function (item) { return item.answers[0] }))))
  if (bank) E.app.append(h('p', { class: 'banco' }, h('strong', { text: E.label('wordBank', 'Banco de palabras') + ': ' }), h('span', { text: words.join(' · ') })))
  var list = h('ol', { class: 'lista' })
  items.forEach(function (item, index) {
    var id = 'hueco-' + index, parts = item.text.split('___')
    var label = h('label', { for: id, id: id + '-frase', class: 'frase-hueco' },
      h('span', { text: (index + 1) + '. ' + parts[0] }),
      h('strong', { text: '[' + E.label('gap', 'Hueco') + ' ' + (index + 1) + ']' }),
      h('span', { text: parts[1] }))
    var control = bank ? h('select', { id: id }) : h('input', { id: id, type: 'text', maxlength: '120', autocomplete: 'off', spellcheck: 'false', class: 'respuesta-hueco' })
    if (bank) {
      control.append(h('option', { value: '', text: E.label('choose', 'Elige…') }))
      words.forEach(function (word) { control.append(h('option', { value: word, text: word })) })
    }
    var mark = h('p', { id: id + '-resultado', 'aria-live': 'polite' })
    control.setAttribute('aria-describedby', mark.id)
    rows.push({ control: control, mark: mark, item: item })
    list.append(h('li', { class: 'bloque' }, E.image(item), label, control, mark))
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    rows.forEach(function (row) {
      var value = normalize(row.control.value)
      var ok = value !== '' && row.item.answers.some(function (answer) { return normalize(answer) === value })
      if (ok) right++
      row.control.setAttribute('aria-invalid', ok ? 'false' : 'true')
      row.mark.className = ok ? 'bien' : 'mal'
      row.mark.textContent = (ok ? E.label('correct', '¡Correcto!') : value ? E.label('incorrect', 'No es correcto.') : E.label('unanswered', 'Sin responder.')) + (row.item.feedback ? ' ' + row.item.feedback : '')
    })
    result.textContent = E.score(right, rows.length)
    E.say(result.textContent)
    E.report(right, rows.length)
  }
  function retry() {
    rows.forEach(function (row) { row.control.value = ''; row.control.removeAttribute('aria-invalid'); row.mark.textContent = ''; row.mark.className = '' })
    result.textContent = ''; E.say('')
    if (rows[0]) rows[0].control.focus()
  }
  E.app.append(list, h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
})()
