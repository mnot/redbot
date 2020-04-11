/* global qs docReady alert escapeHtml */

var knownReqHdrs = {
  'Accept-Language': ['', 'en', 'en-us', 'en-uk', 'fr'],
  'Cache-Control': ['', 'no-cache', 'only-if-cached'],
  Cookie: null,
  Referer: null,
  'User-Agent': [
    'RED/1 (http://redbot.org/about)',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:74.0) Gecko/20100101 Firefox/74.0'
  ]
}

var redReqHdrs = [
  'accept-encoding',
  'if-modified-since',
  'if-none-match',
  'connection',
  'transfer-encoding',
  'content-length'
]

function addReqHdr (rawName, rawVal) {
  var setName = escapeHtml(rawName)
  var setVal = escapeHtml(rawVal)
  var reqHdrs = qs('#req_hdrs')
  var reqHdr = document.createElement('div')
  reqHdr.classList.add('req_hdr')
  reqHdr.innerHTML = `
<a href='#' class='delete_req_hdr'>x</a>
<span class='hdr_name' data-name='${setName || ''}'></span>: <span class='hdr_val'></span>
<input type='hidden' name='req_hdr' value='${setName || ''}:${setVal || ''}'/>`
  reqHdrs.appendChild(reqHdr)

  /* populate header name list */
  if (setName == null || setName in knownReqHdrs) {
    var nameHtml = "<select class='hdr_name'><option/>"
    for (var name in knownReqHdrs) {
      if (name === setName) {
        nameHtml += `<option selected='true'>${name}</option>`
      } else {
        nameHtml += `<option>${name}</option>`
      }
      nameHtml += "<option value='other...'>other...</option> </select>"
      qs('.hdr_name', reqHdr).innerHTML = nameHtml
    }

    /* select specified header, if any */
    if (setName != null) {
      var knownHdrVals = knownReqHdrs[setName]
      if (knownHdrVals == null) {
        setValue(reqHdr, `<input class="hdr_val" type="text" value="${setVal}"/>`)
      } else if (knownHdrVals.indexOf(setVal) > -1) {
        var valHtml = "<select class='hdr_val'><option />"
        knownHdrVals.forEach(val => {
          if (setVal === val) {
            valHtml += `<option selected='true'>${val}</option>`
          } else {
            valHtml += `<option>${val}</option>`
          }
        })
        valHtml += "<option value='other...'>other...</option></select>"
        setValue(reqHdr, valHtml)
      } else if (setVal != null) {
        setValue(reqHdr, `<input class="hdr_val" type="text" value="${setVal}"/>`)
      }
    }
  }

  installNameChangeHandler(reqHdr)

  /* handle delete */
  var deleteHdr = qs('.delete_req_hdr', reqHdr)
  deleteHdr.onclick = function () {
    reqHdrs.removeChild(reqHdr)
  }
}

function installNameChangeHandler (reqHdr) {
  var hdrName = qs('.hdr_name', reqHdr)
  var content = hdrName.firstElementChild
  if (!content) {
    console.log(`Missing content for ${hdrName}.`)
    return
  }
  content.onchange = function () {
    var newName
    if (content.tagName === 'SELECT') {
      newName = qs('option:checked', content).text
      hdrName.setAttribute('data-name', newName)
      var valHtml
      if (newName in knownReqHdrs) {
        if (knownReqHdrs[newName] == null) {
          valHtml = "<input class='hdr_val' type='text'/>"
        } else {
          valHtml = "<select class='hdr_val'>"
          for (var val in knownReqHdrs[newName]) {
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
  var hdrName = qs('.hdr_name', reqHdr)
  var hdrVal = qs('.hdr_val', reqHdr)
  hdrVal.innerHTML = valueHtml
  var content = hdrVal.firstElementChild
  content.onchange = function () {
    var newValue = ''
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

docReady(function () {
  var config = JSON.parse(qs('#config').innerHTML)

  /* add pre-populated headers */
  config.redbot_req_hdrs.forEach(hdr => {
    addReqHdr(hdr[0], hdr[1])
  })

  /* handle the add header button */
  qs('#add_req_hdr').onclick = function () {
    addReqHdr()
  }
})
