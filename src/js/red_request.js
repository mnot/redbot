/* global alert */

import { qs, escapeHtml, config } from './red_util.js'

const knownReqHdrs = {
  'Accept-Language': ['', 'en', 'en-us', 'en-uk', 'fr'],
  'Cache-Control': ['', 'no-cache', 'only-if-cached'],
  Cookie: null,
  Referer: null,
  'User-Agent': [
    'RED/1 (https://redbot.org/about)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:74.0) Gecko/20100101 Firefox/74.0'
  ]
}

const redReqHdrs = [
  'accept-encoding',
  'if-modified-since',
  'if-none-match',
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
      if (newName in knownReqHdrs) {
        if (knownReqHdrs[newName] == null) {
          valHtml = "<input class='hdr_val' type='text'/>"
        } else {
          valHtml = "<select class='hdr_val'>"
          for (const val in knownReqHdrs[newName]) {
            valHtml += `<option>${knownReqHdrs[newName][val]}</option>`
          }
          valHtml += "<option value='other...'>other...</option></select>"
        }
      } else if (newName === 'other...') {
        content.outerHTML = "<input class='hdr_name' type='text'/>"
        installNameChangeHandler(reqHdr)
        valHtml = "<input class='hdr_val' type='text'/>"
      }
      setValue(reqHdr, valHtml)
    } else {
      newName = escapeHtml(content.value)
      if (redReqHdrs.indexOf(newName.toLowerCase()) > -1) {
        alert(`Setting the ${newName} request header can lead to unpredictable results.`)
      }
      hdrName.setAttribute('data-name', newName)
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
addLink.appendChild(document.createTextNode('add a request header'))
addButton.appendChild(addLink)
qs('#request_form').appendChild(addButton)

/* handle the add header button */
qs('#add_req_hdr').onclick = function () {
  addReqHdr()
}
