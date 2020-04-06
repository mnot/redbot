
/* request headers */

/* global jQuery, $, config, alert */

var knownReqHdrs = {
  'Accept-Language': ['', 'en', 'en-us', 'en-uk', 'fr'],
  'Cache-Control': ['', 'no-cache', 'only-if-cached'],
  Cookie: null,
  Referer: null,
  'User-Agent': [
    'RED/' + config.redbot_version + ' (http://redbot.org/about)',
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; Win64; x64; Trident/4.0)',
    'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; )',
    'Mozilla/5.0 (X11; U; Linux x86_64; en-US) Gecko Firefox/3.0.8',
    'Opera/9.80 (Windows NT 5.1; U; cs) Presto/2.2.15 Version/10.00'
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

function addReqHdr (hdrName, hdrVal) {
  var hdrShell = "<div class='req_hdr'>"
  hdrShell += "<a href='#' class='delete_req_hdr'>x</a> "
  hdrShell += "<span class='hdr_name'></span>"
  hdrShell += ": <span class='hdr_val'></span>"
  hdrShell += "<input type='hidden' name='req_hdr' value=''/>"
  hdrShell += '</div>'
  $('#req_hdrs').append(hdrShell)
  var reqHdr = $('#req_hdrs > .req_hdr:last')

  /* populate header name list */
  if (hdrName == null || hdrName in knownReqHdrs) {
    var nameHtml = "<select class='hdr_name'><option/>"
    for (var name in knownReqHdrs) {
      if (name === hdrName) {
        nameHtml += "<option selected='true'>" + name + '</option>'
      } else {
        nameHtml += '<option>' + name + '</option>'
      }
    }
    nameHtml += "<option value='other...'>other...</option>"
    nameHtml += '</select>'
    $('.hdr_name', reqHdr).replaceWith(nameHtml)

    /* select specified header, if any */
    if (hdrName != null) {
      var knownHdrVals = knownReqHdrs[hdrName]
      if (knownHdrVals == null) {
        $('.hdr_val', reqHdr)
          .replaceWith('<input class="hdrVal" type="text"/>')
        $('.hdr_val', reqHdr).val(hdrVal)
      } else if (jQuery.inArray(hdrVal, knownHdrVals) > -1) {
        var valHtml = "<select class='hdr_val'>"
        valHtml += '<option />'
        for (var i in knownHdrVals) {
          var val = knownHdrVals[i]
          if (hdrVal === val) {
            valHtml += "<option selected='true'>" + val + '</option>'
          } else {
            valHtml += '<option>' + val + '</option>'
          }
        }
        valHtml += "<option value='other...'>other...</option>"
        valHtml += '</select>'
        $('.hdr_val', reqHdr).replaceWith(valHtml)
      } else if (hdrVal != null) {
        $('.hdr_val', reqHdr)
          .replaceWith('<input class="hdrVal" type="text"/>')
        $('.hdr_val', reqHdr).val(hdrVal)
      }
      $('input[type=hidden]', reqHdr).val(hdrName + ':' + hdrVal)
    }
  } else {
    $('.hdr_name', reqHdr)
      .replaceWith('<input class="hdr_name" type="text"/>')
    $('.hdr_name', reqHdr).val(hdrName)
    $('.hdr_val', reqHdr)
      .replaceWith('<input class="hdr_val" type="text"/>')
    $('.hdr_val', reqHdr).val(hdrVal)
    $('input[type=hidden]', reqHdr).val(hdrName + ':' + hdrVal)
  }
}

$(document).ready(function () {
  /* add pre-populated headers */
  for (var i in config.redbot_reqHdrs) {
    var hdr = config.redbot_reqHdrs[i]
    addReqHdr(hdr[0], hdr[1])
  }

  /* handle the add header button */
  $('#add_req_hdr').click(function () {
    addReqHdr()
    return false
  })

  /* handle the delete header button */
  $('#req_hdrs').on('click', '.delete_req_hdr', function (ev) {
    var reqHdr = $(ev.target).closest('.req_hdr')
    reqHdr.remove()
    return false
  })

  /* handle header name list changes */
  $('#req_hdrs').on('change', 'select.hdr_name', function (ev) {
    var reqHdr = $(ev.target).closest('.req_hdr')
    var hdrName = $('.hdr_name > option:selected', reqHdr).val()
    if (hdrName in knownReqHdrs) {
      var hdrVal
      if (knownReqHdrs[hdrName] == null) {
        hdrVal = "<input class='hdr_val' type='text'/>"
        $('.hdr_val', reqHdr).replaceWith(hdrVal)
      } else {
        hdrVal = "<select class='hdr_val'>"
        for (var val in knownReqHdrs[hdrName]) {
          hdrVal += '<option>' + knownReqHdrs[hdrName][val] + '</option>'
        }
        hdrVal += "<option value='other...'>other...</option>"
        hdrVal += '</select>'
        $('.hdr_val', reqHdr).replaceWith(hdrVal)
      }
    } else if (hdrName === 'other...') {
      $('.hdr_name', reqHdr)
        .replaceWith("<input class='hdr_name' type='text'/>")
      $('.hdr_val', reqHdr)
        .replaceWith("<input class='hdr_val' type='text'/>")
    }
  })

  /* handle header name text changes */
  $('#req_hdrs').on('change', 'input.hdr_name', function (ev) {
    /* alert on dangerous changes */
    var reqHdr = $(ev.target).closest('.req_hdr')
    var hdrName = $('.hdr_name', reqHdr).val()
    if (jQuery.inArray(hdrName.toLowerCase(), redReqHdrs) > -1) {
      alert('The ' + hdrName + ' request header is used by RED in its tests. Setting it yourself can lead to unpredictable results.')
    }
    $('input[type=hidden]', reqHdr).val(hdrName + ':' + '')
  })

  /* handle header value list changes */
  $('#req_hdrs').on('change', 'select.hdr_val', function (ev) {
    var reqHdr = $(ev.target).closest('.req_hdr')
    var hdrName = $('.hdr_name', reqHdr).val()
    var hdrVal = ''
    if ($('.hdr_val > option:selected', reqHdr).val() === 'other...') {
      $('.hdr_val', reqHdr)
        .replaceWith("<input class='hdr_val' type='text'/>")
    } else {
      hdrVal = $('.hdr_val > option:selected', reqHdr).val()
    }
    $('input[type=hidden]', reqHdr).val(hdrName + ':' + hdrVal)
    $('#uri').focus()
  })

  /* handle header value text changes */
  $('#req_hdrs').on('change', 'input.hdr_val', function (ev) {
    var reqHdr = $(ev.target).closest('.req_hdr')
    var hdrName = $('.hdr_name', reqHdr).val()
    var hdrVal = $('.hdr_val:text', reqHdr).val()
    $('input[type=hidden]', reqHdr).val(hdrName + ':' + hdrVal)
    $('#uri').focus()
  })

  /* handle return in textbox values */
  $('#req_hdrs').on('keypress', 'input.hdr_val', function (ev) {
    if (ev.which === 13) {
      var reqHdr = $(ev.target).closest('.req_hdr')
      $('input.hdr_val', reqHdr).trigger('change')
      $('#request_form').submit()
      return false
    }
  })
})
