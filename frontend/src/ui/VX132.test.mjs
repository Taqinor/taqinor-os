// VX132 — L'attente premium : shimmer, crossfade, squelettes honnêtes,
// anti-scintillement propagé, chargement long conscient. Vérification de
// SOURCE (pas de node_modules installés dans ce lane — cf. VX124/VX130) :
//   node --test src/ui/VX132.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SKELETON_SRC = readFileSync(join(HERE, 'Skeleton.jsx'), 'utf8')
const TOKENS_SRC = readFileSync(join(HERE, '..', 'design', 'tokens.css'), 'utf8')
const DATATABLE_SRC = readFileSync(join(HERE, 'datatable', 'DataTable.jsx'), 'utf8')
const DEVIS_LIST_SRC = readFileSync(join(HERE, '..', 'pages', 'ventes', 'DevisList.jsx'), 'utf8')
const FACTURE_LIST_SRC = readFileSync(join(HERE, '..', 'pages', 'ventes', 'FactureList.jsx'), 'utf8')

test('(a) Skeleton consomme .skeleton-shimmer (balayage directionnel, pas le pulse Tailwind)', () => {
  assert.match(SKELETON_SRC, /skeleton-shimmer/)
  assert.doesNotMatch(SKELETON_SRC, /animate-pulse/)
})

test('(a) tokens.css définit .skeleton-shimmer avec un dégradé + background-position', () => {
  assert.match(TOKENS_SRC, /\.skeleton-shimmer\s*\{[^}]*background-image:\s*linear-gradient/)
  assert.match(TOKENS_SRC, /@keyframes skeleton-shimmer\s*\{/)
  assert.match(TOKENS_SRC, /background-position:\s*200% 0/)
  assert.match(TOKENS_SRC, /background-position:\s*-200% 0/)
})

test('(c) DataTable dérive le nombre de lignes-squelettes de pageSize (borné à 12)', () => {
  assert.match(DATATABLE_SRC, /Math\.min\(pageSize \|\| 6,\s*12\)/)
  assert.doesNotMatch(DATATABLE_SRC, /Array\.from\(\{ length: 6 \}\)\.map/)
})

test('(e) DevisList/FactureList : les boutons PDF font tourner des libellés honnêtes pendant la génération', () => {
  assert.match(DEVIS_LIST_SRC, /useRotatingLabel/)
  assert.match(DEVIS_LIST_SRC, /PDF_GENERATION_LABELS/)
  assert.match(FACTURE_LIST_SRC, /useRotatingLabel/)
  assert.match(FACTURE_LIST_SRC, /FACTURE_PDF_GENERATION_LABELS/)
  // Au moins 2 libellés distincts par registre (le chemin PDF long doit en
  // faire défiler plusieurs, jamais un seul figé).
  const devisLabelsMatch = DEVIS_LIST_SRC.match(/const PDF_GENERATION_LABELS = \[([\s\S]*?)\]/)
  assert.ok(devisLabelsMatch, 'PDF_GENERATION_LABELS introuvable')
  const devisLabelCount = (devisLabelsMatch[1].match(/'[^']+'/g) || []).length
  assert.ok(devisLabelCount >= 2, `attendu ≥ 2 libellés, trouvé ${devisLabelCount}`)
})

test('(e) le moteur PDF premium n’est pas IMPORTÉ côté frontend (règle #4 — comments autorisés)', () => {
  // Les commentaires peuvent légitimement CITER `quote_engine` (rappel de la
  // règle #4) ; seul un import/appel réel serait une violation.
  assert.doesNotMatch(DEVIS_LIST_SRC, /from ['"].*quote_engine/)
  assert.doesNotMatch(FACTURE_LIST_SRC, /from ['"].*quote_engine/)
})
