// ACAL896 — « Vidéo 10 s ». Exécuté en CI :
//   node --test src/features/calepinage/exportVideo.test.mjs
// Prouve : MediaRecorder absent ⇒ motif sans fichier ; nom `<reference>-orbite.<ext>` avec l'extension du
// format réellement enregistré ; un échec revient en motif, jamais en exception ; rien n'est téléchargé en cas d'échec.
import test from 'node:test'
import assert from 'node:assert/strict'

import { exporterVideoOrbite, nomFichierOrbite } from './exportVideo.js'

const blobFactice = { type: 'video/mp4', size: 99 }
const espion = (impl) => {
  const appels = []
  const fn = (...args) => { appels.push(args); return impl ? impl(...args) : undefined }
  fn.appels = appels
  return fn
}

test('ACAL896 — le nom suit la référence et le format réellement enregistré', () => {
  assert.equal(nomFichierOrbite('DEV-2026-014', 'mp4'), 'DEV-2026-014-orbite.mp4')
  assert.equal(nomFichierOrbite('a/b c', 'webm'), 'a-b-c-orbite.webm')
  assert.equal(nomFichierOrbite(null, 'webm'), 'calepinage-orbite.webm')
})

test('ACAL896 — l’orbite enregistrée est téléchargée sous `<reference>-orbite.mp4`', async () => {
  const enregistrerOrbite = espion(async () => ({ ok: true, blob: blobFactice, extension: 'mp4', mime: 'video/mp4' }))
  const telecharger = espion()
  const res = await exporterVideoOrbite({ current: { enregistrerOrbite } }, { reference: 'CAL-7', telecharger })
  assert.deepEqual(res, { ok: true, nom: 'CAL-7-orbite.mp4' })
  assert.deepEqual(telecharger.appels, [[blobFactice, 'CAL-7-orbite.mp4']])
})

test('ACAL896 — MediaRecorder absent (motif du builder) ⇒ motif affiché, aucun fichier', async () => {
  const motif = 'Enregistrement vidéo indisponible sur ce navigateur — aucun fichier produit.'
  const telecharger = espion()
  const res = await exporterVideoOrbite({ current: { enregistrerOrbite: async () => ({ ok: false, motif }) } }, { telecharger })
  assert.deepEqual(res, { ok: false, motif })
  assert.equal(telecharger.appels.length, 0)
})

test('ACAL896 — builder absent ou qui lève ⇒ motif, jamais une exception', async () => {
  const telecharger = espion()
  assert.equal((await exporterVideoOrbite(null, { telecharger })).ok, false)
  const res = await exporterVideoOrbite({ current: { enregistrerOrbite: async () => { throw new Error('boum') } } }, { telecharger })
  assert.equal(res.ok, false)
  assert.equal(telecharger.appels.length, 0)
})
