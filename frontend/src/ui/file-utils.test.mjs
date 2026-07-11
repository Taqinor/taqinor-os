import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatFileSize, fileExtension, matchesAccept, validateFile, validateFiles, clampProgress,
  compressImage, scaledSize, MAX_DIMENSION,
} from './file-utils.js'

const MB = 1024 * 1024

test('formatFileSize : octets / Ko / Mo', () => {
  assert.equal(formatFileSize(0), '0 o')
  assert.equal(formatFileSize(-5), '0 o')
  assert.equal(formatFileSize(512), '512 o')
  assert.equal(formatFileSize(1024), '1 Ko')
  assert.equal(formatFileSize(2048), '2 Ko')
  assert.equal(formatFileSize(1.5 * MB), '1,5 Mo')
  assert.equal(formatFileSize('not-a-number'), '0 o')
})

test('fileExtension : minuscule, sans point, gère les cas limites', () => {
  assert.equal(fileExtension('facture.PDF'), 'pdf')
  assert.equal(fileExtension('photo.scan.JPEG'), 'jpeg')
  assert.equal(fileExtension('sansext'), '')
  assert.equal(fileExtension('.gitignore'), '') // pas d'extension réelle
  assert.equal(fileExtension('fin.'), '')
  assert.equal(fileExtension(null), '')
})

test('matchesAccept : *, mime exact, wildcard, extension, listes', () => {
  const pdf = { name: 'doc.pdf', type: 'application/pdf' }
  const png = { name: 'img.png', type: 'image/png' }
  assert.equal(matchesAccept(pdf, ''), true) // accept vide → tout
  assert.equal(matchesAccept(pdf, 'application/pdf'), true)
  assert.equal(matchesAccept(png, 'application/pdf'), false)
  assert.equal(matchesAccept(png, 'image/*'), true)
  assert.equal(matchesAccept(pdf, 'image/*'), false)
  assert.equal(matchesAccept(pdf, '.pdf'), true)
  assert.equal(matchesAccept(pdf, '.PDF'), true)
  assert.equal(matchesAccept(png, 'application/pdf,image/png,image/jpeg'), true)
  assert.equal(matchesAccept({ name: 'x.gif', type: 'image/gif' }, 'application/pdf,image/png'), false)
})

test('matchesAccept : type vide → repli sur extension (régression N104)', () => {
  // Cas RÉEL : le navigateur ne fournit pas toujours le type MIME — certains
  // .pdf/.png/.jpg sélectionnés (Windows/Linux) ou glissés depuis une autre app
  // arrivent avec type === ''. Sans repli, ils étaient refusés AVANT envoi, ce
  // qui bloquait l'ajout de pièces jointes partout.
  const accept = 'application/pdf,image/png,image/jpeg,image/webp'
  assert.equal(matchesAccept({ name: 'facture.pdf', type: '' }, accept), true)
  assert.equal(matchesAccept({ name: 'scan.PNG', type: '' }, accept), true)
  assert.equal(matchesAccept({ name: 'photo.jpg', type: '' }, accept), true)
  assert.equal(matchesAccept({ name: 'photo.jpeg', type: '' }, accept), true)
  assert.equal(matchesAccept({ name: 'image.webp', type: '' }, accept), true)
  // Reste STRICT : un type vide avec une extension non autorisée est refusé.
  assert.equal(matchesAccept({ name: 'archive.zip', type: '' }, accept), false)
  assert.equal(matchesAccept({ name: 'sansext', type: '' }, accept), false)
  // Wildcard 'image/*' : repli par extension d'image quand le type est absent.
  assert.equal(matchesAccept({ name: 'p.png', type: '' }, 'image/*'), true)
  assert.equal(matchesAccept({ name: 'd.pdf', type: '' }, 'image/*'), false)
})

test('validateFile : type refusé, taille dépassée, OK', () => {
  const accept = 'application/pdf,image/png,image/jpeg,image/webp'
  const okFile = { name: 'f.pdf', type: 'application/pdf', size: 2 * MB }
  assert.equal(validateFile(okFile, { accept, maxSize: 10 * MB }).ok, true)

  const badType = validateFile({ name: 'f.gif', type: 'image/gif', size: 1 * MB }, { accept })
  assert.equal(badType.ok, false)
  assert.equal(badType.code, 'type')

  const tooBig = validateFile({ name: 'f.pdf', type: 'application/pdf', size: 12 * MB }, { accept, maxSize: 10 * MB })
  assert.equal(tooBig.ok, false)
  assert.equal(tooBig.code, 'size')
  assert.match(tooBig.message, /max 10,0 Mo/)

  assert.equal(validateFile(null).ok, false)
  assert.equal(validateFile(null).code, 'missing')
})

