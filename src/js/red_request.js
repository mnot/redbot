/* global alert */

import { qs, qsa, escapeHtml, config, docReady } from './red_util.js'

const knownReqHdrs = {
  'Accept-Language': ['', 'en', 'en-us', 'en-uk', 'fr'],
  Authorization: ['Basic', 'Bearer'],
  'Cache-Control': ['', 'no-cache', 'only-if-cached'],
  Cookie: null,
  Referer: null,
  'User-Agent': [
    'RED/1 (https://redbot.org/about)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:74.0) Gecko/20100101 Firefox/74.0'
  ]
}

const redReqHdrs = [
  'connection',
  'transfer-encoding',
  'content-length'
]

function addReqHdr (rawName, rawVal) {
  const setName = escapeHtml(rawName)
  const setVal = escapeHtml(rawVal)
  const reqHdrs = qs('#req_hdrs')
  const reqHdr = document.createElement('div')
  reqHdr.classList.add('req_hdr')
  reqHdr.innerHTML = `
<a href='#' class='delete_req_hdr'>x</a>
<span class='hdr_name' data-name='${setName || ''}'></span>: <span class='hdr_val'></span>
<input type='hidden' name='req_hdr' value='${setName || ''}:${setVal || ''}'/>`

  /* populate header name */
  let nameHtml
  if (setName == null || setName in knownReqHdrs) {
    nameHtml = "<select class='hdr_name'><option/>"
    for (const name in knownReqHdrs) {
      if (name === setName) {
        nameHtml += `<option selected='true'>${name}</option>`
      } else {
        nameHtml += `<option>${name}</option>`
      }
    }
    nameHtml += "<option value='other...'>other...</option> </select>"
  } else {
    nameHtml = `<input class="hdr_name" type="text" value="${setName}"/>`
  }
  qs('.hdr_name', reqHdr).innerHTML = nameHtml

  /* populate header value */
  if (setVal != null) {
    const knownHdrVals = knownReqHdrs[setName]
    if (knownHdrVals == null) {
      setValue(reqHdr, `<input class="hdr_val" type="text" value="${setVal}"/>`)
    } else if (knownHdrVals.indexOf(setVal) > -1) {
      let valHtml = "<select class='hdr_val'><option />"
      knownHdrVals.forEach(val => {
        if (setVal === val) {
          valHtml += `<option selected='true'>${val}</option>`
        } else {
          valHtml += `<option>${val}</option>`
        }
      })
      valHtml += "<option value='other...'>other...</option></select>"
      setValue(reqHdr, valHtml)
    } else {
      setValue(reqHdr, `<input class="hdr_val" type="text" value="${setVal}"/>`)
    }
  }

  installNameChangeHandler(reqHdr)
  reqHdrs.appendChild(reqHdr)

  /* handle delete */
  const deleteHdr = qs('.delete_req_hdr', reqHdr)
  deleteHdr.onclick = function () {
    reqHdrs.removeChild(reqHdr)
  }
}

function installNameChangeHandler (reqHdr) {
  const hdrName = qs('.hdr_name', reqHdr)
  const content = hdrName.firstElementChild
  if (!content) {
    console.log(`Missing content for ${hdrName}.`)
    return
  }
  content.onchange = function () {
    let newName
    if (content.tagName === 'SELECT') {
      newName = qs('option:checked', content).text
      hdrName.setAttribute('data-name', newName)
      let valHtml
      if (newName === 'Authorization') {
        // Default to Basic if just switching to Authorization
        valHtml = `
          <span class='auth_wrapper'>
            <select class='auth_type'>
              <option value='Basic'>Basic</option>
              <option value='Bearer'>Bearer</option>
              <option value='other...'>other...</option>
            </select>
            <span class='auth_params'>
              <span class='basic_auth'>
              <input type='text' class='basic_user' placeholder='User' /> :
              <input type='password' class='basic_password' placeholder='Password' />
              </span>
            </span>
          </span>`
      } else if (newName === 'other...') {
        content.outerHTML = "<input class='hdr_name' type='text'/>"
        installNameChangeHandler(reqHdr)
        valHtml = "<input class='hdr_val' type='text'/>"
      } else if (newName in knownReqHdrs) {
        if (knownReqHdrs[newName] == null) {
          valHtml = "<input class='hdr_val' type='text'/>"
        } else {
          valHtml = "<select class='hdr_val'>"
          for (const val in knownReqHdrs[newName]) {
            valHtml += `<option>${knownReqHdrs[newName][val]}</option>`
          }
          valHtml += "<option value='other...'>other...</option></select>"
        }
      }
      setValue(reqHdr, valHtml)
      if (newName === 'Authorization') {
        setupAuthHandler(reqHdr)
      }
    } else {
      newName = escapeHtml(content.value)
      if (redReqHdrs.indexOf(newName.toLowerCase()) > -1) {
        alert(config.i18n.header_warning.replace('%s', newName))
      }
      hdrName.setAttribute('data-name', newName)
    }
  }
}

