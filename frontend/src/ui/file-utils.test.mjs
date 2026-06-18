import test from 'node:test'
import assert from 'node:assert/strict'
import {
  formatFileSize, fileExtension, matchesAccept, validateFile, validateFiles, clampProgress,
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
