// Plantilla «Lectura por partes»: el texto se descubre sección a sección; cada parte puede tener «Saber más»
// (<details>) y una pregunta de comprensión con respuesta inmediata.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, sections = E.D.sections || []
  var shown = 0
  var container = h('div', {})
  var next = E.button(E.label('next', 'Continuar'), reveal, true)
  var progress = h('p', { class: 'pista', 'aria-live': 'polite' })
  function question(q, index) {
    var set = h('fieldset', { class: 'bloque' }, h('legend', { text: q.text }))
    var mark = h('p', { 'aria-live': 'polite' })
    ;(q.options || []).forEach(function (option, value) {
      var input = h('input', { type: 'radio', name: 'l' + index, value: value })
      input.addEventListener('change', function () {
        var ok = value === q.answer
        mark.className = ok ? 'bien' : 'mal'
        mark.textContent = (ok ? E.label('correct', '¡Correcto!') : E.label('incorrect', 'No es correcto.')) + (q.feedback ? ' ' + q.feedback : '')
      })
      set.append(h('label', { class: 'opcion' }, input, h('span', { text: option })))
    })
    set.append(mark)
    return set
  }
  function reveal() {
    var s = sections[shown]
    if (!s) return
    var heading = h('h2', { text: s.heading, tabindex: '-1' })
    var part = h('section', { class: 'bloque aparece' }, heading, E.image(s), h('p', { text: s.text }))
    if (s.more) part.append(h('details', {}, h('summary', { text: E.label('more', 'Saber más') }), h('p', { text: s.more })))
    if (s.question) part.append(question(s.question, shown))
    container.append(part)
    shown++
    progress.textContent = shown + ' / ' + sections.length
    if (shown >= sections.length) { next.disabled = true; next.textContent = E.label('done', '¡Has terminado!'); E.complete() }
    if (shown > 1) { heading.focus(); heading.scrollIntoView({ block: 'start' }) }
  }
  E.app.append(container, h('div', { class: 'acciones' }, next), progress)
  reveal()
})()
