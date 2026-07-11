// VX48 — openPdfInGesture() : l'onglet est pré-ouvert SYNCHRONE (dans le
// geste), puis `deliver()` le redirige vers le blob une fois prêt — le seul
// patron que Safari iOS honore après un `await`.
// Exécuté en CI : node --test src/utils/pdfBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { openPdfInGesture } from './pdfBlob.js'

// Fenêtre factice minimale (jamais document.createElement — CAUTION : pas de
// mock global de document, seulement window.open/URL en globals de test).
function fakeWindow({ closed = false } = {}) {
  return { closed, location: '', document: { title: '' } }
}

test('geste frais : deliver() redirige la fenêtre pré-ouverte vers le blob', () => {
  const win = fakeWindow()
  global.window = { open: () => win }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }

  const pending = openPdfInGesture()
  const ok = pending.deliver(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(ok, true)
  assert.equal(win.location, 'blob:fake-url')
  assert.equal(win.document.title, 'devis.pdf')
})

test('blocage : window.open renvoie null -> deliver() renvoie false (repli à l\'appelant)', () => {
  global.window = { open: () => null }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }

  const pending = openPdfInGesture()
  const ok = pending.deliver(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(ok, false)
  assert.equal(pending.win, null)
})

test('blocage : la fenêtre pré-ouverte est déjà fermée -> deliver() renvoie false', () => {
  const win = fakeWindow({ closed: true })
  global.window = { open: () => win }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }

  const pending = openPdfInGesture()
  const ok = pending.deliver(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(ok, false)
})
