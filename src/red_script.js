
/* Configuration */

/* global $, prettyPrint */

var config = JSON.parse($('#config').html()) // eslint-disable-line

$(document).ready(function () {
  'use strict'

  /* URI */

  $('input').keypress(function (e) {
    if (e.which === 13) {
      $('#request_form').submit()
      return false
    }
  })

  /* help */

  $('#help').click(function () {
    $('.help').toggle()
  })

  $('.help').click(function () {
    $(this).fadeOut()
  })

  /* single response display */

  var hiddenList = $('#hidden_list')

  $('span.hdr').hoverPopup(
    function (e) {
      var name = $(this).attr('data-name')
      return $('li#header-' + name, hiddenList).html()
    },
    function (e) {
      var name = $(this).attr('data-name')
      var offset = $(this).attr('data-offset')
      $("span.hdr[data-name='" + name + "']").addClass('hilight')
      $('li.note').each(function (index, note) {
        var noteInteresting = false
        var subjects = $(note).attr('data-subject').split(' ')
        for (var i = 0; i < subjects.length; i++) {
          var subject = subjects[i]
          if (subject === 'header-' + name) {
            noteInteresting = true
            break
          }
          if (subject === 'offset-' + offset) {
            noteInteresting = true
            break
          }
        }
        if (!noteInteresting) {
          $(note).fadeTo(100, 0.15)
        }
      })
    },
    function (e) {
      var name = $(this).attr('data-name')
      $("span.hdr[data-name='" + name + "']").removeClass('hilight')
      $('li.note').fadeTo(100, 1.0)
    }
  )

  function findHeaderTargets (subjects, cb) {
    var targets = []
    for (var i = 0; i < subjects.length; i++) {
      var subject = subjects[i]
      var target
      if (subject.indexOf('offset-') === 0) {
        target = $("span.hdr[data-offset='" + subject.slice(7) + "']")
      } else if (subject.indexOf('header-') === 0) {
        target = $("span.hdr[data-name='" + subject.slice(7) + "']")
      }
      if (target) {
        cb(target)
        targets.push(target)
      }
    }
  }

  $('li.note span').hoverPopup(
    function (e) {
      return $('li#' + $(this).parent().attr('data-name'), hiddenList)
        .html()
    },
    function (e) {
      findHeaderTargets(
        $(this).parent().attr('data-subject').split(' '),
        function (target) {
          target.addClass('hilight')
        }
      )
    },
    function (e) {
      findHeaderTargets(
        $(this).parent().attr('data-subject').split(' '),
        function (target) {
          target.removeClass('hilight')
        }
      )
    }
  )

  var bodyViewClicks = 0
  $('#body_view').click(function () {
    bodyViewClicks += 1
    if (bodyViewClicks % 2 === 1) {
      $('#details').fadeOut('fast', function () {
        $('#body').fadeIn('fast')
        prettyPrint()
        $('#body_view').text('show notes')
      })
    } else {
      $('#body').fadeOut('fast', function () {
        $('#details').fadeIn('fast')
        $('#body_view').text('show body')
      })
    }
    return false
  })

  $('#save').click(function () {
    $('#save_form').submit()
  })

  /* multiple result display */

  var tid = false
  $('tr.droid').hoverIntent(function () {
    var classes = this.className.split(' ')
    $('li.note').fadeTo(100, 0.15)
    for (var i = 0; i < classes.length; i++) {
      var c = classes[i]
      if (c !== 'droid') {
        $('li.note:eq(' + c + ')').fadeTo(50, 1.0)
      }
    }
    if (tid !== false) {
      clearTimeout(tid)
      tid = false
    }
  }, function () {
    tid = setTimeout(function () {
      $('li.note').fadeTo(50, 1.0)
    }, 100)
  })

  $('span.prob_num').hoverPopup(function (e) {
    return $(this).children('.hidden').html()
  })

  $('a.preview').hoverPopup(function (e) {
    var link = (this.title !== '') ? this.title : this.href
    return "<img src='" + link + "'/><br />" + link
  })
})
