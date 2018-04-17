/*
jQuery extension to hover a popup (#popup).
*/

/* global jQuery, $ */

var tid = false
jQuery.fn.hoverPopup = function (fnText, fnOver, fnOut) {
  var fnOverPopup = function (e) {
    if (tid !== false) {
      clearTimeout(tid)
      tid = false
    }
    var text = fnText.call(this, e)
    if (text) {
      var popTop = $(this).position().top + 15
      var popupWidth = 450
      var popupX
      if (popupWidth + 10 > window.innerWidth) {
        popupX = 5
        popupWidth = window.innerWidth - 10
      } else if (e.pageX + popupWidth + 10 < window.innerWidth) {
        popupX = e.pageX + 5
      } else if (e.pageX - popupWidth - 5 > 5) {
        popupX = e.pageX - popupWidth + 5
      } else {
        popupX = 5
      }
      $('#popup')
        .fadeIn('fast')
        .css('top', popTop + 'px')
        .css('left', popupX + 'px')
        .css('width', popupWidth + 'px')
        .html(text)
      var margin = 28
      var popHeight = $('#popup').height()
      var winBottom = $(window).height() + $(window).scrollTop()
      if (winBottom < popTop + popHeight - margin) {
        var placement = winBottom - margin - popHeight
        $('#popup').animate({ top: placement }, 100)
      }
    } else {
      $('#popup').hide()
    }
    if (fnOver) {
      fnOver.call(this, e)
    }
  }
  var fnOutPopup = function (e) {
    tid = setTimeout(function () {
      $('#popup').fadeOut('fast')
    }, 500)
    if (fnOut) {
      fnOut.call(this, e)
    }
  }
  return jQuery.fn.hoverIntent.call(this, fnOverPopup, fnOutPopup)
}

$(document).ready(function () {
  $('#popup').hoverIntent(function () {
    if (tid !== false) {
      clearTimeout(tid)
      tid = false
    }
  }, function () {
    $('#popup').fadeOut('fast')
  })
})