test('validateFiles : tri accepté/refusé, mode single', () => {
  const accept = 'application/pdf,image/png'
  const files = [
    { name: 'a.pdf', type: 'application/pdf', size: 1 * MB },
    { name: 'b.gif', type: 'image/gif', size: 1 * MB },
    { name: 'c.png', type: 'image/png', size: 20 * MB },
  ]
  const multi = validateFiles(files, { accept, maxSize: 10 * MB, multiple: true })
  assert.equal(multi.accepted.length, 1) // seul a.pdf passe
  assert.equal(multi.accepted[0].name, 'a.pdf')
  assert.equal(multi.rejected.length, 2) // b (type) + c (taille)

  const single = validateFiles(
    [{ name: 'x.pdf', type: 'application/pdf', size: 1 }, { name: 'y.pdf', type: 'application/pdf', size: 1 }],
    { accept, multiple: false },
  )
  assert.equal(single.accepted.length, 1) // un seul retenu en mode simple
})

test('clampProgress : borne 0–100, gère NaN', () => {
  assert.equal(clampProgress(-10), 0)
  assert.equal(clampProgress(0), 0)
  assert.equal(clampProgress(42.6), 43)
  assert.equal(clampProgress(150), 100)
  assert.equal(clampProgress('abc'), 0)
})

// ── VX77 — compressImage / scaledSize ────────────────────────────────────────

test('scaledSize : borne le bord long, préserve le ratio, no-op si déjà petit', () => {
  assert.deepEqual(scaledSize(4000, 3000, 1600), { width: 1600, height: 1200 })
  assert.deepEqual(scaledSize(3000, 4000, 1600), { width: 1200, height: 1600 })
  assert.deepEqual(scaledSize(800, 600, 1600), { width: 800, height: 600 }) // déjà petit
  assert.deepEqual(scaledSize(0, 0, 1600), { width: 0, height: 0 })
})

test('compressImage : passthrough pour un PDF (jamais compressé)', async () => {
  const pdf = { name: 'bon.pdf', type: 'application/pdf', size: 5_000_000 }
  const out = await compressImage(pdf)
  assert.equal(out, pdf)
})

test('compressImage : passthrough sans document/Image (SSR, vieux navigateur, jsdom absent)', async () => {
  const savedDoc = globalThis.document
  const savedImg = globalThis.Image
  delete globalThis.document
  delete globalThis.Image
  try {
    const photo = { name: 'photo.jpg', type: 'image/jpeg', size: 5_000_000 }
    const out = await compressImage(photo)
    assert.equal(out, photo)
  } finally {
    if (savedDoc !== undefined) globalThis.document = savedDoc
    if (savedImg !== undefined) globalThis.Image = savedImg
  }
})

test('compressImage : passthrough pour un SVG (pas de bitmap à compresser)', async () => {
  const svg = { name: 'plan.svg', type: 'image/svg+xml', size: 10_000 }
  const out = await compressImage(svg)
  assert.equal(out, svg)
})

test('compressImage : réduit un fichier N Mo, plafonne les dimensions, renomme en .jpg', async () => {
  // Mock DOM minimal : Image (charge instantanément), canvas (toBlob renvoie
  // un blob plus petit que l'original), URL.createObjectURL/revokeObjectURL.
  const ORIGINAL_SIZE = 8 * 1024 * 1024 // 8 Mo, routinier sur un appareil moderne
  const COMPRESSED_SIZE = 900 * 1024 // 900 Ko après compression

  class FakeImage {
    set src(_v) {
      this.width = 4032
      this.height = 3024
      queueMicrotask(() => this.onload?.())
    }
  }
  const savedImage = globalThis.Image
  globalThis.Image = FakeImage

  const savedURL = globalThis.URL
  globalThis.URL = { createObjectURL: () => 'blob:fake', revokeObjectURL: () => {} }

  let canvasWidth = null
  let canvasHeight = null
  const fakeCanvas = {
    set width(v) { canvasWidth = v },
    get width() { return canvasWidth },
    set height(v) { canvasHeight = v },
    get height() { return canvasHeight },
    getContext: () => ({ drawImage: () => {} }),
    toBlob: (cb) => cb({ size: COMPRESSED_SIZE }),
  }
  const savedDocument = globalThis.document
  globalThis.document = { createElement: () => fakeCanvas }

  const savedFile = globalThis.File
  globalThis.File = class FakeFile {
    constructor(parts, name, opts) {
      this.parts = parts
      this.name = name
      this.type = opts?.type
      this.size = COMPRESSED_SIZE
    }
  }

  try {
    const original = { name: 'chantier.jpg', type: 'image/jpeg', size: ORIGINAL_SIZE }
    const out = await compressImage(original)
    assert.equal(canvasWidth, MAX_DIMENSION, 'bord long plafonné à 1600px')
    assert.ok(canvasHeight < canvasWidth, 'ratio préservé (portrait/paysage source)')
    assert.ok(out.size < original.size, 'le fichier compressé est plus petit')
    assert.equal(out.name, 'chantier.jpg')
    assert.equal(out.type, 'image/jpeg')
  } finally {
    if (savedImage !== undefined) globalThis.Image = savedImage; else delete globalThis.Image
    if (savedURL !== undefined) globalThis.URL = savedURL; else delete globalThis.URL
    if (savedDocument !== undefined) globalThis.document = savedDocument; else delete globalThis.document
    if (savedFile !== undefined) globalThis.File = savedFile; else delete globalThis.File
  }
})
