// EZ15 — La FRONTIERE avec NTMOB30, verrouillee.
// ----------------------------------------------------------------------------
// EZ15 = dictee INLINE navigateur (Web Speech, zero backend) pour le BUREAU :
// composer du chatter lead, description de ticket SAV, motif de perte.
// NTMOB30 = enregistrement + transcription SERVEUR (Whisper) pour le TERRAIN
// (intervention, checklist de chantier). La regle qui les separe :
// JAMAIS DEUX BOUTONS MICRO SUR UN MEME CHAMP.
//
// TEST MANUEL DOCUMENTE (impossible a automatiser : il faut un vrai micro et
// une vraie voix) :
//   1. Chrome ou Edge, en HTTPS, ouvrir la fiche d'un lead -> onglet Historique.
//   2. Cliquer le micro a cote du champ de note, autoriser le micro.
//   3. Dire : « Le client rappelle demain. » puis « Il veut un devis batterie. »
//      -> les DEUX phrases s'ajoutent au champ, l'une apres l'autre.
//   4. Recliquer le micro : la dictee s'arrete et ne redemarre pas.
//   5. Le meme parcours dans Firefox : AUCUN bouton micro n'apparait.
//
//   node --test src/ui/DictationSurfaces.ez15.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = join(HERE, '..')
const lf = (s) => s.replace(/\r\n/g, '\n')
const lire = (p) => lf(readFileSync(join(SRC, p), 'utf8'))

const COMPOSANT = lire('ui/DictationButton.jsx')
const CHATTER = lire('features/crm/workspace/TimelineTab.jsx')
const TICKETS = lire('pages/sav/TicketsPage.jsx')
const PERDU = lire('pages/crm/leads/PerduPopover.jsx')

/** Tous les .jsx du front (hors tests). */
function fichiers(dir = SRC, acc = []) {
  for (const nom of readdirSync(dir)) {
    if (nom === 'node_modules') continue
    const p = join(dir, nom)
    if (statSync(p).isDirectory()) { fichiers(p, acc); continue }
    if (nom.endsWith('.jsx') && !nom.includes('.test.')) acc.push(p)
  }
  return acc
}

test('EZ15 : les TROIS surfaces BUREAU portent la dictee', () => {
  for (const [nom, src] of [['chatter lead', CHATTER], ['ticket SAV', TICKETS], ['motif de perte', PERDU]]) {
    assert.match(src, /<DictationButton\s/, `${nom} : bouton de dictee absent`)
    assert.match(src, /DICTATION_PRIVACY_FR/, `${nom} : HelpTip de confidentialite absent`)
  }
})

test('EZ15 : le TERRAIN (NTMOB30) n\'est PAS touche — jamais deux micros', () => {
  const terrain = /interventions?\/|installations\//i
  for (const p of fichiers()) {
    if (!terrain.test(p.replace(/\\/g, '/'))) continue
    assert.doesNotMatch(
      lf(readFileSync(p, 'utf8')),
      /DictationButton/,
      `surface TERRAIN equipee d'un micro EZ15 (elle appartient a NTMOB30) : ${p}`,
    )
  }
})

test('EZ15 : un seul bouton micro par champ (aucun doublon dans une surface)', () => {
  assert.equal((CHATTER.match(/<DictationButton\s/g) || []).length, 1)
  assert.equal((TICKETS.match(/<DictationButton\s/g) || []).length, 1)
  assert.equal((PERDU.match(/<DictationButton\s/g) || []).length, 1)
})

test('EZ15 : ZERO backend, ZERO cle — l\'API vient du navigateur', () => {
  assert.match(COMPOSANT, /win\.SpeechRecognition \|\| win\.webkitSpeechRecognition \|\| null/)
  const code = COMPOSANT.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  assert.doesNotMatch(code, /api\.|axios|fetch\(|API_KEY|whisper/i)
})

test('EZ15 : la detection est une CAPACITE, jamais un sniffing de user-agent', () => {
  // Un test de navigateur par nom se serait trompe au premier Safari qui
  // implemente l'API, et aurait masque le bouton pour rien.
  const code = COMPOSANT.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  assert.doesNotMatch(code, /userAgent|navigator\.vendor|isChrome|isSafari/)
  assert.match(COMPOSANT, /if \(!supporte\) return null/)
})

test('EZ15 : le texte ajoute, jamais ne REMPLACE ce qui est deja saisi', () => {
  assert.match(CHATTER, /note: composer\.note \? `\$\{composer\.note\} \$\{txt\}` : txt,/)
  assert.match(TICKETS, /fields\.description\s*\n?\s*\? `\$\{fields\.description\} \$\{txt\}` : txt/)
  assert.match(PERDU, /setMotif\(\(cur\) => \(cur \? `\$\{cur\} \$\{txt\}` : txt\)\)/)
})

test('EZ15 : le HelpTip de confidentialite ne ment pas et n\'est pas adouci', () => {
  assert.match(COMPOSANT, /export const DICTATION_PRIVACY_FR = /)
  assert.match(COMPOSANT, /l'audio est envoyé à Google/)
  assert.match(COMPOSANT, /Ce n'est pas une transcription locale/)
  assert.match(COMPOSANT, /HTTPS/)
  // UNE seule definition : impossible qu'une surface en affiche une version
  // plus douce que les autres.
  let occurrences = 0
  for (const p of fichiers()) {
    if (/DICTATION_PRIVACY_FR = /.test(lf(readFileSync(p, 'utf8')))) occurrences += 1
  }
  assert.equal(occurrences, 1)
})

test('EZ15 : la frontiere avec NTMOB30 est ECRITE dans le composant', () => {
  assert.match(COMPOSANT, /FRONTIÈRE NETTE avec NTMOB30/)
  assert.match(COMPOSANT, /JAMAIS DEUX BOUTONS MICRO SUR UN MÊME CHAMP/)
})
