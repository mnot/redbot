/* global hcaptcha */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'

docReady(function () {
  /* URI */

  qs('input').onkeydown = function (e) {
    if (e.key === 'Enter') {
      if (config.hcaptcha_sitekey) {
        qs('#hcaptcha_popup').style.display = 'block'
        var widgetId = hcaptcha.render('hcaptcha_popup', {
          size: 'compact',
          sitekey: config.hcaptcha_sitekey,
          callback: function (token) {
            const tokenElement = document.createElement('input')
            tokenElement.name = 'hCaptcha_token'
            tokenElement.value = token
            tokenElement.style.visibility = 'hidden'
            qs('#request_form').appendChild(tokenElement)
            qs('#request_form').submit()
          },
          'error-callback': function () { qs('hcaptcha_popup').style.display = 'none' }
        })
        hcaptcha.execute(widgetId)
      } else {
        qs('#request_form').submit()
      }
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
