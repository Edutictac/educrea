// Plantilla «Ordenar»: los pasos aparecen desordenados y se mueven con los botones Subir y Bajar.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, items = E.D.items || []
  var order = E.shuffle(items.map(function (_, i) { return i }))
  if (items.length > 1 && order.every(function (v, i) { return v === i })) order.reverse()
  var list = h('ol', { class: 'lista' })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function text(i) { return typeof items[i] === 'string' ? items[i] : items[i].text }
  function render(focus) {
    list.textContent = ''
    order.forEach(function (item, position) {
      var up = h('button', { type: 'button', text: '↑ ' + E.label('up', 'Subir'), 'aria-label': E.label('up', 'Subir') + ': ' + text(item), disabled: position === 0,
        onclick: function () { move(position, -1) } })
      var down = h('button', { type: 'button', text: '↓ ' + E.label('down', 'Bajar'), 'aria-label': E.label('down', 'Bajar') + ': ' + text(item), disabled: position === order.length - 1,
        onclick: function () { move(position, 1) } })
      list.append(h('li', { class: 'bloque' }, h('div', { class: 'fila' }, h('span', {}, E.image(items[item]), h('strong', { text: (position + 1) + '. ' + text(item) })),
        h('span', { class: 'acciones' }, up, down))))
      if (focus && focus.item === item) setTimeout(function () { (focus.up && !up.disabled ? up : down.disabled ? up : down).focus() })
    })
  }
  function move(position, delta) {
    var target = position + delta
    var item = order[position]
    order[position] = order[target]; order[target] = item
    result.textContent = ''
    render({ item: item, up: delta < 0 })
    E.say(text(item) + ': ' + E.label('position', 'posición') + ' ' + (target + 1))
  }
  function check() {
    var right = order.filter(function (item, position) { return item === position }).length
    result.className = 'resultado ' + (right === order.length ? 'bien' : 'mal')
    result.textContent = right === order.length ? E.label('allRight', '¡Todo en orden!') : E.score(right, order.length) + ' ' + E.label('inPlace', 'en su sitio.')
    E.say(result.textContent)
    E.report(right, order.length)
  }
  render()
  E.app.append(list, h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true)), result)
})()
