
import { qs, qsa, docReady, toggleHidden } from './red_util.js'

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
