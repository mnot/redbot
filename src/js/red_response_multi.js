/* global qs qsa docReady tippy */

docReady(function () {
  qsa('span.prob_num', function (element) {
    var tooltip = qs('span.tip', element)
    if (tooltip === null) {
      return
    }
    tippy(element, {
      content: tooltip,
      theme: 'redbot',
      delay: [10, 10],
      interactive: true,
      interactiveBorder: 5,
      placement: 'bottom-start',
      offset: [50, 5],
      maxWidth: 460,
      appendTo: document.body
    })
  })

  qsa('a.preview', function (element) {
    var link = (element.title !== '') ? element.title : element.href
    var tooltip = document.createElement('img')
    tooltip.src = link
    tippy(element, {
      content: tooltip,
      theme: 'redbot',
      delay: [10, 10],
      interactive: true,
      interactiveBorder: 5,
      placement: 'bottom-start',
      offset: [50, 5],
      maxWidth: 460,
      appendTo: document.body
    })
  })

  qsa('tr.droid', function (element) {
    var noteNums = []
    qsa('span.prob_num', function (span) {
      console.log(span)
      if (span.textContent) {
        noteNums.push(span.textContent)
      }
    }, qs('td:last-child', element))
    element.onmouseover = element.onmouseout = function () {
      qsa('li.note', function (noteElement) {
        var noteOffset = noteElement.getAttribute('data-offset')
        if (noteNums.includes(noteOffset)) {
          noteElement.classList.toggle('hilight')
        }
      })
    }
  })
})
