// QJR245 — La notice de palier 5 kWc couvre les TROIS entrées d'`autoQuote`,
// pas une seule.
//
// AVANT ce correctif : `arrondirAuPasKwc` arrondit toujours au palier
// (doctrine conservée), mais la notice utilisateur n'existait qu'à UN
// endroit — `DevisTab.jsx` (calculée sur le kWc tapé dans CE seul panneau).
// L'arrondi de `lead.taille_souhaitee_kwc` (quand le champ est laissé vide)
// et le troisième point d'entrée de `createAutoQuote`
// (`LeadDevisPanel.jsx:187`) restaient silencieux.
//
// `autoQuote.js` importe `./store/ventesSlice` (Redux) et `ventesApi`
// (axios, effets de bord au chargement du module) : le fichier ENTIER n'est
// pas importable sous `node --test` sans node_modules complet (confirmé —
// résolution d'import sans extension, même contrainte que
// `useSizingMoteur.js`/`ventesApi.js` ailleurs dans ce dépôt). La fonction
// PURE visée par cette tâche (`noticePalierKwc`) est donc extraite de son
// texte RÉEL (jamais recopiée à la main) et EXÉCUTÉE avec la VRAIE
// `arrondirAuPasKwc` importée de `solar.js` (module pur, sans ce problème).
//
// Run : node --test src/features/ventes/autoQuote.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { arrondirAuPasKwc } from './solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')
const LEAD_DEVIS_PANEL = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'LeadDevisPanel.jsx'), 'utf8')
const DEVIS_TAB = readFileSync(
  join(HERE, '..', 'crm', 'workspace', 'DevisTab.jsx'), 'utf8')

// Extrait le corps RÉEL de `noticePalierKwc` (jamais une copie) et l'exécute
// avec la VRAIE `arrondirAuPasKwc` — le seul nom libre que son corps référence.
function extraireNoticePalierKwc() {
  const m = SRC.match(/export function noticePalierKwc\(([^)]*)\)\s*\{([\s\S]*?)\n\}/)
  assert.ok(m, 'noticePalierKwc introuvable dans autoQuote.js')
  const [, params, corps] = m
  const fn = new Function(...params.split(',').map(p => p.trim()), 'arrondirAuPasKwc', corps)
  return (kwcSaisi) => fn(kwcSaisi, arrondirAuPasKwc)
}
const noticePalierKwc = extraireNoticePalierKwc()

// ── (exécuté) noticePalierKwc : le comportement RÉEL ────────────────────────

test('(exécuté) une saisie hors palier (6,5) produit la notice, nommant 5 kWc', () => {
  const notice = noticePalierKwc('6.5')
  assert.equal(typeof notice, 'string')
  assert.match(notice, /Palier appliqué : 5 kWc/)
  assert.match(notice, /saisie 6,5 kWc/, 'la virgule FR, jamais le point brut du champ number')
  assert.match(notice, /ne sort jamais hors palier de 5 kWc/)
})

test('(exécuté) une saisie DÉJÀ sur un palier ne produit aucune notice', () => {
  assert.equal(noticePalierKwc('5'), null)
  assert.equal(noticePalierKwc('10'), null)
  assert.equal(noticePalierKwc(20), null)
})

test('(exécuté) un autre palier que 5 (12 -> 10) : la notice généralise, pas un cas isolé', () => {
  const notice = noticePalierKwc('12')
  assert.match(notice, /Palier appliqué : 10 kWc/)
  assert.match(notice, /saisie 12 kWc/)
})

test('(exécuté) champ vide/nul/négatif/illisible : jamais de notice (comportement historique inchangé)', () => {
  for (const v of ['', null, undefined, 0, '0', -5, 'abc', NaN]) {
    assert.equal(noticePalierKwc(v), null, `valeur ${JSON.stringify(v)}`)
  }
})

test('(exécuté) le kWc nommé par la notice est EXACTEMENT celui que createAutoQuote appliquera (arrondirAuPasKwc réelle)', () => {
  // Aucune formule d'arrondi dupliquée : la notice retombe sur la même valeur
  // que la VRAIE arrondirAuPasKwc (solar.js) rendrait pour la même saisie.
  for (const saisie of [6.5, 8, 12, 22, 3]) {
    const notice = noticePalierKwc(saisie)
    const palierReel = arrondirAuPasKwc(saisie)
    if (palierReel === saisie) {
      assert.equal(notice, null, `saisie ${saisie} déjà un palier`)
    } else {
      assert.match(notice, new RegExp(`Palier appliqué : ${palierReel} kWc`), `saisie ${saisie}`)
    }
  }
})

// ── câblage : les TROIS points d'entrée, UNE seule formulation ──────────────

test('noticePalierKwc est exporté (les écrans doivent l’IMPORTER, jamais le recopier)', () => {
  assert.match(SRC, /export function noticePalierKwc\(/)
})

test('UNE SEULE définition du texte « Palier appliqué » — les trois écrans se contentent de {noticeKwc}', () => {
  // La formulation entière vit dans autoQuote.js, une fois — jamais recopiée
  // par un écran (DevisTab.jsx et LeadDevisPanel.jsx ne rendent que
  // {noticeKwc}, ils n'écrivent plus le texte eux-mêmes).
  const occurrencesAutoQuote = (SRC.match(/Palier appliqué :/g) || []).length
  assert.equal(occurrencesAutoQuote, 1, 'autoQuote.js doit porter EXACTEMENT une définition du texte')
  assert.doesNotMatch(DEVIS_TAB, /Palier appliqué :/,
    'DevisTab.jsx ne doit plus écrire le texte lui-même')
  assert.doesNotMatch(LEAD_DEVIS_PANEL, /Palier appliqué :/,
    'LeadDevisPanel.jsx ne doit plus écrire le texte lui-même')
})

test('LeadDevisPanel.jsx (3ᵉ entrée de createAutoQuote) importe et affiche noticePalierKwc — plus jamais silencieux', () => {
  assert.match(
    LEAD_DEVIS_PANEL,
    /import \{ createAutoQuote, noticePalierKwc \} from '\.\.\/\.\.\/\.\.\/features\/ventes\/autoQuote'/,
    'AVANT QJR245 : LeadDevisPanel.jsx importait createAutoQuote SEUL — aucune notice',
  )
  assert.match(LEAD_DEVIS_PANEL, /const noticeKwc = noticePalierKwc\(kwcASaisir\)/)
  assert.match(LEAD_DEVIS_PANEL, /data-testid="lw-devis-kwc-palier"/,
    'même data-testid que DevisTab.jsx (contrat DOM partagé)')
  assert.match(
    LEAD_DEVIS_PANEL,
    /<p className="gen-hint lw-devis-kwc-palier" data-testid="lw-devis-kwc-palier">\s*\n\s*\{noticeKwc\}\s*\n\s*<\/p>/,
    'le JSX doit rendre {noticeKwc} tel quel — jamais un texte recopié',
  )
})

test('LeadDevisPanel.jsx suit la MÊME précédence que createAutoQuote (targetKwc, sinon lead.taille_souhaitee_kwc)', () => {
  assert.match(
    LEAD_DEVIS_PANEL,
    /const kwcASaisir = parseFloat\(targetKwc\) > 0 \? targetKwc : lead\?\.taille_souhaitee_kwc/,
  )
})
