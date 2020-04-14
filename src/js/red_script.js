/* global hcaptcha */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'

docReady(function () {
  /* URI */

  qs('input').onkeydown = function (e) {
    function submitForm () {
      var form = qs('#request_form')
      var args = serializeForm(form)
      form.action = `?${args}`
      form.submit()
    }

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
            submitForm()
          },
          'error-callback': function () { qs('hcaptcha_popup').style.display = 'none' }
        })
        hcaptcha.execute(widgetId)
      } else {
        submitForm()
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

function serializeForm (form) {
  var q = []
  for (var i = form.elements.length - 1; i >= 0; i = i - 1) {
    var element = form.elements[i]
    if (element.nodeName === 'INPUT' && ['hidden', 'url'].includes(element.type)
    ) {
      q.unshift(`${element.name}=${encodeURIComponent(element.value)}`)
    }
  }
  return q.join('&')
}
