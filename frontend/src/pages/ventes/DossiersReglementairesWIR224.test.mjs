// WIR224 / FG273 — les alertes d'expiration du calendrier réglementaire
// n'étaient JAMAIS rendues : `GET /ventes/calendrier-reglementaire/` calculait
// tout (statut d'alerte + résumé), `getCalendrierReglementaire` était wrappé,
// et aucun écran ne l'appelait.
//
// Assertions au niveau SOURCE (pas de node_modules dans ce worktree) :
//   node --test src/pages/ventes/DossiersReglementairesWIR224.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DossiersReglementairesPage.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')
const VUE = readFileSync(join(
  HERE, '../../../../backend/django_core/apps/ventes/calendrier_view.py'), 'utf8')

test('WIR224 : l\'écran consomme enfin getCalendrierReglementaire', () => {
  assert.match(API, /getCalendrierReglementaire: \(params\) =>/)
  assert.match(SRC, /ventesApi\.getCalendrierReglementaire\(\)/)
})

test('WIR224 : les TROIS statuts du serveur sont rendus, avec leurs tons', () => {
  // Les clés sont EXACTEMENT celles que le serveur émet (`_alerte`).
  for (const cle of ['expire', 'imminent', 'a_venir']) {
    assert.match(VUE, new RegExp(`'${cle}'`), `le serveur doit émettre ${cle}`)
    assert.ok(SRC.includes(`cle: '${cle}'`), `l'écran doit rendre ${cle}`)
  }
  assert.match(SRC, /cle: 'expire', label: 'Expiré', tone: 'destructive'/)
  assert.match(SRC, /cle: 'imminent', label: 'Imminent', tone: 'warning'/)
})

test('WIR224 : le statut affiché vient du SERVEUR, jamais recalculé sur les dates', () => {
  // On lit `statut_alerte`/`jours_restants` tels quels ; aucun calcul de délai
  // côté écran (sinon l'écran et le serveur divergeraient sur `?seuil=`).
  assert.match(SRC, /e\.statut_alerte/)
  assert.match(SRC, /e\.jours_restants/)
  assert.doesNotMatch(SRC, /Date\.now\(\)/)
  assert.doesNotMatch(SRC, /new Date\(\)/)
})

test('WIR224 : cliquer un compteur RECHARGE du serveur avec ?statut=', () => {
  const idx = SRC.indexOf('const chargerCalendrier')
  assert.notEqual(idx, -1)
  const bloc = SRC.slice(idx, idx + 900)
  assert.match(bloc, /getCalendrierReglementaire\(statut \? \{ statut \} : undefined\)/)
  // Le filtre est SERVEUR : aucune réduction locale du tableau d'échéances.
  assert.doesNotMatch(SRC, /echeances\.filter\(/)
  // Re-cliquer le même compteur enlève le filtre.
  assert.match(SRC, /const suivant = calStatut === cle \? null : cle/)
})

test('WIR224 : le résumé NON filtré est conservé (compteurs jamais vidés)', () => {
  assert.match(SRC, /if \(!statut && r\.data\?\.resume\) setResume\(r\.data\.resume\)/)
})

test('WIR224 : les échéances sont rendues dans l\'ordre serveur (tri serveur)', () => {
  // Le serveur trie par date croissante ; l'écran ne re-trie pas.
  assert.match(VUE, /echeances\.sort\(key=lambda e: e\['date_echeance'\]\)/)
  assert.doesNotMatch(SRC, /\.sort\(/)
})

test('WIR224 : écran sain à vide et en erreur (jamais un tableau fantôme)', () => {
  assert.match(SRC, /Aucune échéance/)
  assert.match(SRC, /Le calendrier réglementaire n&apos;a pas pu être chargé\./)
})

test('WIR224 : le panneau est en TÊTE, avant le sélecteur de ressource', () => {
  const panneau = SRC.indexOf('data-testid="calendrier-reglementaire"')
  const segmented = SRC.indexOf('<Segmented')
  assert.notEqual(panneau, -1)
  assert.ok(panneau < segmented, 'le panneau doit précéder le Segmented')
})
