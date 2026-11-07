// Plantilla «Tarjetas»: tarjetas que se giran (botón con aria-pressed) para repasar vocabulario o conceptos.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, cards = E.D.cards || []
  var grid = h('ul', { class: 'rejilla lista' })
  var seen = {}
  cards.forEach(function (card, index) {
    var front = h('span', {}, E.image(card), h('strong', { text: card.front }))
    var back = h('span', { text: card.back, hidden: true })
    var hint = h('span', { class: 'pista', text: E.label('flip', 'Pulsa para girar') })
    var button = h('button', { type: 'button', class: 'tarjeta', 'aria-pressed': 'false' }, front, back, hint)
    button.addEventListener('click', function () {
      var shown = button.getAttribute('aria-pressed') !== 'true'
      button.setAttribute('aria-pressed', String(shown))
      front.hidden = shown; back.hidden = !shown
      E.say(shown ? card.back : card.front)
      if (shown) { seen[index] = true; if (Object.keys(seen).length >= cards.length) E.complete() }
    })
    grid.append(h('li', {}, button))
  })
  E.app.append(grid)
})()
