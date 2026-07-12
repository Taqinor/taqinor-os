// QD2 — filenameFromResponse : lit le nom cohérent posé par le serveur dans
// l'en-tête Content-Disposition (TAQINOR_Facture_Client_FAC-….pdf), sinon repli.
// Exécuté en CI : node --test src/utils/downloadBlob.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { filenameFromResponse, downloadBlobInGesture, isIosOuStandalone } from './downloadBlob.js'

test('lit filename="…" de Content-Disposition', () => {
  const res = {
    headers: {
      'content-disposition':
        'inline; filename="TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf"',
    },
  }
  assert.equal(
    filenameFromResponse(res, 'x.pdf'),
    'TAQINOR_Facture_Reda-Kasri_FAC-202607-0001.pdf')
})

test('gère filename* RFC 5987 (UTF-8)', () => {
  const res = {
    headers: {
      'content-disposition':
        "attachment; filename*=UTF-8''TAQINOR_Devis_Client_DEV-1.pdf",
    },
  }
  assert.equal(
    filenameFromResponse(res, 'x.pdf'), 'TAQINOR_Devis_Client_DEV-1.pdf')
})

test('gère les headers via getter (Headers-like)', () => {
  const res = {
    headers: {
      get: (k) => (k === 'content-disposition'
        ? 'inline; filename="A_B_C.pdf"' : null),
    },
  }
  assert.equal(filenameFromResponse(res, 'x.pdf'), 'A_B_C.pdf')
})

test('repli sur le fallback quand aucun header', () => {
  assert.equal(filenameFromResponse({}, 'DEV-1.pdf'), 'DEV-1.pdf')
  assert.equal(filenameFromResponse(null, 'DEV-1.pdf'), 'DEV-1.pdf')
  assert.equal(filenameFromResponse(undefined), 'document.pdf')
})

// ── VX172 — isIosOuStandalone() / downloadBlobInGesture() ──────────────────

function fakeWindow({ closed = false } = {}) {
  return { closed, location: '', document: { title: '' } }
}

test('isIosOuStandalone : faux sans window (SSR/test générique)', () => {
  const saved = global.window
  delete global.window
  try {
    assert.equal(isIosOuStandalone(), false)
  } finally {
    global.window = saved
  }
})

test('isIosOuStandalone : vrai sur UA iPhone', () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)' },
    matchMedia: () => ({ matches: false }),
  }
  assert.equal(isIosOuStandalone(), true)
})

test('isIosOuStandalone : vrai en display-mode standalone (Android PWA installée)', () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (Linux; Android 14)' },
    matchMedia: () => ({ matches: true }),
  }
  assert.equal(isIosOuStandalone(), true)
})

test('isIosOuStandalone : faux desktop hors coquille', () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    matchMedia: () => ({ matches: false }),
  }
  assert.equal(isIosOuStandalone(), false)
})

test('downloadBlobInGesture : hors iOS/standalone -> a.download direct, aucun onglet', () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' },
    matchMedia: () => ({ matches: false }),
    open: () => { throw new Error('ne doit jamais être appelé hors iOS/standalone') },
  }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = { body: { appendChild() {}, removeChild() {} }, createElement: () => ({ click() {} }) }

  const pending = downloadBlobInGesture()
  const ok = pending.deliver(new Blob(['x']), 'export.xlsx')

  assert.equal(pending.win, null)
  assert.equal(ok, true)
})

test('downloadBlobInGesture : iOS -> onglet pré-ouvert redirigé vers le blob', () => {
  const win = fakeWindow()
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)' },
    matchMedia: () => ({ matches: false }),
    open: () => win,
  }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }

  const pending = downloadBlobInGesture()
  const ok = pending.deliver(new Blob(['x']), 'export.xlsx')

  assert.equal(ok, true)
  assert.equal(win.location, 'blob:fake-url')
  assert.equal(win.document.title, 'export.xlsx')
})

test('downloadBlobInGesture : iOS mais onglet bloqué -> repli a.download', () => {
  global.window = {
    navigator: { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)' },
    matchMedia: () => ({ matches: false }),
    open: () => null,
  }
  global.URL = { createObjectURL: () => 'blob:fake-url', revokeObjectURL: () => {} }
  global.document = { body: { appendChild() {}, removeChild() {} }, createElement: () => ({ click() {} }) }

  const pending = downloadBlobInGesture()
  const ok = pending.deliver(new Blob(['x']), 'export.xlsx')

  assert.equal(pending.win, null)
  assert.equal(ok, false)
})
