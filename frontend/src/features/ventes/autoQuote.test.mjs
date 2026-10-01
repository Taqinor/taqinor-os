// QJR245 — La notice de palier 5 kWc couvrait les TROIS entrées d'`autoQuote`.
// QJR602 (D-QJR5-13, 30/09/2026) — plus aucun palier n'est appliqué à une
// taille explicite : il n'y a plus rien à annoncer. ERR-QJR576-602 : le stub
// `noticePalierKwc` (rendait toujours `null`, aucun importeur prod) est
// supprimé — son absence est gardée par quote/codeMortParcours.test.mjs.
//
// `autoQuote.js` importe `./store/ventesSlice` (Redux) et `ventesApi`
// (axios, effets de bord au chargement du module) : le fichier ENTIER n'est
// pas importable sous `node --test` sans node_modules complet — d'où une
// lecture de son texte.
//
// Run : node --test src/features/ventes/autoQuote.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'autoQuote.js'), 'utf8')
const LEAD_DEVIS_PANEL = readFileSync(
  join(HERE, '..', '..', 'pages', 'crm', 'leads', 'LeadDevisPanel.jsx'), 'utf8')
const DEVIS_TAB = readFileSync(
  join(HERE, '..', 'crm', 'workspace', 'DevisTab.jsx'), 'utf8')

test('QJR602 — plus aucun texte « Palier appliqué » dans autoQuote.js, DevisTab.jsx ni LeadDevisPanel.jsx', () => {
  assert.doesNotMatch(SRC, /Palier appliqué :/)
  assert.doesNotMatch(DEVIS_TAB, /Palier appliqué :/)
  assert.doesNotMatch(LEAD_DEVIS_PANEL, /Palier appliqué :/)
  assert.doesNotMatch(DEVIS_TAB, /noticePalierKwc/)
})

// QJR602 suivi (D-QJR5-13) — LeadDevisPanel.jsx n'affiche plus d'avis de
// palier (taille explicite respectée telle quelle) : ses deux tests sont
// retirés ; il ne doit toujours pas recopier le texte (test ci-dessus).
