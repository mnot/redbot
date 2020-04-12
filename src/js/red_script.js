/* global XMLHttpRequest */

import { qs, qsa, docReady, toggleHidden } from './red_util.js'

window.onerror = function (message, url, line, col, errorObj) {
  if (window.XMLHttpRequest) {
    var xhr = new XMLHttpRequest()
    var data = `${message} at ${url}, ${line}:${col}`
    xhr.open('POST', '?client_error=1', true)
    xhr.send(data)
  }
}

docReady(function () {
  /* URI */

  qs('input').onkeydown = function (e) {
    if (e.key === 'Enter') {
      qs('#request_form').submit()
      e.preventDefault()
    }
  }

  /* help */

  qs('#help').onclick = function () {
    qsa('.help', toggleHidden)
  }

  qsa('.help', function (element) {
    element.onclick = function () {
      toggleHidden(element)
    }
  })
})
