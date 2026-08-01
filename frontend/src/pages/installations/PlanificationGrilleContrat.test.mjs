// APX28 — contrat de la grille horaire, vérifié à la source (node:test).
// La géométrie et les conflits sont testés au rendu dans
// `PlanificationGrille.test.jsx` ; ici on verrouille les invariants que le plan
// impose et qu'un rendu ne montre pas : zéro écriture serveur NOUVELLE,
// confirmation avant d'écrire un créneau, mobile en lecture seule, et la page
// ne touche pas au scoping `[data-view]` d'APX3.
//
//   node --test src/pages/installations/PlanificationGrilleContrat.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'PlanificationPage.jsx'), 'utf8')
const API = readFileSync(join(HERE, '../../api/installationsApi.js'), 'utf8')

test('zéro écriture serveur nouvelle : le seul PATCH est updateIntervention', () => {
  const appels = [...SRC.matchAll(/installationsApi\.(\w+)\(/g)].map((m) => m[1])
  const ecritures = appels.filter((n) => !n.startsWith('get'))
  assert.deepEqual([...new Set(ecritures)].sort(),
    ['creerInterventionsStandard', 'updateIntervention'],
    'un appel d\'écriture inattendu est apparu dans la page')
  // …et cet endpoint existe déjà côté client (aucune route inventée).
  assert.match(API, /updateIntervention: \(id, data\) => api\.patch\(/)
})

test('un dépôt sur un créneau passe par une CONFIRMATION avant d\'écrire', () => {
  const dragEnd = SRC.slice(SRC.indexOf('const handleDragEnd'), SRC.indexOf('const confirmerDrop'))
  assert.match(dragEnd, /overId\.startsWith\('slot:'\)/)
  assert.match(dragEnd, /setPendingDrop\(/)
  assert.equal(dragEnd.includes('installationsApi.updateIntervention'), false,
    'le glisser écrit sans confirmation')
  assert.match(SRC, /<AlertDialogAction onClick=\{confirmerDrop\}>Confirmer<\/AlertDialogAction>/)
})

test('le créneau écrit une fenêtre XFSM5 — jamais une durée devinée', () => {
  assert.match(SRC, /export function payloadDeplacement\(toKey, jourCible, heure\)/)
  const payload = SRC.slice(SRC.indexOf('export function payloadDeplacement'),
    SRC.indexOf('// Chevauchements RÉELS'))
  assert.match(payload, /fenetre_debut: heureEnTime\(heure\)/)
  assert.match(payload, /fenetre_fin: heureEnTime\(heure \+ 1\)/)
  // Aucune durée/heure n'est écrite quand aucun créneau n'est visé.
  assert.match(payload, /heure != null/)
})

test('mobile = lecture seule (aucun glisser-déposer au pouce)', () => {
  assert.match(SRC, /const draggable = !isMobile/)
  assert.match(SRC, /Lecture seule sur mobile/)
})

test('la page ne touche pas au scoping [data-view] d\'APX3', () => {
  // `.lp-page` de cette page N'A PAS de `data-view` : c'est ce qui la protège
  // du resserrement de chrome des Leads. On ne lui en ajoute pas.
  const racine = SRC.slice(SRC.indexOf('export default function PlanificationPage'))
  assert.match(racine, /className="page lp-page"/)
  assert.equal(racine.includes('data-view'), false)
})

test('la bande « Sans créneau » existe et reste la cible « technicien seul »', () => {
  assert.match(SRC, /function BandeSansCreneau/)
  assert.match(SRC, /useDroppable\(\{ id: `col:\$\{techKey\}` \}\)/)
  assert.match(SRC, /useDroppable\(\{ id: `slot:\$\{techKey\}:\$\{heure\}` \}\)/)
  // La réaffectation technicien-seule (VX251) garde son undo 6 s.
  assert.match(SRC, /toastWithUndo\(\{/)
})