function setupAuthHandler (reqHdr) {
  const authWrapper = qs('.auth_wrapper', reqHdr)
  if (!authWrapper) return

  // Override the default onchange from setValue with our bubbling handler
  authWrapper.onchange = function (e) {
    const target = e.target
    if (target.classList.contains('auth_type')) {
      // Type switched
      const type = target.value
      const params = qs('.auth_params', authWrapper)
      if (type === 'Basic') {
        params.innerHTML = `
          <span class='basic_auth'>
            <input type='text' class='basic_user' placeholder='User' /> :
            <input type='password' class='basic_password' placeholder='Password' />
          </span>`
      } else if (type === 'Bearer') {
        params.innerHTML = `
            <span class='bearer_auth'>
              <input type='text' class='bearer_token' placeholder='Token' />
            </span>`
      } else if (type === 'other...') {
        // Fallback to text input, removing the wrapper effectively
        setValue(reqHdr, "<input class='hdr_val' type='text'/>")
        return // End handler as wrapper is gone
      }
    }

    // Update hidden value
    updateAuthValue(reqHdr)
  }

  // Also listen for input events for smoother updates
  authWrapper.oninput = function (e) {
    updateAuthValue(reqHdr)
  }
}

function updateAuthValue (reqHdr) {
  const authWrapper = qs('.auth_wrapper', reqHdr)
  if (!authWrapper) return
  const type = qs('.auth_type', authWrapper).value
  const hiddenInput = qs('input[type=hidden]', reqHdr)

  if (type === 'Basic') {
    const userInput = qs('.basic_user', authWrapper)
    const passInput = qs('.basic_password', authWrapper)
    if (userInput && passInput) {
      const user = userInput.value || ''
      const pass = passInput.value || ''
      const creds = btoa(`${user}:${pass}`)
      hiddenInput.value = `Authorization:Basic ${creds}`
    }
  } else if (type === 'Bearer') {
    const tokenInput = qs('.bearer_token', authWrapper)
    if (tokenInput) {
      const token = tokenInput.value || ''
      hiddenInput.value = `Authorization:Bearer ${token}`
    }
  }
}

function setValue (reqHdr, valueHtml) {
  const hdrName = qs('.hdr_name', reqHdr)
  const hdrVal = qs('.hdr_val', reqHdr)
  hdrVal.innerHTML = valueHtml
  const content = hdrVal.firstElementChild
  content.onchange = function () {
    let newValue = ''
    if (content.tagName === 'SELECT') { // option list value
      if (qs('option:checked', hdrVal).value === 'other...') {
        setValue(reqHdr, "<input class='hdr_val' type='text'/>")
      } else {
        newValue = qs('option:checked', hdrVal).value
      }
    } else {
      newValue = qs('input', hdrVal).value
    }
    qs('input[type=hidden]', reqHdr).value = `${hdrName.getAttribute('data-name')}:${newValue}`
  }
}

// setup request headers. Depends on #request_form being available.

/* add pre-populated headers */
config.redbot_req_hdrs.forEach(hdr => {
  addReqHdr(hdr[0], hdr[1])
})

/* add the 'add a request header' button */
const addButton = document.createElement('div')
addButton.className = 'add_req_hdr'
const addLink = document.createElement('a')
addLink.href = '#'
addLink.id = 'add_req_hdr'
addLink.appendChild(document.createTextNode(config.i18n.add_req_hdr))
addButton.appendChild(addLink)
qs('#request_form').appendChild(addButton)

/* handle the add header button */
qs('#add_req_hdr').onclick = function () {
  addReqHdr()
}

/* handle 'copy cookies' button */
docReady(function () {
  const setCookieHdrs = []
  qsa("li.hdr[data-name='set-cookie']", function (element) {
    setCookieHdrs.push(element)
  })

  if (setCookieHdrs.length > 0) {
    const addButton = qs('.add_req_hdr')
    if (addButton) {
      const copyLink = document.createElement('a')
      copyLink.href = '#'
      copyLink.id = 'copy_cookies'
      copyLink.appendChild(document.createTextNode(config.i18n.copy_cookies))
      addButton.appendChild(copyLink)

      copyLink.onclick = function (e) {
        e.preventDefault()
        /* remove existing cookies */
        qsa('.req_hdr', function (element) {
          const hdrName = qs('.hdr_name', element).getAttribute('data-name')
          if (hdrName && hdrName.toLowerCase() === 'cookie') {
            qs('.delete_req_hdr', element).click() // trigger delete click
          }
        })
        setCookieHdrs.forEach(function (element) {
          const fullText = element.textContent
          const colonIndex = fullText.indexOf(':')
          if (colonIndex > -1) {
            const val = fullText.substring(colonIndex + 1).trim()
            const parts = val.split(';')
            if (parts.length > 0) {
              let cookiePair = parts[0].trim()
              const eqIndex = cookiePair.indexOf('=')
              if (eqIndex > -1) {
                const name = cookiePair.substring(0, eqIndex).trim()
                const value = cookiePair.substring(eqIndex + 1).trim()
                cookiePair = `${name}=${value}`
              } else {
                cookiePair = cookiePair.trim()
              }
              addReqHdr('Cookie', cookiePair)
            }
          }
        })
      }
    }
  }
})
