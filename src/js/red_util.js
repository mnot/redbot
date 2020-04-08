
function qs (query, element) {
  if (element === undefined) {
    return document.querySelector(query)
  } else {
    return element.querySelector(query)
  }
}

function qsa (query, fn, element) {
  var results
  if (element === undefined) {
    results = document.querySelectorAll(query)
  } else {
    results = element.querySelectorAll(query)
  }
  results.forEach(fn)
}

function toggleHidden (element) {
  element.classList.toggle('hidden')
}

function docReady (fn) {
  if (document.readyState !== 'loading') {
    fn()
  } else {
    document.addEventListener('DOMContentLoaded', fn)
  }
}
