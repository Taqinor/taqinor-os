// LB15 — PerduPopover : composant PARTAGÉ « Marquer perdu » (fin de la
// triplication byte-à-byte LeadCard/ListView). Contrat vérifié sur SOURCE
// (le composant importe react + ui → non rendu ici, no node_modules dans ce
// worktree/lane) :
//   - une seule requête via le callback stable onMarkPerdu(lead, motif) ;
//   - AUCUN crmApi.updateLead direct (seulement getMotifsPerte, paresseux) ;
//   - modes auto-déclenché (trigger) ET contrôlé (open/onOpenChange + anchor).
//   node --test src/pages/crm/leads/PerduPopover.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'PerduPopover.jsx'), 'utf8')

test('LB15 : PerduPopover exporte un composant par défaut', () => {
  assert.match(SRC, /export default function PerduPopover\(/)
})

test('LB15 : confirme via le callback stable onMarkPerdu(lead, motif) — jamais de crmApi.updateLead direct', () => {
  assert.match(SRC, /await onMarkPerdu\(lead, m\)/)
  // Aucune écriture directe : uniquement la LECTURE paresseuse des motifs.
  assert.doesNotMatch(SRC, /crmApi\.updateLead/)
  assert.doesNotMatch(SRC, /crmApi\.patchLead/)
})

test('LB15 : chargement PARESSEUX des motifs (à la 1re ouverture seulement)', () => {
  assert.match(SRC, /if \(!open \|\| motifs !== null\) return/)
  assert.match(SRC, /crmApi\.getMotifsPerte\(\)/)
  assert.match(SRC, /\.filter\(\(m\) => !m\.archived\)/)
})

test('LB15 : supporte le mode CONTRÔLÉ (open/onOpenChange) et le mode auto-déclenché (trigger/anchor)', () => {
  assert.match(SRC, /const controlled = openProp !== undefined/)
  assert.match(SRC, /trigger \? <PopoverTrigger asChild>\{trigger\}<\/PopoverTrigger> : null/)
  assert.match(SRC, /anchor \? <PopoverAnchor asChild>\{anchor\}<\/PopoverAnchor> : null/)
})

test('LB15 : réinitialise le champ motif à la fermeture', () => {
  assert.match(SRC, /if \(!v\) setMotif\(''\)/)
})
