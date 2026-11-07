// Plantilla «Clasificar»: cada elemento se asigna a un grupo con un desplegable.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, groups = E.D.groups || [], items = E.shuffle(E.D.items || [])
  var rows = []
  var list = h('ul', { class: 'lista' })
  items.forEach(function (item, index) {
    var id = 'c' + index
    var select = h('select', { id: id }, h('option', { value: '', text: E.label('choose', 'Elige…') }))
    groups.forEach(function (group, g) { select.append(h('option', { value: g, text: group })) })
    var mark = h('span', { 'aria-live': 'polite' })
    rows.push({ select: select, mark: mark, item: item })
    list.append(h('li', { class: 'bloque' }, h('div', { class: 'fila' }, h('label', { for: id }, E.image(item), h('strong', { text: item.text })), select), mark))
  })
  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    rows.forEach(function (row) {
      var ok = row.select.value !== '' && Number(row.select.value) === row.item.group
      if (ok) right++
      row.mark.className = ok ? 'bien' : 'mal'
      row.mark.textContent = ok ? E.label('correct', '¡Correcto!') : E.label('incorrect', 'No es correcto.')
    })
    result.textContent = E.score(right, rows.length)
    E.say(result.textContent)
    E.report(right, rows.length)
  }
  function retry() { rows.forEach(function (row) { row.select.value = ''; row.mark.textContent = '' }); result.textContent = ''; if (rows[0]) rows[0].select.focus() }
  E.app.append(h('p', { text: E.label('groups', 'Grupos') + ': ' + groups.join(' · ') }), list,
    h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true), E.button(E.label('retry', 'Volver a empezar'), retry)), result)
})()
