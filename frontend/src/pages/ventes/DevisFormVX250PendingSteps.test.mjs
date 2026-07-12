// VX250 — La fiche annonce son état et ses relations : « en attente de… » +
// compteurs cliquables. Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/ventes/DevisFormVX250PendingSteps.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const FORM_SRC = readFileSync(join(HERE, 'DevisForm.jsx'), 'utf8')
const LIST_SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')

test('DevisForm.jsx : PendingStepsIndicator — devis envoyé non signé affiche le bandeau, lecture PURE', () => {
  assert.match(FORM_SRC, /devis\.statut === 'envoye' && \(/)
  assert.match(FORM_SRC, /En attente de signature client/)
  // Jamais un dispatch/mutation dans ce bloc — lecture pure du statut déjà
  // chargé (règle #4 : la chaîne Devis/BonCommande/Facture reste 1:1).
  const start = FORM_SRC.indexOf("devis.statut === 'envoye' && (")
  const end = FORM_SRC.indexOf(')}', start)
  const block = FORM_SRC.slice(start, end)
  assert.doesNotMatch(block, /dispatch\(/)
  assert.doesNotMatch(block, /updateDevis/)
})

test('DevisForm.jsx : RelationCounters réutilise factures_liees/bon_commande_etat/chantier déjà chargés (ZÉRO appel réseau)', () => {
  assert.match(FORM_SRC, /import \{[\s\S]*RelationCounters[\s\S]*\} from '\.\.\/\.\.\/ui'/)
  assert.match(FORM_SRC, /count: devis\.factures_liees\?\.length \?\? 0/)
  assert.match(FORM_SRC, /count: devis\.bon_commande_etat \? 1 : 0/)
  assert.match(FORM_SRC, /count: devis\.chantier \? 1 : 0/)
})

test('DevisList.jsx : lit désormais ?q= au montage (le lien pré-filtré de RelationCounters/LIST_ROUTE fonctionne réellement)', () => {
  assert.match(LIST_SRC, /const \[query, setQuery\] = useState\(\(\) => searchParams\.get\('q'\) \?\? ''\)/)
})
