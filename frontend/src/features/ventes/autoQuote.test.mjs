// QJR245 — La notice de palier 5 kWc couvrait les TROIS entrées d'`autoQuote`.
// QJR602 (D-QJR5-13, 30/09/2026) — plus aucun palier n'est appliqué à une
// taille explicite : `noticePalierKwc` rend toujours `null` (gardée pour ses
// deux derniers appelants, LeadDevisPanel.jsx et DevisGenerator.jsx).
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
  const noms = params.split(',').map(p => p.trim()).filter(Boolean)
  const fn = new Function(...noms, 'arrondirAuPasKwc', corps)
  return (kwcSaisi) => fn(kwcSaisi, arrondirAuPasKwc)
}
const noticePalierKwc = extraireNoticePalierKwc()

// ── (exécuté) QJR602 (D-QJR5-13) : plus AUCUN palier sur une taille explicite ──
// `createAutoQuote` respecte la cible telle quelle (exécuté dans
// autoQuote.tailleExplicite.test.jsx) : la notice n'a plus rien à annoncer et
// rend `null` pour TOUTE saisie — y compris celles qu'elle annonçait avant.

test('(exécuté) QJR602 — aucune notice de palier, quelle que soit la saisie', () => {
  for (const v of ['6.5', '12', 7, 22, '5', '10', '', null, undefined, 0, -5, 'abc', NaN]) {
    assert.equal(noticePalierKwc(v), null, `valeur ${JSON.stringify(v)}`)
  }
})

test('QJR602 — plus aucun texte « Palier appliqué » dans autoQuote.js, DevisTab.jsx ni LeadDevisPanel.jsx', () => {
  assert.doesNotMatch(SRC, /Palier appliqué :/)
  assert.doesNotMatch(DEVIS_TAB, /Palier appliqué :/)
  assert.doesNotMatch(LEAD_DEVIS_PANEL, /Palier appliqué :/)
  assert.doesNotMatch(DEVIS_TAB, /noticePalierKwc/)
})

// QJR602 suivi (D-QJR5-13) — LeadDevisPanel.jsx n'affiche plus d'avis de
// palier (taille explicite respectée telle quelle) : ses deux tests sont
// retirés ; il ne doit toujours pas recopier le texte (test ci-dessus).
