import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// XSAL3 — verrouille le contrat de `getPrixApplicable` (URL + params). BLOQUÉ
// côté backend : XSAL1 (`ventes.ListePrix`/`LignePrixListe`/
// `Client.liste_prix`) et XSAL2 (`RegleListePrix`) sont TOUS DEUX encore
// `[ ]` dans docs/PLAN.md — ni le modèle, ni `prix_applicable()`, ni cet
// endpoint n'existent (grep confirmé : `ListePrix|RegleListePrix` absent de
// `apps/ventes/models.py`). Ce test verrouille uniquement le CLIENT (URL/
// params conventionnels prêts pour l'intégration DevisGenerator/ProduitPicker
// une fois XSAL1/XSAL2 livrés) — pas d'appel réseau, pas de mock du graphe
// ESM (le module importe `./axios` avec effets de bord), on relit la source.

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'ventesApi.js'), 'utf8')

test('getPrixApplicable -> GET /ventes/prix-applicable/ avec produit/client/quantite', () => {
  assert.match(src, /getPrixApplicable:[\s\S]*?api\.get\('\/ventes\/prix-applicable\/'/)
  assert.match(src, /getPrixApplicable:[\s\S]*?params:\s*\{\s*produit,\s*client,\s*quantite\s*\}/)
})

test('getPrixApplicable ne contient aucune logique de repli (juste un GET direct)', () => {
  // Garde adversariale : la fonction elle-même doit rester un pur passe-plat
  // réseau (un seul `api.get(...)`, pas de `||`/`??`/ternaire qui deviendrait
  // un fallback prix_vente local — ce calcul doit rester server-side).
  const match = src.match(/getPrixApplicable:[\s\S]*?params: \{ produit, client, quantite \} \}\),/)
  assert.ok(match, 'getPrixApplicable introuvable dans la source')
  assert.doesNotMatch(match[0], /\|\||\?\?|\?\s*.*:/)
})
