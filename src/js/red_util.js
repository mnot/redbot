export function qs (query, element) {
  if (element === undefined) {
    return document.querySelector(query)
  } else {
    return element.querySelector(query)
  }
}

export function qsa (query, fn, element) {
  let results
  if (element === undefined) {
    results = document.querySelectorAll(query)
  } else {
    results = element.querySelectorAll(query)
  }
  results.forEach(fn)
}

export function toggleHidden (element) {
  element.classList.toggle('hidden')
}

export function docReady (fn) {
  if (document.readyState !== 'loading') {
    fn()
  } else {
    document.addEventListener('DOMContentLoaded', fn)
  }
}

export function escapeHtml (unsafe) {
  if (unsafe === undefined) {
    return undefined
  }
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// ie11 fix
if (window.NodeList && !window.NodeList.prototype.forEach) {
  window.NodeList.prototype.forEach = Array.prototype.forEach
}

export const config = JSON.parse(qs('#config').innerHTML)
