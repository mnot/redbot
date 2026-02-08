/* global prettyPrint */

import { qs, qsa, docReady, toggleHidden, config } from './red_util.js'
import tippy from 'tippy.js'

docReady(function () {
  /* single response display - header hover */

  qsa('li.hdr', function (element) {
    const headerName = element.getAttribute('data-name')
    const offset = element.getAttribute('data-offset')

    element.addEventListener('mouseenter', function () {
      element.classList.add('hilight')
      highlightHeaderRelated(headerName, offset, true)
    })
    element.addEventListener('mouseleave', function () {
      element.classList.remove('hilight')
      highlightHeaderRelated(headerName, offset, false)
    })

    const tooltip = qs('span.tip', element)
    if (tooltip) {
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
        appendTo: document.body
      })
    }
  })

  function highlightHeaderRelated (headerName, offset, direction) {
    qsa('li.note', function (element) {
      let noteInteresting = false
      const rawSubjects = element.getAttribute('data-subject')
      if (rawSubjects) {
        const subjects = rawSubjects.toLowerCase().split(' ')
        subjects.forEach(subject => {
          if (subject === `field-${headerName.toLowerCase()}`) {
            noteInteresting = true
          }
          if (subject === `offset-${offset}`) {
            noteInteresting = true
          }
        })
      }
      if (!noteInteresting) {
        element.style.opacity = direction ? 0.2 : 1.0
      }
    })
  }

  /* single response display - note hover */

  qsa('li.note', function (element) {
    element.addEventListener('mouseenter', function () {
      highlightNoteRelated(element, true)
    })
    element.addEventListener('mouseleave', function () {
      highlightNoteRelated(element, false)
    })

    const tooltip = qs('span.tip', element)
    if (tooltip) {
      tippy(qs('span', element), {
        content: tooltip.innerHTML,
        allowHTML: true,
        theme: 'redbot',
        delay: [10, 10],
        interactive: true,
        interactiveBorder: 5,
        placement: 'bottom-end',
        offset: [50, 5],
        maxWidth: 460,
        appendTo: document.body
      })
    }
  })

  function highlightNoteRelated (note, direction) {
    const rawSubject = note.getAttribute('data-subject')
    if (rawSubject) {
      const noteSubjects = rawSubject.toLowerCase().split(' ')
      noteSubjects.forEach(subject => {
        if (subject.indexOf('offset-') === 0) {
          qsa(`li.hdr[data-offset='${subject.slice(7)}']`, function (element) {
            if (direction) {
              element.classList.add('hilight')
            } else {
              element.classList.remove('hilight')
            }
          })
        } else if (subject.indexOf('field-') === 0) {
          const fieldName = subject.slice(6)
          qsa(`li.hdr[data-name='${fieldName}']`, function (element) {
            if (direction) {
              element.classList.add('hilight')
            } else {
              element.classList.remove('hilight')
            }
          })
        }
      })
    }
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

  /* single response display - sort headers */
  const sortButton = qs('#sort_headers')
  let sorted = false
  if (sortButton !== null) {
    sortButton.onclick = function (e) {
      e.preventDefault()
      const response = qs('#response')
      const status = qs('.status', response)
      const headers = []
      qsa('.hdr', function (element) {
        headers.push(element)
      }, response)
      headers.sort(function (a, b) {
        if (!sorted) {
          const aName = a.getAttribute('data-name')
          const bName = b.getAttribute('data-name')
          if (aName < bName) {
            return -1
          }
          if (aName > bName) {
            return 1
          }
          return 0
        } else {
          const aOffset = parseInt(a.getAttribute('data-offset'), 10)
          const bOffset = parseInt(b.getAttribute('data-offset'), 10)
          return aOffset - bOffset
        }
      })

      while (response.firstChild) {
        response.removeChild(response.firstChild)
      }

      response.appendChild(status)
      headers.forEach(function (element) {
        response.appendChild(element)
      })

      if (!sorted) {
        // We just sorted by alpha
        sortButton.textContent = config.i18n.wire_order
      } else {
        // We just sorted by wire order
        sortButton.textContent = config.i18n.sort_alpha
      }
      sorted = !sorted
    }
  }
})
