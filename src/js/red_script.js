/* global hcaptcha */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'

docReady(function () {
  qsa('#request_form, form.link', function (form) {
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
  const form = e.target.closest('form')
  if (config.hcaptcha_sitekey && !document.cookie.split(';').some((item) =>
    item.trim().startsWith('human_hmac='))) {
    qs('#captcha_popup').style.display = 'block'
    const widgetId = hcaptcha.render('captcha_popup', {
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
  if (config.hcaptcha_sitekey) {
    qs('#captcha_popup').style.display = 'none'
  }
  const args = serializeForm(form)
  form.action = `?${args}`
  form.submit()
}

const secrets = ['captcha_token']

function serializeForm (form) {
  const q = []
  for (let i = form.elements.length - 1; i >= 0; i = i - 1) {
    const element = form.elements[i]
    if (element.nodeName === 'INPUT' && ['hidden', 'url'].includes(element.type)
    ) {
      if (!secrets.includes(element.name)) {
        q.unshift(`${element.name}=${encodeURIComponent(element.value)}`)
      }
    }
  }
  return q.join('&')
}
