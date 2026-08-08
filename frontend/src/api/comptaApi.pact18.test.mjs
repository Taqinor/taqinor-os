import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, resolve } from 'node:path'

/* PACT18 — un seul caractère tuait l'onglet « Comptabilité → États →
   Grand-livre ».

   `comptaApi.js` appelait `/compta/etats/grand-livre/` avec un TIRET ; la route
   réelle est `/compta/etats/grand_livre/` avec un SOULIGNÉ, parce que
   `def grand_livre` (apps/compta/views.py) est la SEULE @action de
   `EtatsComptablesViewSet` à ne pas déclarer d'`url_path=` — ses voisines en
   déclarent une (`balance-referentiel`, `cockpit-cloture`…), elle non — et le
   `url_path` par défaut d'une @action DRF est le NOM DE LA MÉTHODE, souligné
   compris (`rest_framework/decorators.py` : `func.url_path = url_path if
   url_path else func.__name__`).

   POURQUOI CE TEST EXISTE ALORS QUE `check_api_contract.py` EXISTE (mesuré) :
   la garde de contrat NE COUVRE PAS ce sous-arbre. Vérifié en remplaçant le
   chemin par `/compta/etats/grand_livre_bidon/` — la garde reste VERTE. Un
   « nettoyage » qui ré-harmoniserait le tiret avec ses vingt voisines
   rouvrirait donc le trou sans que rien ne le dise. Ce test est le seul filet.

   Il relit les DEUX sources (client + serveur) : pas d'appel réseau, pas de
   mock du graphe ESM (`comptaApi.js` importe `./axios`, à effets de bord). */

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'comptaApi.js'), 'utf8')

function racineDepot() {
  let dossier = resolve(here)
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier
    dossier = dirname(dossier)
  }
  throw new Error(`Racine du dépôt introuvable depuis ${here}`)
}

const vuesCompta = readFileSync(
  join(racineDepot(), 'backend', 'django_core', 'apps', 'compta', 'views.py'),
  'utf8',
)

test('grandLivre appelle /compta/etats/grand_livre/ (SOULIGNÉ)', () => {
  assert.match(src, /grandLivre:[\s\S]{0,120}?api\.get\('\/compta\/etats\/grand_livre\/'/)
})

test('plus aucun appel /compta/etats/grand-livre/ (TIRET) dans le client', () => {
  assert.doesNotMatch(src, /['`]\/compta\/etats\/grand-livre\//)
})

test('le serveur sert bien le SOULIGNÉ : `def grand_livre` n\'a pas d\'url_path', () => {
  // Le décorateur qui précède immédiatement `def grand_livre` ne doit porter
  // AUCUN `url_path=`. S'il en gagne un un jour, ce test échoue et rappelle
  // qu'il faut changer le client DANS LA MÊME modification — c'est exactement
  // le lien front↔back qui manquait.
  const bloc = vuesCompta.match(/@action\([^)]*\)\s*\n\s*def grand_livre\b/)
  assert.ok(bloc, '`def grand_livre` introuvable dans apps/compta/views.py')
  assert.doesNotMatch(
    bloc[0], /url_path\s*=/,
    "apps/compta/views.py::grand_livre déclare désormais un `url_path=` : "
    + 'aligner `comptaApi.etats.grandLivre` sur ce chemin dans le même commit.',
  )
})
