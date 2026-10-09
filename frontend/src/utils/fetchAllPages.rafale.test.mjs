// APRF26 (C-APRF-031) — rafale de lectures complètes : borne GLOBALE de 8 requêtes
// de liste en vol + reprise d'un 429/503 isolé. Faux serveur comportemental :
// compte les requêtes en vol, répond 503 au-delà de 30 simultanées et 503 UNE fois
// sur la page 3 d'une lecture.
// Run: node --test src/utils/fetchAllPages.rafale.test.mjs
// Test-du-test : retirer le sémaphore ⇒ pic ≫ 8 (le test échoue) ; retirer la
// reprise ⇒ le thunk est rejeté sur le 503 isolé (le test échoue).
import test from 'node:test'
import assert from 'node:assert/strict'

import { fetchAllPages } from './fetchAllPages.js'

const erreur503 = () => Object.assign(new Error('HTTP 503'), { response: { status: 503 } })

function fauxServeur({ lignes, taillePage, echecUneFoisPage = null, echecToujoursPage = null }) {
  const etat = { enVol: 0, pic: 0, deja503: new Set(), parPage: [] }
  const fetchPage = async (page, opts) => {
    etat.parPage.push(opts)
    etat.enVol += 1
    etat.pic = Math.max(etat.pic, etat.enVol)
    try {
      await new Promise((resolve) => { setTimeout(resolve, 2) })
      if (etat.enVol > 30) throw erreur503()
      if (page === echecToujoursPage) throw erreur503()
      if (page === echecUneFoisPage && !etat.deja503.has(page)) {
        etat.deja503.add(page)
        throw erreur503()
      }
      const debut = (page - 1) * taillePage
      const n = Math.max(0, Math.min(taillePage, lignes - debut))
      return {
        count: lignes,
        next: debut + n < lignes ? 'x' : null,
        results: Array.from({ length: n }, (_, i) => ({ id: debut + i + 1 })),
      }
    } finally {
      etat.enVol -= 1
    }
  }
  return { fetchPage, etat }
}

test('7 lectures complètes simultanées : pic en vol ≤ 8, 503 isolé repris, rien de perdu', async () => {
  const serveur = fauxServeur({ lignes: 2000, taillePage: 100, echecUneFoisPage: 3 })
  const onPages = Array.from({ length: 7 }, () => [])
  const resultats = await Promise.all(onPages.map((vus) => fetchAllPages(
    serveur.fetchPage,
    { retryDelayMs: 1, onPage: (_r, { page }) => vus.push(page) },
  )))
  assert.ok(serveur.etat.pic <= 8, `pic en vol = ${serveur.etat.pic}`)
  for (const res of resultats) {
    assert.equal(res.length, 2000)
    assert.deepEqual(res.map((r) => r.id), Array.from({ length: 2000 }, (_, i) => i + 1))
  }
  for (const vus of onPages) assert.equal(new Set(vus).size, 20) // onPage par page
})

test('la taille de page voulue est transmise en second argument (défaut 200)', async () => {
  const serveur = fauxServeur({ lignes: 30, taillePage: 10 })
  await fetchAllPages(serveur.fetchPage, { retryDelayMs: 1 })
  assert.deepEqual(serveur.etat.parPage[0], { page_size: 200 })
  const serveur2 = fauxServeur({ lignes: 30, taillePage: 10 })
  await fetchAllPages(serveur2.fetchPage, { retryDelayMs: 1, pageSize: 50 })
  assert.deepEqual(serveur2.etat.parPage[0], { page_size: 50 })
})

test('un 503 persistant (3 échecs) fait échouer le thunk avec l\'erreur d\'origine', async () => {
  const serveur = fauxServeur({ lignes: 500, taillePage: 100, echecToujoursPage: 3 })
  await assert.rejects(
    fetchAllPages(serveur.fetchPage, { retryDelayMs: 1 }),
    (err) => err.response?.status === 503,
  )
})

test('une erreur non transitoire (400) n\'est pas rejouée', async () => {
  let appels = 0
  const fetchPage = async () => {
    appels += 1
    throw Object.assign(new Error('HTTP 400'), { response: { status: 400 } })
  }
  await assert.rejects(fetchAllPages(fetchPage, { retryDelayMs: 1 }))
  assert.equal(appels, 1)
})
