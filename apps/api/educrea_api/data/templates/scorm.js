// EduStudio: SCORM 1.2 bridge for Aules/Moodle. It finds the LMS API in a parent window, starts the attempt and
// reports the best score of the session (0-100) and the completion. Without an LMS it does nothing.
(function () {
  'use strict'
  function find(win) {
    for (var depth = 0; win && depth < 12; depth++) {
      try { if (win.API) return win.API } catch (e) { return null }
      if (!win.parent || win.parent === win) break
      win = win.parent
    }
    return null
  }
  var api = find(window) || (window.opener ? find(window.opener) : null)
  var started = false
  var finished = false
  var best = -1
  function set(key, value) { try { api.LMSSetValue(key, String(value)) } catch (e) { /* the LMS rejected the value */ } }
  function start() {
    if (!api || started) return started
    try { started = String(api.LMSInitialize('')) === 'true' } catch (e) { started = false }
    if (started) {
      var status = ''
      try { status = String(api.LMSGetValue('cmi.core.lesson_status') || '') } catch (e) { status = '' }
      if (!status || status === 'not attempted') set('cmi.core.lesson_status', 'incomplete')
      try { api.LMSCommit('') } catch (e) { /* ignore */ }
    }
    return started
  }
  function finish() {
    if (!started || finished) return
    finished = true
    try { api.LMSCommit(''); api.LMSFinish('') } catch (e) { /* ignore */ }
  }
  window.EduScorm = {
    available: function () { return !!api },
    score: function (right, total) {
      if (!start() || !total) return
      var percent = Math.round(100 * right / total)
      if (percent <= best) return
      best = percent
      set('cmi.core.score.min', 0)
      set('cmi.core.score.max', 100)
      set('cmi.core.score.raw', percent)
      set('cmi.core.lesson_status', 'completed')
      try { api.LMSCommit('') } catch (e) { /* ignore */ }
    },
    complete: function () {
      if (!start()) return
      set('cmi.core.lesson_status', 'completed')
      try { api.LMSCommit('') } catch (e) { /* ignore */ }
    },
  }
  start()
  window.addEventListener('pagehide', finish)
  window.addEventListener('beforeunload', finish)
})()
