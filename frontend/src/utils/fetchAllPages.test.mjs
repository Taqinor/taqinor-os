// VX54 — tests purs de fetchAllPages : le payload final doit être le total
// d'une réponse DRF multi-pages, les pages 2..N doivent partir SANS
// s'attendre les unes les autres (parallèle, pas un escalier sériel), et la
// concurrence doit rester bornée (critique pour les DEVIS — QPERF1 N+1).
// Run: node --test src/utils/fetchAllPages.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import http from 'node:http'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { fetchAllPages, lireToutesLesPages } from './fetchAllPages.js'

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

// ── PERF-CRM (2026-09-01) — flux progressif `onPage` ────────────────────────
// La 1re page doit être signalée DÈS son arrivée (premier rendu immédiat),
// chaque page suivante à sa réception, et le retour final reste inchangé.
test('onPage : la page 1 est signalée AVANT la fin, puis chaque page ; retour final inchangé', async () => {
  const chunks = []
  let resolved = false
  const fetchPage = makeApi(250, 100)
  const promise = fetchAllPages(fetchPage, {
    concurrency: 2,
    onPage: (results, meta) => {
      chunks.push({ n: results.length, page: meta.page, first: meta.first, resolved })
    },
  }).then((all) => { resolved = true; return all })
  const all = await promise
  assert.equal(all.length, 250)
  // 3 pages signalées, la première marquée `first`, AVANT la résolution finale.
  assert.equal(chunks.length, 3)
  assert.deepEqual(chunks[0], { n: 100, page: 1, first: true, resolved: false })
  assert.ok(chunks.every((c) => c.resolved === false))
  assert.equal(chunks.filter((c) => c.first).length, 1)
  // Total signalé == total rendu (aucune page perdue ni doublée).
  assert.equal(chunks.reduce((s, c) => s + c.n, 0), 250)
})

test('onPage : chemin SANS count (découverte via next) signale aussi chaque page', async () => {
  const pages = [
    { results: [{ id: 1 }], next: 'x' },
    { results: [{ id: 2 }], next: 'x' },
    { results: [{ id: 3 }], next: null },
  ]
  const chunks = []
  const all = await fetchAllPages(async (p) => pages[p - 1], {
    concurrency: 2,
    onPage: (results, meta) => chunks.push([meta.page, results[0].id, meta.first]),
  })
  assert.equal(all.length, 3)
  assert.deepEqual(chunks[0], [1, 1, true])
  assert.equal(chunks.length, 3)
})

test('onPage absent : comportement byte-identique (aucune dépendance au callback)', async () => {
  const all = await fetchAllPages(makeApi(120, 50), { concurrency: 3 })
  assert.equal(all.length, 120)
})

test('lireToutesLesPages : tableau complet, paramètres page/page_size transmis au wrapper', async () => {
  const appels = []
  const api = makeApi(250, 100)
  const all = await lireToutesLesPages((p) => {
    appels.push(p)
    return api(p.page).then((data) => ({ data }))
  })
  assert.equal(all.length, 250)
  assert.deepEqual(appels.map((p) => p.page).sort(), [1, 2, 3])
  assert.ok(appels.every((p) => 'page_size' in p))
})

// APRF25 (C-APRF-030) — taille de page des lectures complètes : le Dashboard sur
// un faux serveur HTTP qui applique la pagination DRF RÉELLE (50 par défaut,
// plafond 200 — core/pagination.py) émet au plus 60 requêtes (au lieu de 210)
// sans perdre une ligne, parce que chaque slice transmet le `page_size` que
// `fetchAllPages` (APRF26) lui fournit.
// Test-du-test : retirer `page_size` d'un slice ⇒ le contrôle de source échoue ET,
// rejoué à 50 par page, le compte dépasse 60.
const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const PAGE_DEFAUT = 50
const PAGE_MAX = 200

