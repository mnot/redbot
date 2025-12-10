/* global prettyPrint */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'
import tippy from 'tippy.js'

docReady(function () {
  /* single response display - header hover */

  qsa('span.hdr', function (element) {
    const headerName = element.getAttribute('data-name')
    const offset = element.getAttribute('data-offset')
    const tooltip = qs('span.tip', element)
    if (tooltip === null) {
      return
    }
    tippy(element, {
      content: tooltip.innerHTML,
      allowHTML: true,
      theme: 'redbot',
      delay: [10, 10],
      interactive: true,
      interactiveBorder: 5,
      placement: 'bottom-end',
      offset: [50, 5],
      maxWidth: 460,
      appendTo: document.body,
      onShow: function (tippyInstance) {
        element.classList.toggle('hilight')
        highlightHeaderRelated(headerName, offset, true)
      },
      onHidden: function (tippyInstance) {
        element.classList.toggle('hilight')
        highlightHeaderRelated(headerName, offset, false)
      }
    })
  })

  function highlightHeaderRelated (headerName, offset, direction) {
    qsa('li.note', function (element) {
      let noteInteresting = false
      const subjects = element.getAttribute('data-subject').split(' ')
      subjects.forEach(subject => {
        if (subject === `field-${headerName}`) {
          noteInteresting = true
        }
        if (subject === `offset-${offset}`) {
          noteInteresting = true
        }
      })
      if (!noteInteresting) {
        element.style.opacity = direction ? 0.2 : 1.0
      }
    })
  }

  /* single response display - note hover */

  qsa('li.note span', function (element) {
    const tooltip = qs('span.tip', element)
    if (tooltip === null) {
      return
    }
    tippy(element, {
      content: tooltip.innerHTML,
      allowHTML: true,
      theme: 'redbot',
      delay: [10, 10],
      interactive: true,
      interactiveBorder: 5,
      placement: 'bottom-end',
      offset: [50, 5],
      maxWidth: 460,
      appendTo: document.body,
      onShow: function (tippyInstance) {
        highlightNoteRelated(element, true)
      },
      onHidden: function (tippyInstance) {
        highlightNoteRelated(element, false)
      }
    })
  })

  function highlightNoteRelated (note, direction) {
    const noteSubjects = note.parentNode.getAttribute('data-subject').split(' ')
    noteSubjects.forEach(subject => {
      if (subject.indexOf('offset-') === 0) {
        qsa(`span.hdr[data-offset='${subject.slice(7)}']`, function (element) {
          element.classList.toggle('hilight')
        })
      } else if (subject.indexOf('field-') === 0) {
        qsa(`span.hdr[data-name='${subject.slice(6)}']`, function (element) {
          element.classList.toggle('hilight')
        })
      }
    })
  }

  /* single response display - response body */

  const bodyButton = qs('#body_view')
  let showingBody = false
  if (bodyButton !== null) {
    bodyButton.onclick = function () {
      toggleHidden(qs('#body'))
      toggleHidden(qs('#details'))
      if (!showingBody) {
        qs('#body_view').textContent = config.i18n.view_notes
        prettyPrint()
      } else {
        qs('#body_view').textContent = config.i18n.view_body
      }
      showingBody = !showingBody
    }
  }

  /* single response display - save */

  const saveButton = qs('#save')
  if (saveButton !== null) {
    saveButton.onclick = function () {
      qs('#save_form').submit()
    }
  }
})
