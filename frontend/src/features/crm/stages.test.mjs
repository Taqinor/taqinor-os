// Tests du module canonique des étapes pipeline (vue kanban & co).
// Exécutés en CI : node --test src/features/crm/stages.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  PIPELINE_STAGES,
  STAGE_LABELS,
  STAGE_COLORS,
  groupLeadsByStage,
  filterLeads,
  isPerdu,
  tagList,
  latestDevisTotal,
  initials,
  EMPTY_FILTERS,
} from './stages.js'

test('les 6 étapes canoniques, dans l’ordre de l’entonnoir (STAGES.py)', () => {
  assert.deepEqual(PIPELINE_STAGES, [
    'NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD',
  ])
  assert.deepEqual(STAGE_LABELS, {
    NEW: 'Nouveau',
    CONTACTED: 'Contacté',
    QUOTE_SENT: 'Devis envoyé',
    FOLLOW_UP: 'Relance',
    SIGNED: 'Signé',
    COLD: 'Froid',
  })
  for (const key of PIPELINE_STAGES) {
    assert.ok(STAGE_COLORS[key], `couleur manquante pour ${key}`)
  }
})

test('groupLeadsByStage rend TOUJOURS 6 colonnes, même sans aucun lead', () => {
  const cols = groupLeadsByStage([])
  assert.equal(cols.length, 6)
  assert.deepEqual(cols.map((c) => c.key), PIPELINE_STAGES)
  for (const c of cols) {
    assert.deepEqual(c.leads, [])
    assert.equal(c.count, 0)
    assert.equal(c.totalDevis, 0)
  }
})

test('groupLeadsByStage répartit, compte et totalise les devis par colonne', () => {
  const leads = [
    { id: 1, stage: 'NEW', priorite: 'normale', date_creation: '2026-06-01', devis: [{ total_ttc: '10000.00' }] },
    { id: 2, stage: 'NEW', priorite: 'haute', date_creation: '2026-05-01', devis: [] },
    { id: 3, stage: 'SIGNED', priorite: 'basse', date_creation: '2026-06-02', devis: [{ total_ttc: '2500.50' }, { total_ttc: '999.00' }] },
  ]
  const cols = groupLeadsByStage(leads)
  const byKey = Object.fromEntries(cols.map((c) => [c.key, c]))
  assert.equal(byKey.NEW.count, 2)
  // Priorité haute en premier dans la colonne.
  assert.deepEqual(byKey.NEW.leads.map((l) => l.id), [2, 1])
  assert.equal(byKey.NEW.totalDevis, 10000)
  // Seul le devis le plus récent du lead compte (le serializer trie déjà).
  assert.equal(byKey.SIGNED.totalDevis, 2500.5)
  assert.equal(byKey.CONTACTED.count, 0)
})

test('perdu = drapeau booléen `perdu`, jamais le texte du motif ni une colonne', () => {
  assert.equal(isPerdu({ perdu: true }), true)
  assert.equal(isPerdu({ perdu: true, motif_perte: '' }), true) // perdu sans motif tapé
  assert.equal(isPerdu({ perdu: false, motif_perte: 'Trop cher' }), false) // motif résiduel ≠ perdu
  assert.equal(isPerdu({ motif_perte: 'Trop cher' }), false)
  assert.equal(isPerdu({ perdu: false }), false)
  assert.equal(isPerdu({}), false)
  // Un lead perdu garde son étape dans le regroupement.
  const cols = groupLeadsByStage([{ id: 9, stage: 'FOLLOW_UP', perdu: true }])
  assert.equal(cols.find((c) => c.key === 'FOLLOW_UP').count, 1)
})

test('filterLeads : texte libre, canal, responsable, priorité, tag', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'Alaoui', ville: 'Rabat', canal: 'site_web', owner_nom: 'meryem', priorite: 'haute', tags: 'VIP, 82-21' },
    { id: 2, stage: 'COLD', nom: 'Bennani', telephone: '0612345678', canal: 'telephone', owner_nom: 'demo_admin', priorite: 'normale', tags: '' },
  ]
  assert.deepEqual(filterLeads(leads, { q: 'rabat' }).map((l) => l.id), [1])
  assert.deepEqual(filterLeads(leads, { q: '06123' }).map((l) => l.id), [2])
  assert.deepEqual(filterLeads(leads, { canal: 'site_web' }).map((l) => l.id), [1])
  assert.deepEqual(filterLeads(leads, { owner: 'demo_admin' }).map((l) => l.id), [2])
  assert.deepEqual(filterLeads(leads, { priorite: 'haute' }).map((l) => l.id), [1])
  assert.deepEqual(filterLeads(leads, { tag: 'VIP' }).map((l) => l.id), [1])
  assert.equal(filterLeads(leads, EMPTY_FILTERS).length, 2)
})

