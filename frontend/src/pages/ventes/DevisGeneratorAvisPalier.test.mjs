// QJR308 — L'avis du palier 5 kWc de `noticePalierKwc` (autoQuote.js) était
// bien branché aux DEUX points de PRÉ-navigation (DevisTab.jsx,
// LeadDevisPanel.jsx) mais PAS au troisième point d'entrée de
// `createAutoQuote` : `runAutoQuote` dans le générateur lui-même
// (`?lead=&auto=1` / prop `autoProp`). Le vendeur qui arrive par CE chemin
// voyait sa puissance snappée au palier de 5 kWc sans jamais lire pourquoi.
//
// Correctif : `runAutoQuote` calcule l'avis (MÊME fonction partagée, aucune
// seconde formulation) au moment RÉEL où le snap a lieu — juste avant l'appel
// à `createAutoQuote` — et le pose dans `warnings`, qui alimente le bloc
// d'avertissements non bloquants déjà rendu par l'écran (aucun second bloc
// créé pour l'occasion).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules pour son propre rendu React : la partie « source » de ce test
// lit donc le fichier en texte, même patron que DevisGeneratorOverrides.test.mjs
// / DevisTabKwcPalier.test.mjs. `solar.js`, lui, est un module PUR (aucun JSX,
// aucune dépendance React) : la partie « comportement » importe donc la VRAIE
// fonction `arrondirAuPasKwc`, pas une réplique qui pourrait diverger.
//
// Run : node --test src/pages/ventes/DevisGeneratorAvisPalier.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { arrondirAuPasKwc } from '../../features/ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')
const DEVIS_TAB = readFileSync(
  join(HERE, '..', '..', 'features', 'crm', 'workspace', 'DevisTab.jsx'), 'utf8')
const LEAD_PANEL = readFileSync(
  join(HERE, '..', 'crm', 'leads', 'LeadDevisPanel.jsx'), 'utf8')

test('QJR308 — DevisGenerator.jsx importe noticePalierKwc de autoQuote.js (jamais une notice recopiée)', () => {
  assert.match(
    DG,
    /import \{\s*\n\s*createAutoQuote, buildEtudePompage, LEAD_TYPE_TO_MODE,[\s\S]*?\n\s*noticePalierKwc,\s*\n\} from '\.\.\/\.\.\/features\/ventes\/autoQuote'/,
    'noticePalierKwc doit être importé depuis la même source unique que DevisTab.jsx / LeadDevisPanel.jsx',
  )
})

test('QJR308 — runAutoQuote calcule l’avis AU MOMENT du snap (avant l’appel réseau createAutoQuote), même précédence', () => {
  const idx = DG.indexOf('const runAutoQuote = async (lead, discountStr) => {')
  assert.ok(idx > -1, 'runAutoQuote introuvable')
  const idxCreate = DG.indexOf('const devisId = await createAutoQuote({', idx)
  assert.ok(idxCreate > -1 && idxCreate > idx)
  const bloc = DG.slice(idx, idxCreate)
  // Aucune cible n'est transmise à createAutoQuote depuis ce point d'entrée
  // (voir le corps de createAutoQuote plus bas) : la valeur réellement snappée
  // est donc `lead.taille_souhaitee_kwc`, exactement ce que l'avis doit lire.
  assert.match(bloc, /const avisPalier = noticePalierKwc\(lead\?\.taille_souhaitee_kwc\)/,
    'l’avis doit être dérivé de la même valeur que celle réellement snappée par createAutoQuote')
  assert.match(bloc, /setWarnings\(prev => \(\{ \.\.\.prev, avisPalier \}\)\)/,
    'l’avis doit rejoindre le bloc d’avertissements non bloquants existant, pas un second bloc')
})

test('QJR308 — l’avis est posé AVANT l’appel réseau, pas seulement en cas de succès/échec', () => {
  const idx = DG.indexOf('const runAutoQuote = async (lead, discountStr) => {')
  const idxTry = DG.indexOf('try {', idx)
  const idxSet = DG.indexOf('setWarnings(prev => ({ ...prev, avisPalier }))', idx)
  assert.ok(idxSet > -1 && idxSet < idxTry,
    'setWarnings(avisPalier) doit précéder le try/await de createAutoQuote — le snap ne dépend pas du réseau')
})

test('QJR308 — le bloc d’avertissements non bloquants existant rend toute valeur posée dans `warnings` (aucun second bloc créé)', () => {
  assert.match(
    DG,
    /\{Object\.values\(warnings\)\.filter\(Boolean\)\.length > 0 && \(/,
    'le générateur doit continuer à rendre `warnings` via le bloc générique existant',
  )
  assert.match(DG, /\{Object\.values\(warnings\)\.filter\(Boolean\)\.map\(\(w, i\) => \(/)
})

test('QJR308 — les deux points d’entrée existants (DevisTab, LeadDevisPanel) sont INCHANGÉS', () => {
  assert.match(DEVIS_TAB, /const noticeKwc = noticePalierKwc\(kwcASaisir\)/)
  assert.match(DEVIS_TAB, /data-testid="lw-devis-kwc-palier"/)
  assert.match(LEAD_PANEL, /const noticeKwc = noticePalierKwc\(kwcASaisir\)/)
})

test('QJR308 — rejoué avec la VRAIE arrondirAuPasKwc importée de solar.js : un lead dont la taille souhaitée franchit un palier déclenche l’avis, sinon aucun', () => {
  // Cas qui déclenche : 6,5 kWc franchit le palier de 5.
  const kwcDeclenche = 6.5
  assert.notEqual(arrondirAuPasKwc(kwcDeclenche), kwcDeclenche)
  // Cas qui ne déclenche rien : une valeur déjà alignée sur le palier.
  const kwcAligne = 5
  assert.equal(arrondirAuPasKwc(kwcAligne), kwcAligne)
})
