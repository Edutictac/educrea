// EduStudio: utilidades comunes de las plantillas. Construye la página solo con textContent y nodos DOM, sin HTML en cadenas.
(function () {
  'use strict'
  var D = window.EDUCREA_DATA || {}
  var L = D.labels || {}
  function h(tag, attrs) {
    var el = document.createElement(tag)
    var options = attrs || {}
    Object.keys(options).forEach(function (key) {
      var value = options[key]
      if (value === undefined || value === null || value === false) return
      if (key === 'text') el.textContent = String(value)
      else if (key.indexOf('on') === 0) el.addEventListener(key.slice(2), value)
      else if (key === 'class') el.className = value
      else el.setAttribute(key, value === true ? '' : String(value))
    })
    for (var i = 2; i < arguments.length; i++) { if (arguments[i]) el.append(arguments[i]) }
    return el
  }
  function image(item) {
    if (!item || typeof item.image !== 'string' || !item.image) return null
    return h('img', { class: 'imagen', src: item.image, alt: item.alt || '' })
  }
  function say(text) { var status = document.getElementById('estado'); if (status) { status.textContent = ''; status.textContent = text } }
  function shuffle(list) {
    var copy = list.slice()
    for (var i = copy.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = copy[i]; copy[i] = copy[j]; copy[j] = t }
    return copy
  }
  function label(key, fallback) { return typeof L[key] === 'string' ? L[key] : fallback }
  function score(right, total) { return label('score', '{n} de {total}').replace('{n}', right).replace('{total}', total) }
  function button(text, onclick, primary) { return h('button', { type: 'button', class: primary ? 'principal' : '', text: text, onclick: onclick }) }
  document.documentElement.lang = D.language === 'va' ? 'ca-ES-valencia' : D.language === 'ca' ? 'ca' : D.language === 'en' ? 'en' : 'es'
  if (D.title) document.title = D.title
  var access = D.accessibility || {}
  document.body.classList.toggle('grande', access.large_text === true)
  document.body.classList.toggle('contraste', access.high_contrast === true)
  var app = document.getElementById('app')
  app.append(h('h1', { text: D.title || '' }))
  if (D.instructions) app.append(h('p', { class: 'consigna', text: D.instructions }))
  // Result for a learning platform (SCORM in Aules/Moodle). Outside one, window.EduScorm does not exist: no-op.
  function report(right, total) { if (window.EduScorm) window.EduScorm.score(right, total) }
  function complete() { if (window.EduScorm) window.EduScorm.complete() }
  window.EDU = { D: D, h: h, image: image, say: say, shuffle: shuffle, label: label, score: score, button: button, app: app,
    report: report, complete: complete }
})()
