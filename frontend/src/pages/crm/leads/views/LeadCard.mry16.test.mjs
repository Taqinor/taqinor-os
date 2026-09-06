// F5/MRY16 — badge « prochaine touche » (kanban/liste, `kb-card-touche-micro`).
// Avant F5, `heureToucheFr` ne rendait QUE l'heure Casablanca de
// `prochaine_touche_at`, même pour une touche plusieurs jours dans le passé
// ou le futur — un badge « 08:30 » sur une carte se lit comme « aujourd'hui,
// 08:30 » quel que soit le vrai jour visé. F5 ajoute le jour de semaine
// court (fr-FR) devant l'heure quand la touche N'EST PAS aujourd'hui
// (Casablanca) ; une touche du jour garde l'heure seule (le cas le plus
// fréquent, glyphe/format inchangés). Verified against SOURCE (no
// node_modules in this worktree/lane) : `heureToucheFr`/`estAujourdhuiCasa`
// sont des fonctions PURES (Date/Intl seulement, aucun import React) — leur
// code est extrait tel quel du fichier réel puis exécuté ici, pour prouver
// le CALCUL et pas seulement sa présence dans la source (patron renforcé par
// rapport à LeadCardFirstTouchTimer.test.mjs, qui ne fait que du pattern-
// matching).
//   node --test src/pages/crm/leads/views/LeadCard.mry16.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'LeadCard.jsx'), 'utf8')

// Extrait le code source ENTRE le début du premier nom et la fin du dernier
// (bornée à la première accolade fermante en tout début de ligne après
// l'ouverture du dernier — ni `estAujourdhuiCasa` ni `heureToucheFr` n'ouvrent
// de bloc `{` à l'indentation 0 avant leur propre fin, seulement des
// littéraux d'options Intl indentés en ligne), puis évalue les DEUX
// fonctions dans UNE SEULE portée : `heureToucheFr` appelle
// `estAujourdhuiCasa` en interne, les extraire séparément les isolerait
// chacune dans sa propre portée globale et casserait cet appel.
function extraireFonctions(...noms) {
  const debut = SRC.indexOf(`const ${noms[0]} = `)
  assert.notEqual(debut, -1, `const ${noms[0]} introuvable dans LeadCard.jsx`)
  const dernier = noms[noms.length - 1]
  const debutDernier = SRC.indexOf(`const ${dernier} = `, debut)
  assert.notEqual(debutDernier, -1, `const ${dernier} introuvable dans LeadCard.jsx`)
  const ouvrante = SRC.indexOf('{', debutDernier)
  const fermante = SRC.indexOf('\n}', ouvrante)
  assert.notEqual(fermante, -1, `fin de ${dernier} introuvable`)
  const code = SRC.slice(debut, fermante + 2)
  // Extraction volontaire (lane sans node_modules) pour exécuter ces
  // fonctions pures sans tirer tout le graphe React/JSX du composant.
  return new Function(`${code}\nreturn { ${noms.join(', ')} };`)()
}

const { estAujourdhuiCasa, heureToucheFr } = extraireFonctions('estAujourdhuiCasa', 'heureToucheFr')

test('F5 : le câblage source est bien présent (structure)', () => {
  assert.match(SRC, /const estAujourdhuiCasa = \(iso\) => \{/)
  assert.match(SRC, /if \(estAujourdhuiCasa\(iso\)\) return heure/)
  assert.match(SRC, /weekday: 'short', timeZone: 'Africa\/Casablanca'/)
  assert.match(SRC, /return `\$\{jourCourt\} \$\{heure\}`/)
})

test('F5 : heureToucheFr(null) reste null (aucune touche programmée)', () => {
  assert.equal(heureToucheFr(null), null)
  assert.equal(heureToucheFr(''), null)
})

test('F5 : heureToucheFr(iso invalide) reste null', () => {
  assert.equal(heureToucheFr('pas-une-date'), null)
  assert.equal(estAujourdhuiCasa('pas-une-date'), false)
})

test('F5 : une touche AUJOURD\'HUI (Casablanca) garde l\'heure SEULE', () => {
  // « maintenant » réel — toujours vrai « aujourd'hui », quel que soit le
  // jour où ce test tourne (zéro horloge simulée à entretenir).
  const maintenant = new Date()
  const touche = maintenant.toISOString()
  const heureAttendue = new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(maintenant)
  assert.equal(estAujourdhuiCasa(touche), true)
  assert.equal(heureToucheFr(touche), heureAttendue)
  // Jamais de jour de semaine mélangé à l'heure du jour même.
  assert.doesNotMatch(heureToucheFr(touche), /[a-zé]{3}\. \d/i)
})

test('F5 : une touche un AUTRE jour ajoute « jour court. HH:MM »', () => {
  // +3 jours : toujours un jour CALENDAIRE différent d'aujourd'hui en
  // Casablanca quel que soit l'instant réel d'exécution (large marge, pas de
  // cas limite de fuseau/minuit à gérer comme avec +1/-1 j).
  const dans3Jours = new Date(Date.now() + 3 * 24 * 3600 * 1000)
  const touche = dans3Jours.toISOString()
  assert.equal(estAujourdhuiCasa(touche), false)
  const heureAttendue = new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(dans3Jours)
  const jourAttendu = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'short', timeZone: 'Africa/Casablanca',
  }).format(dans3Jours)
  assert.equal(heureToucheFr(touche), `${jourAttendu} ${heureAttendue}`)
})

test('F5 : une touche il y a plusieurs jours (en retard) ajoute aussi le jour court', () => {
  const ilYA5Jours = new Date(Date.now() - 5 * 24 * 3600 * 1000)
  const touche = ilYA5Jours.toISOString()
  assert.equal(estAujourdhuiCasa(touche), false)
  const heureAttendue = new Intl.DateTimeFormat('fr-FR', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
  }).format(ilYA5Jours)
  const jourAttendu = new Intl.DateTimeFormat('fr-FR', {
    weekday: 'short', timeZone: 'Africa/Casablanca',
  }).format(ilYA5Jours)
  assert.equal(heureToucheFr(touche), `${jourAttendu} ${heureAttendue}`)
})