// Faux serveur : 7 collections, pagination DRF (page_size borné à 200, défaut 50).
function demarrerServeur(tailles) {
  const requetes = []
  const serveur = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://x')
    const nom = url.pathname.slice(1)
    const page = Number(url.searchParams.get('page') || 1)
    const demande = Number(url.searchParams.get('page_size') || PAGE_DEFAUT)
    const taille = Math.min(demande, PAGE_MAX)
    requetes.push({ nom, page, taille })
    const total = tailles[nom]
    const debut = (page - 1) * taille
    const n = Math.max(0, Math.min(taille, total - debut))
    res.setHeader('content-type', 'application/json')
    res.end(JSON.stringify({
      count: total,
      next: debut + n < total ? 'x' : null,
      results: Array.from({ length: n }, (_, i) => ({ id: debut + i + 1 })),
    }))
  })
  return new Promise((resolve) => {
    serveur.listen(0, '127.0.0.1', () => resolve({
      requetes,
      base: `http://127.0.0.1:${serveur.address().port}`,
      fermer: () => new Promise((r) => { serveur.close(r) }),
    }))
  })
}

const TAILLES = {
  produits: 2000, clients: 2000, devis: 2000, factures: 2000, leads: 2000, installations: 1000, tickets: 1000,
}

// Les sept lectures du Dashboard, écrites comme les slices : `(page, { page_size })`
// transmis à la requête (`avecTaille=false` rejoue l'ancien comportement).
function lectures(base, avecTaille) {
  const lire = (nom) => fetchAllPages(
    async (page, { page_size: pageSize } = {}) => {
      const q = new URLSearchParams({ page: String(page) })
      if (avecTaille) q.set('page_size', String(pageSize))
      return (await fetch(`${base}/${nom}?${q}`)).json()
    },
    { concurrency: 20 },
  )
  return Promise.all(Object.keys(TAILLES).map(lire))
}

test('Dashboard : au plus 60 requêtes pour 2 000/1 000 lignes, aucune ligne perdue', async () => {
  const srv = await demarrerServeur(TAILLES)
  try {
    const res = await lectures(srv.base, true)
    assert.ok(srv.requetes.length <= 60, `requêtes = ${srv.requetes.length}`)
    Object.keys(TAILLES).forEach((nom, i) => {
      assert.equal(res[i].length, TAILLES[nom], nom)
      assert.deepEqual(res[i].map((r) => r.id), Array.from({ length: TAILLES[nom] }, (_, k) => k + 1))
    })
  } finally { await srv.fermer() }
})

test('sans page_size le serveur sert 50 par page : le compte dépasse 60 (garde du test)', async () => {
  const srv = await demarrerServeur(TAILLES)
  try {
    await lectures(srv.base, false)
    assert.ok(srv.requetes.length > 60, `requêtes = ${srv.requetes.length}`)
  } finally { await srv.fermer() }
})

// Les slices réels : chaque appel `fetchAllPages(` reçoit `page_size` de
// `fetchAllPages` et le met dans sa requête (retirer l'un d'eux fait échouer ce cas).
const SLICES = [
  'features/crm/store/crmSlice.js',
  'features/stock/store/stockSlice.js',
  'features/ventes/store/ventesSlice.js',
  'features/installations/store/installationsSlice.js',
  'features/sav/store/ticketsSlice.js',
  'features/sav/store/equipementsSlice.js',
]
const HORS_STORE = [
  'pages/ventes/DevisGenerator.jsx',
  'pages/ventes/FactureForm.jsx',
  'pages/ventes/Conception3DPage.jsx',
  'features/stock/StructureSelector.jsx',
  'features/portail/admin/ComptesPortailAdmin.jsx',
  'features/portail/admin/chargerToutesLesPages.js',
]

// Sépare les appels `fetchAllPages(` d'un source (corps jusqu'à la parenthèse fermante).
function appels(source) {
  const out = []
  let i = source.indexOf('fetchAllPages(')
  while (i !== -1) {
    let prof = 0
    let j = i + 'fetchAllPages'.length
    for (; j < source.length; j += 1) {
      if (source[j] === '(') prof += 1
      else if (source[j] === ')') { prof -= 1; if (prof === 0) break }
    }
    out.push(source.slice(i, j + 1))
    i = source.indexOf('fetchAllPages(', j)
  }
  return out
}

test('les slices et lectures hors store transmettent page_size à la requête', () => {
  const fautifs = []
  for (const f of [...SLICES, ...HORS_STORE]) {
    const source = readFileSync(path.join(SRC, f), 'utf8')
    const liste = appels(source)
    assert.ok(liste.length > 0, `${f} : aucun appel fetchAllPages`)
    for (const a of liste) {
      if (!/page_size/.test(a)) fautifs.push(`${f} : ${a.slice(0, 80).replace(/\s+/g, ' ')}`)
    }
  }
  assert.deepEqual(fautifs, [])
})
