// VX54 — tests purs de fetchAllPages : le payload final doit être le total
// d'une réponse DRF multi-pages, les pages 2..N doivent partir SANS
// s'attendre les unes les autres (parallèle, pas un escalier sériel), et la
// concurrence doit rester bornée (critique pour les DEVIS — QPERF1 N+1).
// Run: node --test src/utils/fetchAllPages.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { fetchAllPages } from './fetchAllPages.js'

function makeApi(totalItems, pageSize) {
  const pages = []
  for (let i = 0; i < totalItems; i += pageSize) {
    pages.push({
      results: Array.from({ length: Math.min(pageSize, totalItems - i) }, (_, j) => ({ id: i + j + 1 })),
      count: totalItems,
      next: i + pageSize < totalItems ? 'x' : null,
    })
  }
  return async (page) => pages[page - 1]
}

test('payload final = total d’une réponse multi-pages mockée', async () => {
  const fetchPage = makeApi(250, 100) // 3 pages : 100 + 100 + 50
  const all = await fetchAllPages(fetchPage, { concurrency: 20 })
  assert.equal(all.length, 250)
  assert.equal(all[0].id, 1)
  assert.equal(all[249].id, 250)
})

test('une seule page (pas de troncature à tort, pas d’appel superflu)', async () => {
  let calls = 0
  const fetchPage = async (page) => {
    calls += 1
    return { results: [{ id: 1 }, { id: 2 }], count: 2, next: null }
  }
  const all = await fetchAllPages(fetchPage, { concurrency: 20 })
  assert.equal(all.length, 2)
  assert.equal(calls, 1)
})

test('timing : les pages 2 et 3 partent sans s’attendre (parallèle, pas sériel)', async () => {
  const order = []
  const fetchPage = async (page) => {
    order.push(`start-${page}`)
    // Page 2 est délibérément plus lente que la page 3 : si l'appel était
    // sériel, "start-3" n'apparaîtrait qu'après "end-2". En parallèle,
    // "start-3" arrive avant "end-2".
    const delay = page === 2 ? 30 : 5
    await new Promise((resolve) => setTimeout(resolve, delay))
    order.push(`end-${page}`)
    return {
      results: [{ id: page }],
      count: 3,
      next: page < 3 ? 'x' : null,
    }
  }
  await fetchAllPages(fetchPage, { concurrency: 20 })
  const startThreeIdx = order.indexOf('start-3')
  const endTwoIdx = order.indexOf('end-2')
  assert.ok(startThreeIdx < endTwoIdx, `attendu start-3 avant end-2, ordre=${order}`)
})

test('la borne de concurrence est respectée (jamais plus de N requêtes en vol)', async () => {
  const concurrency = 5
  let inFlight = 0
  let maxInFlight = 0
  const totalPages = 23
  const fetchPage = async (page) => {
    inFlight += 1
    maxInFlight = Math.max(maxInFlight, inFlight)
    await new Promise((resolve) => setTimeout(resolve, 5))
    inFlight -= 1
    return {
      results: [{ id: page }],
      count: totalPages, // pageSize=1 côté page 1 → totalPages pages
      next: page < totalPages ? 'x' : null,
    }
  }
  await fetchAllPages(fetchPage, { concurrency })
  assert.ok(maxInFlight <= concurrency, `maxInFlight=${maxInFlight} dépasse la borne ${concurrency}`)
})

test('borne basse type DEVIS (≤5) — jamais plus de 5 requêtes en vol', async () => {
  const concurrency = 5
  let inFlight = 0
  let maxInFlight = 0
  const totalPages = 12
  const fetchPage = async (page) => {
    inFlight += 1
    maxInFlight = Math.max(maxInFlight, inFlight)
    await new Promise((resolve) => setTimeout(resolve, 3))
    inFlight -= 1
    return {
      results: [{ id: page }],
      count: totalPages,
      next: page < totalPages ? 'x' : null,
    }
  }
  const all = await fetchAllPages(fetchPage, { concurrency })
  assert.equal(all.length, totalPages)
  assert.ok(maxInFlight <= 5, `maxInFlight=${maxInFlight} dépasse 5`)
})

test('réponse non paginée (tableau brut) : renvoyée telle quelle', async () => {
  const fetchPage = async () => [{ id: 1 }, { id: 2 }]
  const all = await fetchAllPages(fetchPage, { concurrency: 20 })
  assert.deepEqual(all, [{ id: 1 }, { id: 2 }])
})

test('sans `count` mais avec `next` : suit next jusqu’au bout', async () => {
  const fetchPage = makeApi(45, 20) // 3 pages : 20 + 20 + 5, count présent malgré tout
  // On simule une API sans count pour exercer la branche `next`-only.
  const noCountApi = async (page) => {
    const data = await fetchPage(page)
    if (!data) return { results: [], count: undefined, next: null }
    return { results: data.results, count: undefined, next: data.next }
  }
  const all = await fetchAllPages(noCountApi, { concurrency: 20 })
  assert.equal(all.length, 45)
})
