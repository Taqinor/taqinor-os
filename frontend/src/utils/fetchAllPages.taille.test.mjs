// APRF25 (C-APRF-030) — taille de page des lectures complètes : le Dashboard sur
// un faux serveur HTTP qui applique la pagination DRF RÉELLE (50 par défaut,
// plafond 200 — core/pagination.py) émet au plus 60 requêtes (au lieu de 210)
// sans perdre une ligne, parce que chaque slice transmet le `page_size` que
// `fetchAllPages` (APRF26) lui fournit.
// Run: node --test src/utils/fetchAllPages.taille.test.mjs
// Test-du-test : retirer `page_size` d'un slice ⇒ le contrôle de source échoue ET,
// rejoué à 50 par page, le compte dépasse 60.
import test from 'node:test'
import assert from 'node:assert/strict'
import http from 'node:http'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { fetchAllPages } from './fetchAllPages.js'

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
