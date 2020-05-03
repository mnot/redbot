/* global hcaptcha */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'

docReady(function () {
  qsa('form', function (form) {
    form.onsubmit = captchaLink
  })

  qs('#help').onclick = function () {
    qsa('.help', toggleHidden)
  }

  qsa('.help', function (element) {
    element.onclick = function () {
      toggleHidden(element)
    }
  })
})

function captchaLink (e) {
  var form = e.target.closest('form')
  if (config.hcaptcha_sitekey) {
    qs('#captcha_popup').style.display = 'block'
    var widgetId = hcaptcha.render('captcha_popup', {
      size: 'normal',
      sitekey: config.hcaptcha_sitekey,
      callback: function (token) {
        const tokenElement = document.createElement('input')
        tokenElement.type = 'hidden'
        tokenElement.name = 'captcha_token'
        tokenElement.value = token
        tokenElement.style.visibility = 'hidden'
        form.appendChild(tokenElement)
        submitForm(form)
      }
    })
    hcaptcha.execute(widgetId)
  } else {
    submitForm(form)
  }
  e.preventDefault()
}

function submitForm (form) {
  qs('#captcha_popup').style.display = 'none'
  var args = serializeForm(form)
  form.action = `?${args}`
  form.submit()
}

const secrets = ['captcha_token']

function serializeForm (form) {
  var q = []
  for (var i = form.elements.length - 1; i >= 0; i = i - 1) {
    var element = form.elements[i]
    if (element.nodeName === 'INPUT' && ['hidden', 'url'].includes(element.type)
    ) {
      if (!secrets.includes(element.name)) {
        q.unshift(`${element.name}=${encodeURIComponent(element.value)}`)
      }
    }
  }
  return q.join('&')
}
