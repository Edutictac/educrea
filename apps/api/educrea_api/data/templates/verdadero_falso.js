// Verdadero o falso: afirmaciones con explicación, controles nativos y puntuación SCORM.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, statements = E.D.statements || [], rows = []
  var form = h('form', { novalidate: true })
  statements.forEach(function (item, index) {
    var name = 'vf' + index
    var mark = h('p', { id: name + '-resultado', 'aria-live': 'polite' })
    var set = h('fieldset', { class: 'bloque', 'aria-describedby': mark.id },
      h('legend', { text: (index + 1) + '. ' + item.text }), E.image(item))
    ;[true, false].forEach(function (value) {
      set.append(h('label', { class: 'opcion' },
        h('input', { type: 'radio', name: name, value: String(value), 'aria-describedby': mark.id }),
        h('span', { text: E.label(String(value), value ? 'Verdadero' : 'Falso') })))
    })
    set.append(mark); form.append(set)
    rows.push({ item: item, name: name, mark: mark, set: set })
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    rows.forEach(function (row) {
      var chosen = form.querySelector('input[name=' + row.name + ']:checked')
      var ok = !!chosen && chosen.value === String(row.item.answer)
      if (ok) right++
      row.set.setAttribute('aria-invalid', ok ? 'false' : 'true')
      row.mark.className = ok ? 'bien' : 'mal'
      row.mark.textContent = (ok ? E.label('correct', '¡Correcto!') : chosen ? E.label('incorrect', 'No es correcto.') : E.label('unanswered', 'Sin responder.'))
        + ' ' + row.item.feedback
    })
    result.textContent = E.score(right, rows.length)
    E.say(result.textContent); E.report(right, rows.length)
  }
  function retry() {
    form.reset()
    rows.forEach(function (row) { row.mark.textContent = ''; row.mark.className = ''; row.set.removeAttribute('aria-invalid') })
    result.textContent = ''; E.say('')
    var first = form.querySelector('input'); if (first) first.focus()
  }
  form.append(h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true),
    E.button(E.label('retry', 'Volver a empezar'), retry)), result)
  E.app.append(form)
})()
