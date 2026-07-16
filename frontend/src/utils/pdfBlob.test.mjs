// VX48/VX49 — openPdfInGesture() : l'onglet est pré-ouvert SYNCHRONE (dans le
// geste), puis `deliver()` le redirige vers le blob une fois prêt — le seul
// patron que Safari iOS honore après un `await`. ouvrirPdfBlob() détecte aussi
// la fenêtre INERTE (non-null mais bloquée) en plus du simple `null`.
// Exécuté en CI : node --test src/utils/pdfBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { openPdfInGesture, ouvrirPdfBlob, openPdfBlob } from './pdfBlob.js'

// Fenêtre factice minimale (jamais document.createElement — CAUTION : pas de
// mock global de document, seulement window.open/URL en globals de test).
function fakeWindow({ closed = false } = {}) {
  return { closed, location: '', document: { title: '' } }
}

// document factice minimal — CAUTION : jamais un spy sur le VRAI
// document/HTMLAnchorElement.prototype (il n'y en a pas ici, plain Node), on
// fournit juste un objet document complet pour openPdfBlob()'s <a> click.
function fakeDocument() {
  const body = { appendChild() {}, removeChild() {} }
  return {
    body,
    createElement: () => ({ click() {}, style: {} }),
  }
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

// ── VX49 — détection réelle du blocage popup (null PUIS fenêtre inerte) ──

test('ouvrirPdfBlob : window.open renvoie null -> repli download', () => {
  global.window = { open: () => null }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = fakeDocument()

  const result = ouvrirPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(result, 'download')
})

test('ouvrirPdfBlob : window.open renvoie un objet INERTE (closed=true) -> repli download aussi', () => {
  global.window = { open: () => fakeWindow({ closed: true }) }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = fakeDocument()

  const result = ouvrirPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(result, 'download')
})

test('ouvrirPdfBlob : window.open renvoie un objet inerte SANS `closed` défini -> repli download', () => {
  global.window = { open: () => ({ location: '' }) } // pas de `closed` du tout
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = fakeDocument()

  const result = ouvrirPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(result, 'download')
})

test('ouvrirPdfBlob : fenêtre usable -> "open", aucun repli', () => {
  global.window = { open: () => fakeWindow({ closed: false }) }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = fakeDocument()

  const result = ouvrirPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(result, 'open')
})

// ── VX49 — un blob/DOM invalide ne plante jamais et ne fuit pas l'URL ──

test('openPdfBlob : un DOM défaillant (createElement en échec) ne lève pas et révoque quand même', async () => {
  let revoked = false
  const realSetTimeout = global.setTimeout
  global.setTimeout = (fn) => { fn(); return 0 } // exécute le revoke immédiatement (pas de vraie attente)
  global.URL = {
    createObjectURL: () => 'blob:fake-url',
    revokeObjectURL: () => { revoked = true },
  }
  global.document = {
    body: { appendChild() {}, removeChild() {} },
    createElement: () => { throw new Error('DOM indisponible') },
  }

  try {
    // VX172 — openPdfBlob est désormais async (détection iOS/standalone avant
    // le <a>) : on attend la promesse pour observer le `finally` (revoke).
    await assert.doesNotReject(() => openPdfBlob(new Blob(['x']), 'x.pdf'))
    assert.equal(revoked, true)
  } finally {
    global.setTimeout = realSetTimeout
  }
})

// ── VX172 — openPdfBlob : repli iOS/standalone sans target=_blank ──────────

test('openPdfBlob : iOS/standalone -> pas de target=_blank (download pur)', async () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)' },
    matchMedia: () => ({ matches: false }),
  }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  const anchor = { click() {} }
  global.document = { body: { appendChild() {}, removeChild() {} }, createElement: () => anchor }

  await openPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(anchor.target, undefined)
  assert.equal(anchor.download, 'devis.pdf')
})

test('openPdfBlob : desktop hors coquille -> garde target=_blank + noopener', async () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    matchMedia: () => ({ matches: false }),
  }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  const anchor = { click() {} }
  global.document = { body: { appendChild() {}, removeChild() {} }, createElement: () => anchor }

  await openPdfBlob(new Blob(['x'], { type: 'application/pdf' }), 'devis.pdf')

  assert.equal(anchor.target, '_blank')
  assert.equal(anchor.rel, 'noopener')
})
