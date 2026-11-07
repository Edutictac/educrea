// Pure layout helpers shared by the two fixed puzzle engines. No model-supplied coordinates.
(function () {
  'use strict'
  var E = window.EDU
  function normalize(value) {
    return value.toUpperCase().normalize('NFC').replace(/Ñ/g, '\u0000').replace(/Ç/g, '\u0001')
      .normalize('NFD').replace(/\p{M}/gu, '').replace(/[\s’'·.\-]/g, '')
      .replace(/\u0000/g, 'Ñ').replace(/\u0001/g, 'Ç')
  }
  function key(r, c) { return r + ',' + c }
  function searchGrid(words) {
    var size = Math.max(10, words.length, Math.max.apply(null, words.map(function (w) { return w.length }))) + 2
    var grid, placed
    var directions = [[0, 1], [1, 0], [1, 1], [-1, 1], [0, -1], [-1, 0], [-1, -1], [1, -1]]
    function empty() { grid = Array.from({ length: size }, function () { return Array(size).fill('') }); placed = [] }
    function put(word, r, c, dr, dc) {
      for (var i = 0; i < word.length; i++) grid[r + dr * i][c + dc * i] = word[i]
      placed.push({ word: word, row: r, col: c, dr: dr, dc: dc })
    }
    empty()
    var complete = words.slice().sort(function (a, b) { return b.length - a.length }).every(function (word) {
      var candidates = []
      directions.forEach(function (d) {
        for (var r = 0; r < size; r++) for (var c = 0; c < size; c++) {
          var endR = r + d[0] * (word.length - 1), endC = c + d[1] * (word.length - 1)
          if (endR < 0 || endR >= size || endC < 0 || endC >= size) continue
          var fits = true
          for (var i = 0; i < word.length; i++) {
            var cell = grid[r + d[0] * i][c + d[1] * i]
            if (cell && cell !== word[i]) { fits = false; break }
          }
          if (fits) candidates.push([r, c, d[0], d[1]])
        }
      })
      if (!candidates.length) return false
      var chosen = candidates[Math.floor(Math.random() * candidates.length)]
      put(word, chosen[0], chosen[1], chosen[2], chosen[3]); return true
    })
    // Guaranteed fallback: each word has its own row, including under adversarial random choices.
    if (!complete) {
      empty()
      E.shuffle(words).forEach(function (word, row) { put(word, row, Math.floor(Math.random() * (size - word.length + 1)), 0, 1) })
    }
    var alphabet = 'ABCDEFGHIJKLMNÑOPQRSTUVWXYZ'
    grid.forEach(function (row) { row.forEach(function (cell, c) { if (!cell) row[c] = alphabet[Math.floor(Math.random() * alphabet.length)] }) })
    return { grid: grid, placements: placed, size: size }
  }
  function crosswordAttempt(words, firstIndex) {
    var cells = {}, placed = [], pending = words.map(function (word, index) { return { word: word, index: index } })
      .sort(function (a, b) { return b.word.length - a.word.length || a.index - b.index })
    function at(r, c) { return cells[key(r, c)] }
    function bounds(extra) {
      var all = placed.concat(extra ? [extra] : [])
      return { top: Math.min.apply(null, all.map(function (p) { return p.row })),
        left: Math.min.apply(null, all.map(function (p) { return p.col })),
        bottom: Math.max.apply(null, all.map(function (p) { return p.row + p.dr * (p.word.length - 1) })),
        right: Math.max.apply(null, all.map(function (p) { return p.col + p.dc * (p.word.length - 1) })) }
    }
    function put(p) {
      for (var i = 0; i < p.word.length; i++) {
        var k = key(p.row + p.dr * i, p.col + p.dc * i), old = cells[k]
        cells[k] = { letter: p.word[i], axes: (old ? old.axes : 0) | (p.dr ? 2 : 1) }
      }
      placed.push(p)
    }
    function fits(p) {
      if (at(p.row - p.dr, p.col - p.dc) || at(p.row + p.dr * p.word.length, p.col + p.dc * p.word.length)) return false
      var crosses = 0, axis = p.dr ? 2 : 1
      for (var i = 0; i < p.word.length; i++) {
        var r = p.row + p.dr * i, c = p.col + p.dc * i, old = at(r, c)
        if (old) {
          if (old.letter !== p.word[i] || (old.axes & axis)) return false
          crosses++
        } else if (at(r + p.dc, c + p.dr) || at(r - p.dc, c - p.dr)) return false
      }
      return crosses > 0
    }
    function best(item) {
      var result = null, area = Infinity
      Object.keys(cells).forEach(function (k) {
        var location = k.split(',').map(Number), cell = cells[k]
        for (var i = 0; i < item.word.length; i++) {
          if (item.word[i] !== cell.letter) continue
          ;[[0, 1], [1, 0]].forEach(function (d) {
            var p = { word: item.word, index: item.index, row: location[0] - d[0] * i,
              col: location[1] - d[1] * i, dr: d[0], dc: d[1] }
            if (!fits(p)) return
            var b = bounds(p), cost = (b.bottom - b.top + 1) * (b.right - b.left + 1)
            if (cost < area) { result = p; area = cost }
          })
        }
      })
      return result
    }
    var first = pending.splice(firstIndex, 1)[0]
    put({ word: first.word, index: first.index, row: 0, col: 0, dr: 0, dc: 1 })
    while (pending.length) {
      var progress = false
      for (var j = 0; j < pending.length; j++) {
        var candidate = best(pending[j])
        if (candidate) { put(candidate); pending.splice(j, 1); progress = true; break }
      }
      if (!progress) {
        // Never drop vocabulary that cannot cross: keep it in a clearly announced separate group.
        var next = pending.shift(), bottom = bounds().bottom
        put({ word: next.word, index: next.index, row: bottom + 2, col: 0, dr: 0, dc: 1 })
      }
    }
    var b = bounds(), normalized = placed.map(function (p) {
      return { word: p.word, index: p.index, row: p.row - b.top, col: p.col - b.left, dr: p.dr, dc: p.dc }
    }).sort(function (a, z) { return a.row - z.row || a.col - z.col || a.index - z.index })
    var starts = {}, number = 0
    normalized.forEach(function (p) { var k = key(p.row, p.col); if (!starts[k]) starts[k] = ++number; p.number = starts[k] })
    var parents = words.map(function (_, i) { return i }), owners = {}
    function root(i) { while (parents[i] !== i) i = parents[i]; return i }
    normalized.forEach(function (p) {
      for (var i = 0; i < p.word.length; i++) {
        var k = key(p.row + p.dr * i, p.col + p.dc * i)
        if (owners[k] !== undefined) parents[root(p.index)] = root(owners[k])
        owners[k] = p.index
      }
    })
    return { placements: normalized, rows: b.bottom - b.top + 1, cols: b.right - b.left + 1,
      groups: new Set(words.map(function (_, i) { return root(i) })).size }
  }
  function crossword(words) {
    var best = null
    // Try each starting word before accepting separated groups; prefer fewer groups, then a compact board.
    for (var first = 0; first < words.length; first++) {
      var candidate = crosswordAttempt(words, first)
      if (!best || candidate.groups < best.groups || (candidate.groups === best.groups && candidate.rows * candidate.cols < best.rows * best.cols)) best = candidate
    }
    return best
  }
  E.puzzles = { normalize: normalize, key: key, searchGrid: searchGrid, crossword: crossword }
})();
