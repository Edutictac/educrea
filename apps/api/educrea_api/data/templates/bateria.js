// Batería de ejercicios: varios bloques cortos con una única corrección y nota SCORM.
(function () {
  'use strict'
  var E = window.EDU, h = E.h, blocks = E.D.blocks || [], rows = []
  var form = h('form', { novalidate: true })

  function normalize(value) {
    return value.normalize('NFC').trim().replace(/\s+/g, ' ').toLocaleLowerCase(E.D.language === 'va' ? 'ca-ES-valencia' : E.D.language === 'ca' ? 'ca' : E.D.language === 'en' ? 'en' : 'es')
  }
  function heading(block, key, fallback) { return block.heading || E.label(key, fallback) }

  blocks.forEach(function (block, b) {
    if (!block || ['choice', 'true_false', 'gap'].indexOf(block.type) < 0) return
    if (block.type === 'choice') {
      form.append(h('h2', { class: 'bloque-titulo', text: heading(block, 'blockChoice', 'Elige la respuesta') }))
      ;(block.questions || []).forEach(function (q, i) {
        var name = 'b' + b + '-c' + i
        var mark = h('p', { id: name + '-resultado', 'aria-live': 'polite' })
        var set = h('fieldset', { class: 'bloque', 'aria-describedby': mark.id },
          h('legend', { text: (i + 1) + '. ' + q.text }), E.image(q))
        ;(q.options || []).forEach(function (option, value) {
          set.append(h('label', { class: 'opcion' },
            h('input', { type: 'radio', name: name, value: String(value), 'aria-describedby': mark.id }),
            h('span', { text: option })))
        })
        set.append(mark); form.append(set)
        rows.push({ kind: 'choice', name: name, mark: mark, set: set, item: q, answer: q.answer })
      })
    } else if (block.type === 'true_false') {
      form.append(h('h2', { class: 'bloque-titulo', text: heading(block, 'blockTrueFalse', 'Verdadero o falso') }))
      ;(block.statements || []).forEach(function (item, i) {
        var name = 'b' + b + '-v' + i
        var mark = h('p', { id: name + '-resultado', 'aria-live': 'polite' })
        var set = h('fieldset', { class: 'bloque', 'aria-describedby': mark.id },
          h('legend', { text: (i + 1) + '. ' + item.text }), E.image(item))
        ;[true, false].forEach(function (value) {
          set.append(h('label', { class: 'opcion' },
            h('input', { type: 'radio', name: name, value: String(value), 'aria-describedby': mark.id }),
            h('span', { text: E.label(String(value), value ? 'Verdadero' : 'Falso') })))
        })
        set.append(mark); form.append(set)
        rows.push({ kind: 'true_false', name: name, mark: mark, set: set, item: item, answer: item.answer })
      })
    } else {
      form.append(h('h2', { class: 'bloque-titulo', text: heading(block, 'blockGap', 'Completa la frase') }))
      var bank = block.mode !== 'text'
      if (bank) {
        var words = E.shuffle(Array.from(new Set((block.items || []).map(function (item) { return item.answers[0] }))))
        form.append(h('p', { class: 'banco' }, h('strong', { text: E.label('wordBank', 'Banco de palabras') + ': ' }),
          h('span', { text: words.join(' · ') })))
      }
      var list = h('ol', { class: 'lista' })
      ;(block.items || []).forEach(function (item, i) {
        var id = 'hueco-' + b + '-' + i, parts = item.text.split('___')
        var label = h('label', { for: id, id: id + '-frase', class: 'frase-hueco' },
          h('span', { text: (i + 1) + '. ' + parts[0] }),
          h('strong', { text: '[' + E.label('gap', 'Hueco') + ' ' + (i + 1) + ']' }),
          h('span', { text: parts[1] }))
        var control = bank ? h('select', { id: id })
          : h('input', { id: id, type: 'text', maxlength: '120', autocomplete: 'off', spellcheck: 'false', class: 'respuesta-hueco' })
        if (bank) {
          control.append(h('option', { value: '', text: E.label('choose', 'Elige…') }))
          words.forEach(function (word) { control.append(h('option', { value: word, text: word })) })
        }
        var mark = h('p', { id: id + '-resultado', 'aria-live': 'polite' })
        control.setAttribute('aria-describedby', mark.id)
        rows.push({ kind: 'gap', control: control, mark: mark, item: item, answers: item.answers || [] })
        list.append(h('li', { class: 'bloque' }, E.image(item), label, control, mark))
      })
      form.append(list)
    }
  })

  var result = h('p', { class: 'resultado', 'aria-live': 'polite' })
  function check() {
    var right = 0
    rows.forEach(function (row) {
      var answered = false, ok = false
      if (row.kind === 'gap') {
        var value = normalize(row.control.value)
        answered = value !== ''
        ok = answered && row.answers.some(function (answer) { return normalize(answer) === value })
        row.control.setAttribute('aria-invalid', ok ? 'false' : 'true')
      } else {
        var chosen = form.querySelector('input[name="' + row.name + '"]:checked')
        answered = !!chosen
        ok = answered && (row.kind === 'choice' ? Number(chosen.value) === row.answer : chosen.value === String(row.answer))
        row.set.setAttribute('aria-invalid', ok ? 'false' : 'true')
      }
      if (ok) right++
      row.mark.className = ok ? 'bien' : 'mal'
      row.mark.textContent = (ok ? E.label('correct', '¡Correcto!') : answered ? E.label('incorrect', 'No es correcto.') : E.label('unanswered', 'Sin responder.'))
        + (row.item.feedback ? ' ' + row.item.feedback : '')
    })
    result.textContent = E.score(right, rows.length)
    E.say(result.textContent)
    E.report(right, rows.length)
  }
  function retry() {
    form.reset()
    rows.forEach(function (row) {
      row.mark.textContent = ''; row.mark.className = ''; row.set && row.set.removeAttribute('aria-invalid')
      if (row.control) row.control.removeAttribute('aria-invalid')
    })
    result.textContent = ''; E.say('')
    var first = form.querySelector('input, select'); if (first) first.focus()
  }
  form.append(h('div', { class: 'acciones' }, E.button(E.label('check', 'Comprobar'), check, true),
    E.button(E.label('retry', 'Volver a empezar'), retry)), result)
  E.app.append(form)
})()