test('VX224 : filterLeads — toggle « Mes leads » (mesLeads) scope à myUsername', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'Alaoui', owner_nom: 'meryem' },
    { id: 2, stage: 'NEW', nom: 'Bennani', owner_nom: 'demo_admin' },
  ]
  // mesLeads ON + myUsername fourni → scope à ce seul owner_nom.
  assert.deepEqual(
    filterLeads(leads, { mesLeads: true }, { myUsername: 'meryem' }).map((l) => l.id),
    [1],
  )
  // mesLeads ON mais SANS myUsername (repli) → aucun effet, jamais une liste
  // vidée par accident.
  assert.equal(filterLeads(leads, { mesLeads: true }).length, 2)
  // mesLeads OFF (défaut EMPTY_FILTERS) → aucun effet même avec myUsername.
  assert.equal(filterLeads(leads, EMPTY_FILTERS, { myUsername: 'meryem' }).length, 2)
  // `owner` (filtre manager, n'importe quel responsable) reste INDÉPENDANT de
  // mesLeads — les deux peuvent coexister sans collision.
  assert.deepEqual(
    filterLeads(leads, { owner: 'demo_admin', mesLeads: false }, { myUsername: 'meryem' })
      .map((l) => l.id),
    [2],
  )
})

test('filterLeads : inclure / exclure / seulement les perdus', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'A', perdu: true },
    // motif résiduel mais perdu=false → compte comme NON perdu désormais.
    { id: 2, stage: 'NEW', nom: 'B', motif_perte: 'Ancien motif' },
  ]
  assert.equal(filterLeads(leads, { perdus: 'avec' }).length, 2)
  assert.deepEqual(filterLeads(leads, { perdus: 'sans' }).map((l) => l.id), [2])
  assert.deepEqual(filterLeads(leads, { perdus: 'seuls' }).map((l) => l.id), [1])
})

test('filterLeads : recherche WhatsApp distinct du téléphone', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'A', telephone: '0611111111', whatsapp: '0622222222' },
    { id: 2, stage: 'NEW', nom: 'B', telephone: '0633333333' },
  ]
  // Un numéro WhatsApp trouve le lead même si telephone diffère.
  assert.deepEqual(filterLeads(leads, { q: '0622222222' }).map((l) => l.id), [1])
})

test('filterLeads : filtre par étape et par type d’installation', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'A', type_installation: 'agricole' },
    { id: 2, stage: 'SIGNED', nom: 'B', type_installation: 'residentiel' },
  ]
  assert.deepEqual(filterLeads(leads, { stage: 'SIGNED' }).map((l) => l.id), [2])
  assert.deepEqual(
    filterLeads(leads, { type_installation: 'agricole' }).map((l) => l.id), [1])
})

test('filterLeads : relances en retard et cette semaine', () => {
  const pad = (n) => String(n).padStart(2, '0')
  const local = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const past = new Date(); past.setDate(past.getDate() - 5)
  const todayD = new Date()
  const future = new Date(); future.setDate(future.getDate() + 60)
  const leads = [
    { id: 1, stage: 'NEW', nom: 'Retard', relance_date: local(past) },
    { id: 2, stage: 'NEW', nom: "Aujourd'hui", relance_date: local(todayD) },
    { id: 3, stage: 'NEW', nom: 'Loin', relance_date: local(future) },
    { id: 4, stage: 'NEW', nom: 'Sans' },
  ]
  assert.deepEqual(filterLeads(leads, { relance: 'retard' }).map((l) => l.id), [1])
  // « cette semaine » inclut aujourd'hui, exclut le passé et le lointain.
  const week = filterLeads(leads, { relance: 'semaine' }).map((l) => l.id)
  assert.ok(week.includes(2))
  assert.ok(!week.includes(1))
  assert.ok(!week.includes(3))
})

test('helpers de carte : tags, initiales, total du dernier devis', () => {
  assert.deepEqual(tagList({ tags: ' VIP , 82-21 ,, ' }), ['VIP', '82-21'])
  assert.deepEqual(tagList({}), [])
  assert.equal(initials('meryem'), 'ME')
  assert.equal(initials('Reda Kasri'), 'RK')
  assert.equal(initials(null), '')
  assert.equal(latestDevisTotal({ devis: [{ total_ttc: '1234.56' }] }), 1234.56)
  assert.equal(latestDevisTotal({ devis: [] }), 0)
  assert.equal(latestDevisTotal({}), 0)
})
