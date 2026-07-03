import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// CH6 — verrouille le CONTRAT REST des endpoints de timeline étapes/gates
// consommés par la nouvelle page « Parcours du chantier » (remplace le simple
// sélecteur de statut). Chaque chemin existe côté backend
// (apps/installations/views/installation.py — CH2 `etapes`/`avancer-etape`,
// CH3 `recette`, CH4 `pack-remise`). On relit la source de l'API (le module
// importe `./axios`, effet de bord, donc on verrouille le contrat textuel
// plutôt que de mocker le graphe ESM — même méthode que le test WR10).

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'installationsApi.js'), 'utf8')

test('CH2 — getEtapesChantier → GET chantiers/<id>/etapes/', () => {
  assert.match(src, /getEtapesChantier:[\s\S]*?api\.get\(`\/installations\/chantiers\/\$\{id\}\/etapes\/`\)/)
})

test('CH2 — avancerEtape → POST chantiers/<id>/avancer-etape/ avec {etape}', () => {
  assert.match(src, /avancerEtape:[\s\S]*?api\.post\(`\/installations\/chantiers\/\$\{id\}\/avancer-etape\/`/)
  assert.match(src, /avancerEtape:[\s\S]*?cle \? \{ etape: cle \} : \{\}/)
})

test('CH3 — getRecette → GET chantiers/<id>/recette/', () => {
  assert.match(src, /getRecette:[\s\S]*?api\.get\(`\/installations\/chantiers\/\$\{id\}\/recette\/`\)/)
})

test('CH3 — ouvrirRecette → POST chantiers/<id>/recette/', () => {
  assert.match(src, /ouvrirRecette:[\s\S]*?api\.post\(`\/installations\/chantiers\/\$\{id\}\/recette\/`, \{\}\)/)
})

test('CH4 — getPackRemise → GET chantiers/<id>/pack-remise/', () => {
  assert.match(src, /getPackRemise:[\s\S]*?api\.get\(`\/installations\/chantiers\/\$\{id\}\/pack-remise\/`\)/)
})

test('CH4 — genererPackRemise → POST chantiers/<id>/pack-remise/', () => {
  assert.match(src, /genererPackRemise:[\s\S]*?api\.post\(`\/installations\/chantiers\/\$\{id\}\/pack-remise\/`, \{\}\)/)
})
