// CAL180 — EXPORT « IMAGE HD ». Exécuté en CI :
//   node --test src/features/calepinage/exportImage.test.mjs
//
// Ce fichier prouve que l'export demande bien un rendu HORS ÉCRAN au builder, qu'il rend
// à l'utilisateur les dimensions RÉELLEMENT obtenues (jamais celles demandées), qu'il
// nomme le fichier avec cette taille, et qu'aucun échec ne casse l'écran : chaque refus
// revient en MOTIF affichable. Rien n'est posté au serveur : l'affiche client existante
// n'est pas touchée.
import test from 'node:test'
import assert from 'node:assert/strict'

import { exporterImageHd, nomFichierHd, FACTEURS_HD } from './exportImage.js'

const blobFactice = { type: 'image/png', size: 123 }

/** Petit espion sans dépendance (ce fichier tourne sous `node --test`). */
function espion(impl) {
  const appels = []
  const fn = (...args) => {
    appels.push(args)
    return impl ? impl(...args) : undefined
  }
  fn.appels = appels
  return fn
}

test('CAL180 — le nom de fichier porte la taille réellement obtenue', () => {
  assert.equal(nomFichierHd('DEV-2026-014', 2560, 1440), 'DEV-2026-014-2560x1440.png')
})

test('CAL180 — une référence bancale est assainie sans perdre un nom utilisable', () => {
  assert.equal(nomFichierHd('a/b c', 100, 50), 'a-b-c-100x50.png')
  assert.equal(nomFichierHd(null, 100, 50), 'calepinage-100x50.png')
  assert.equal(nomFichierHd('///', 100, 50), 'calepinage-100x50.png')
})

test('CAL180 — 2× et 3× sont les facteurs proposés', () => {
  assert.deepEqual(FACTEURS_HD, [2, 3])
})

test('CAL180 — l’export demande le facteur choisi et télécharge le PNG obtenu', async () => {
  const renderImageHd = espion(async () => ({ blob: blobFactice, width: 2560, height: 1440, scale: 2 }))
  const telecharger = espion()
  const res = await exporterImageHd({ current: { renderImageHd } }, { scale: 2, reference: 'CAL-7', telecharger })
  assert.deepEqual(renderImageHd.appels, [[2]])
  assert.deepEqual(res, { ok: true, width: 2560, height: 1440, scale: 2, nom: 'CAL-7-2560x1440.png' })
  assert.deepEqual(telecharger.appels, [[blobFactice, 'CAL-7-2560x1440.png']])
})

test('CAL180 — le facteur RENDU est celui obtenu, pas celui demandé (plafond de taille)', async () => {
  const renderImageHd = espion(async () => ({ blob: blobFactice, width: 8192, height: 4608, scale: 2.13 }))
  const res = await exporterImageHd({ current: { renderImageHd } }, { scale: 3, telecharger: espion() })
  assert.deepEqual(renderImageHd.appels, [[3]])
  assert.equal(res.scale, 2.13) // ni 3, ni une supposition
  assert.equal(res.nom, 'calepinage-8192x4608.png')
})

test('CAL180 — builder absent ⇒ motif affichable, aucun téléchargement', async () => {
  const telecharger = espion()
  const attendu = { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' }
  assert.deepEqual(await exporterImageHd(null, { telecharger }), attendu)
  assert.deepEqual(await exporterImageHd({ current: {} }, { telecharger }), attendu)
  assert.equal(telecharger.appels.length, 0)
})

test('CAL180 — scène non rendable ⇒ motif, jamais une image vide présentée comme bonne', async () => {
  const res = await exporterImageHd({ current: { renderImageHd: async () => null } }, { telecharger: espion() })
  assert.equal(res.ok, false)
  assert.ok(res.motif.includes('Scène non rendable'))
})

test('CAL180 — un rendu qui lève revient en motif, jamais en exception', async () => {
  const res = await exporterImageHd(
    {
      current: {
        renderImageHd: async () => {
          throw new Error('WebGL')
        },
      },
    },
    { telecharger: espion() },
  )
  assert.deepEqual(res, { ok: false, motif: 'Le rendu haute résolution a échoué sur ce navigateur.' })
})

test('CAL180 — téléchargement refusé ⇒ motif', async () => {
  const res = await exporterImageHd(
    { current: { renderImageHd: async () => ({ blob: blobFactice, width: 10, height: 10, scale: 2 }) } },
    {
      telecharger: () => {
        throw new Error('bloqué')
      },
    },
  )
  assert.deepEqual(res, { ok: false, motif: 'Téléchargement refusé par le navigateur.' })
})
