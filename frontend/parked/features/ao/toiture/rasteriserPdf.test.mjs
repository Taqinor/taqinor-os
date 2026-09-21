import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  estPdf,
  estImageSupportee,
  estFormatSupporte,
  messageFormatNonSupporte,
  normaliserRotation,
  bornerPage,
  facteurEchelle,
  doitRerasteriser,
  listerPages,
  ouvrirDocument,
  rasteriserPage,
  libererFond,
} from './rasteriserPdf.js'

/* AOF79 — verrouille la logique de fond de calque PDF : quelle page, quelle
   rotation, quelle échelle, quand re-peindre, et surtout QU'UNE SEULE page est
   peinte pour un document de 20 pages (le non-blocage de l'UI tient à ça). */

// ── Faux document pdf.js : compte les pages réellement peintes. ────────────────
function fauxDocument(numPages = 20) {
  const peintes = []
  let detruit = false
  return {
    numPages,
    peintes,
    get detruit() {
      return detruit
    },
    destroy() {
      detruit = true
    },
    async getPage(n) {
      return {
        getViewport({ scale, rotation }) {
          const portrait = rotation % 180 === 0
          return {
            width: (portrait ? 595 : 842) * scale,
            height: (portrait ? 842 : 595) * scale,
          }
        },
        render({ viewport }) {
          peintes.push({ n, largeur: viewport.width })
          return { promise: Promise.resolve() }
        },
      }
    },
  }
}

function fauxCanvas() {
  return {
    width: 0,
    height: 0,
    getContext: () => ({}),
  }
}

test('les formats acceptés sont reconnus par type MIME ET par extension', () => {
  assert.equal(estPdf({ type: 'application/pdf' }), true)
  assert.equal(estPdf({ name: 'plan-masse.PDF' }), true)
  assert.equal(estImageSupportee({ type: 'image/jpeg' }), true)
  assert.equal(estImageSupportee({ name: 'toiture.webp' }), true)
  assert.equal(estFormatSupporte({ name: 'plan.dxf', type: '' }), false)
})

test('un format non supporté dégrade avec un message FR explicite', () => {
  const msg = messageFormatNonSupporte({ name: 'plan.dxf' })
  assert.match(msg, /plan\.dxf/)
  assert.match(msg, /PDF/)
  assert.match(msg, /DXF/)
  // Message d'humain, pas un code technique.
  assert.equal(/undefined|null|Error/.test(msg), false)
})

test('la rotation est toujours un quart de tour dans [0, 360)', () => {
  assert.equal(normaliserRotation(90), 90)
  assert.equal(normaliserRotation(450), 90)
  assert.equal(normaliserRotation(-90), 270)
  assert.equal(normaliserRotation(0), 0)
  assert.equal(normaliserRotation('abc'), 0)
})

test('le numéro de page est borné au document', () => {
  assert.equal(bornerPage(0, 20), 1)
  assert.equal(bornerPage(21, 20), 20)
  assert.equal(bornerPage(7, 20), 7)
  assert.equal(bornerPage(NaN, 20), 1)
})

test("l'échelle remplit la largeur, tient compte du DPR et reste bornée", () => {
  assert.equal(facteurEchelle({ largeurDisponible: 595, largeurPage: 595, dpr: 1 }), 1)
  assert.equal(facteurEchelle({ largeurDisponible: 1190, largeurPage: 595, dpr: 1 }), 2)
  // DPR écrêté à 2 et échelle bornée par `max`.
  assert.equal(facteurEchelle({ largeurDisponible: 5950, largeurPage: 595, dpr: 4, max: 6 }), 6)
  assert.equal(facteurEchelle({ largeurDisponible: 0, largeurPage: 595 }), 1)
})

test('on ne re-rastérise qu’en zoom avant franc, jamais en dézoom', () => {
  assert.equal(doitRerasteriser({ echelleRendue: 1, echelleVoulue: 2 }), true)
  assert.equal(doitRerasteriser({ echelleRendue: 1, echelleVoulue: 1.1 }), false)
  assert.equal(doitRerasteriser({ echelleRendue: 2, echelleVoulue: 1 }), false)
  assert.equal(doitRerasteriser({ echelleRendue: 0, echelleVoulue: 1 }), true)
})

test('un plan de 20 pages est listé sans en peindre AUCUNE', async () => {
  const doc = fauxDocument(20)
  const pages = listerPages(doc)
  assert.equal(pages.length, 20)
  assert.deepEqual(pages.slice(0, 3), [1, 2, 3])
  assert.equal(doc.peintes.length, 0)
})

test('seule la page sélectionnée est peinte (non-blocage de l’UI)', async () => {
  const doc = fauxDocument(20)
  const fond = await rasteriserPage(doc, { numeroPage: 7, echelle: 2, creerCanvas: fauxCanvas })
  assert.equal(doc.peintes.length, 1)
  assert.equal(doc.peintes[0].n, 7)
  assert.equal(fond.numeroPage, 7)
  assert.equal(fond.largeurPx, 1190)
})

test('la rotation 90° bascule les dimensions rendues', async () => {
  const doc = fauxDocument(3)
  const fond = await rasteriserPage(doc, {
    numeroPage: 1,
    rotation: 90,
    echelle: 1,
    creerCanvas: fauxCanvas,
  })
  assert.equal(fond.rotation, 90)
  assert.equal(fond.largeurPx, 842)
  assert.equal(fond.hauteurPx, 595)
})

test('un rendu annulé (démontage) ne rend rien', async () => {
  const doc = fauxDocument(3)
  const fond = await rasteriserPage(doc, {
    numeroPage: 1,
    echelle: 1,
    creerCanvas: fauxCanvas,
    signalAnnule: () => true,
  })
  assert.equal(fond, null)
})

test('ouvrirDocument refuse proprement un lecteur absent', async () => {
  await assert.rejects(() => ouvrirDocument(undefined, new Uint8Array()), /pas disponible/)
})

test('ouvrirDocument passe les octets au chargeur injecté', async () => {
  const octets = new Uint8Array([1, 2, 3])
  let vus = null
  const doc = await ouvrirDocument((params) => {
    vus = params.data
    return { promise: Promise.resolve(fauxDocument(2)) }
  }, octets)
  assert.equal(vus, octets)
  assert.equal(doc.numPages, 2)
})

test('libererFond détruit le document et vide le canvas (mémoire)', () => {
  const doc = fauxDocument(20)
  const canvas = fauxCanvas()
  canvas.width = 4000
  canvas.height = 3000
  libererFond({ doc, canvas })
  assert.equal(doc.detruit, true)
  assert.equal(canvas.width, 0)
  assert.equal(canvas.height, 0)
  // Idempotent : un second démontage ne doit jamais jeter.
  assert.doesNotThrow(() => libererFond(null))
})
