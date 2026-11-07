// Escuchar y responder: recurso local, reproducción voluntaria y alternativa textual.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, D = E.D
  if (D.audio) {
    var error = h('p', { role: 'status' })
    var player = h('audio', { controls: true, preload: 'metadata', src: D.audio,
      'aria-label': E.label('listen', 'Escucha el audio'), onerror: function () {
        error.textContent = E.label('audioError', 'No se puede reproducir el audio.')
      } })
    E.app.append(h('section', { class: 'bloque', 'aria-label': E.label('listen', 'Escucha el audio') },
      h('h2', { text: E.label('listen', 'Escucha el audio') }), player, error,
      h('details', {}, h('summary', { text: E.label('transcript', 'Transcripción o descripción del audio') }),
        h('p', { class: 'transcripcion', text: D.transcript || '' }))))
  } else E.app.append(h('p', { role: 'status', text: E.label('audioMissing', 'Añade un audio al proyecto.') }))
})();

// Plantilla «Cuestionario»: preguntas de opción única con corrección y explicación.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, questions = E.D.questions || []
  var form = h('form', { novalidate: true })
  var marks = []
  questions.forEach(function (q, index) {
    var name = 'p' + index
    var set = h('fieldset', { class: 'bloque' }, h('legend', { text: (index + 1) + '. ' + q.text }), E.image(q))
    ;(q.options || []).forEach(function (option, value) {
      set.append(h('label', { class: 'opcion' }, h('input', { type: 'radio', name: name, value: value }), h('span', { text: option })))
    })
    var mark = h('p', { 'aria-live': 'polite' })
    marks.push(mark)
    set.append(mark)
    form.append(set)
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    questions.forEach(function (q, index) {
      var chosen = form.querySelector('input[name=p' + index + ']:checked')
      var ok = chosen && Number(chosen.value) === q.answer
      if (ok) right++
      marks[index].className = ok ? 'bien' : 'mal'
      marks[index].textContent = (ok ? E.label('correct', '¡Correcto!') : chosen ? E.label('incorrect', 'No es correcto.') : E.label('unanswered', 'Sin responder.'))
        + (q.feedback ? ' ' + q.feedback : '')
    })
    result.textContent = E.score(right, questions.length)
    E.say(result.textContent)
    E.report(right, questions.length)
  }
  function retry() {
    form.reset(); marks.forEach(function (m) { m.textContent = ''; m.className = '' }); result.textContent = ''
    var first = form.querySelector('input'); if (first) first.focus()
  }
  form.append(h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
  E.app.append(form)
})()
