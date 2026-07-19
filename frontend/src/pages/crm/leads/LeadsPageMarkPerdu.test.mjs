// LB5 — « ✗ Perdu » depuis une carte met l'UI à jour via le store (bug
// recon2-03 #3 : LeadCard.confirmPerdu appelait crmApi.updateLead en DIRECT,
// contournant Redux, puis `onChanged?.()` — une prop que ni KanbanView ni
// ForecastView ne passaient JAMAIS ; aucun polling n'existe (les commentaires
// qui l'affirmaient mentaient)). Verified against SOURCE (no node_modules in
// this worktree/lane).
//   node --test src/pages/crm/leads/LeadsPageMarkPerdu.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const PAGE_SRC = readFileSync(join(HERE, 'LeadsPage.jsx'), 'utf8')
const KANBAN_SRC = readFileSync(join(HERE, 'views/KanbanView.jsx'), 'utf8')
const CARD_SRC = readFileSync(join(HERE, 'views/LeadCard.jsx'), 'utf8')
const LIST_SRC = readFileSync(join(HERE, 'views/ListView.jsx'), 'utf8')
const FORECAST_SRC = readFileSync(join(HERE, 'views/ForecastView.jsx'), 'utf8')

test('LB5 : LeadsPage définit onMarkPerdu — dispatch updateLead, AUCUN refetch (I1)', () => {
  const start = PAGE_SRC.indexOf('const onMarkPerdu = useCallback((lead, motif) => (')
  assert.ok(start > 0, 'onMarkPerdu introuvable')
  const body = PAGE_SRC.slice(start, start + 500)
  assert.match(body, /dispatch\(updateLead\(\{ id: lead\.id, data: \{ perdu: true, motif_perte: motif \} \}\)\)/)
  assert.match(body, /\.unwrap\(\)/)
  assert.doesNotMatch(body, /refetch\(\)/)
})

test('LB5 : onMarkPerdu toaste ET relance l\'erreur en échec (I8 — jamais de catch silencieux)', () => {
  const start = PAGE_SRC.indexOf('const onMarkPerdu = useCallback((lead, motif) => (')
  const body = PAGE_SRC.slice(start, start + 500)
  assert.match(body, /toastError\(/)
  assert.match(body, /throw err/)
})

test('LB5 : viewProps transmet onMarkPerdu à toutes les vues', () => {
  // LB6 — viewProps est désormais useMemo (bug #4).
  const start = PAGE_SRC.indexOf('const viewProps = useMemo(() => ({')
  assert.ok(start > 0, 'viewProps introuvable')
  const block = PAGE_SRC.slice(start, start + 500)
  assert.match(block, /onMarkPerdu,/)
})

test('LB5 : KanbanView forwarde onMarkPerdu → DraggableCard → LeadCard (aucun rupture de chaîne)', () => {
  assert.match(KANBAN_SRC, /onMarkPerdu,?\s*\n\}\) \{/) // signature export default
  assert.match(KANBAN_SRC, /onMarkPerdu=\{onMarkPerdu\}/) // <DraggableCard onMarkPerdu={onMarkPerdu} />
})

test('LB5 : ForecastView forwarde AUSSI onMarkPerdu (bug-fix : ne passait déjà rien avant, évite une régression)', () => {
  assert.match(FORECAST_SRC, /onMarkPerdu/)
})

test('LB5 : LeadCard n\'appelle plus JAMAIS crmApi.updateLead en direct — passe par onMarkPerdu (prop)', () => {
  assert.doesNotMatch(CARD_SRC, /crmApi\.updateLead\(/)
  // LB15 — le flux « perdu » a été extrait dans PerduPopover (partagé). LeadCard
  // n'appelle plus onMarkPerdu directement : il le TRANSMET au composant partagé
  // (qui, lui, fait `await onMarkPerdu(lead, motif)` — jamais de crmApi direct).
  assert.match(CARD_SRC, /<PerduPopover[\s\S]{0,160}onMarkPerdu=\{onMarkPerdu\}/)
  // La prop fantôme `onChanged` n'est plus DÉCLARÉE (seul un commentaire
  // documente encore l'ancien bug) : elle n'apparaît plus dans la destructure
  // des props de LeadCard.
  const start = CARD_SRC.indexOf('function LeadCard({')
  const destructure = CARD_SRC.slice(start, CARD_SRC.indexOf('}) {', start))
  assert.doesNotMatch(destructure, /\bonChanged\b/)
})

test('LB5/LB21 : ListView délègue « Marquer perdu » au PerduPopover PARTAGÉ (une seule implémentation carte+liste)', () => {
  assert.doesNotMatch(LIST_SRC, /dispatch\(updateLead\(/)
  // LB21(fold) — plus AUCUNE plomberie locale : le composant partagé (LB15)
  // porte motifs lazy/busy/rejet, et n'appelle QUE onMarkPerdu(lead, motif).
  assert.match(LIST_SRC, /import PerduPopover from '\.\.\/PerduPopover'/)
  assert.match(LIST_SRC, /<PerduPopover[\s\S]{0,200}onMarkPerdu=\{onMarkPerdu\}/)
  assert.doesNotMatch(LIST_SRC, /const confirmPerdu = /)
})
