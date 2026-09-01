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
  funnelRank,
  isStageMoveAllowed,
  isStageMoveBackward,
  LEAD_SORTERS,
  TRI_OPTIONS,
  sortLeads,
} from './stages.js'

// ── Ordre fondateur 2026-09-01 — tri des leads ──────────────────────────────
// Défaut « recent » : le DERNIER lead arrivé en haut. Priorité et score
// deviennent des OPTIONS (avant : priorité haute imposée en tête de colonne).
const L = (id, date, priorite = 'normale', score = 0, stage = 'NEW') => ({
  id, date_creation: date, priorite, score, stage,
})

test('tri par défaut « recent » : le dernier lead arrivé en haut, priorité IGNORÉE', () => {
  const vieuxHaute = L(1, '2026-01-01T10:00:00Z', 'haute')
  const recentNormale = L(2, '2026-08-30T10:00:00Z', 'normale')
  const milieu = L(3, '2026-05-15T10:00:00Z', 'basse')
  const tries = sortLeads([vieuxHaute, milieu, recentNormale], 'recent')
  assert.deepEqual(tries.map((l) => l.id), [2, 3, 1])
  // Clé inconnue / absente → repli « recent », jamais un ordre surprise.
  assert.deepEqual(sortLeads([vieuxHaute, recentNormale], 'inconnu').map((l) => l.id), [2, 1])
})

test('tri « ancien » : inverse exact de « recent »', () => {
  const a = L(1, '2026-01-01T10:00:00Z')
  const b = L(2, '2026-08-30T10:00:00Z')
  assert.deepEqual(sortLeads([a, b], 'ancien').map((l) => l.id), [1, 2])
})

test('tri « priorite » : haute d’abord puis récent (l’ancien ordre kanban, devenu une OPTION)', () => {
  const hauteVieille = L(1, '2026-01-01T10:00:00Z', 'haute')
  const normaleRecente = L(2, '2026-08-30T10:00:00Z', 'normale')
  const hauteRecente = L(3, '2026-06-01T10:00:00Z', 'haute')
  const tries = sortLeads([normaleRecente, hauteVieille, hauteRecente], 'priorite')
  assert.deepEqual(tries.map((l) => l.id), [3, 1, 2])
})

test('tri « score » : chauds d’abord, récent à égalité', () => {
  const froid = L(1, '2026-08-30T10:00:00Z', 'normale', 10)
  const chaud = L(2, '2026-01-01T10:00:00Z', 'normale', 90)
  const chaudRecent = L(3, '2026-08-01T10:00:00Z', 'normale', 90)
  assert.deepEqual(
    sortLeads([froid, chaud, chaudRecent], 'score').map((l) => l.id), [3, 2, 1])
})

test('groupLeadsByStage : défaut « recent » DANS chaque colonne ; « priorite » disponible', () => {
  const leads = [
    L(1, '2026-01-01T10:00:00Z', 'haute', 0, 'NEW'),
    L(2, '2026-08-30T10:00:00Z', 'normale', 0, 'NEW'),
  ]
  const colNew = groupLeadsByStage(leads).find((c) => c.key === 'NEW')
  assert.deepEqual(colNew.leads.map((l) => l.id), [2, 1])
  const colNewPrio = groupLeadsByStage(leads, 'priorite').find((c) => c.key === 'NEW')
  assert.deepEqual(colNewPrio.leads.map((l) => l.id), [1, 2])
})

test('« tri » est un ORDRE, pas un filtre : défaut « recent », ignoré par filterLeads, options complètes', () => {
  assert.equal(EMPTY_FILTERS.tri, 'recent')
  assert.deepEqual(TRI_OPTIONS.map((o) => o.value), ['recent', 'ancien', 'priorite', 'score'])
  for (const { value } of TRI_OPTIONS) {
    assert.ok(LEAD_SORTERS[value], `comparateur manquant pour ${value}`)
  }
  const leads = [L(1, '2026-01-01T10:00:00Z'), L(2, '2026-08-30T10:00:00Z')]
  assert.equal(filterLeads(leads, { ...EMPTY_FILTERS, tri: 'ancien' }).length, 2)
})

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
  // Ordre fondateur 2026-09-01 : DÉFAUT « recent » — le dernier lead arrivé
  // en haut, la priorité ne force plus l'ordre (elle reste l'option 'priorite').
  assert.deepEqual(byKey.NEW.leads.map((l) => l.id), [1, 2])
  assert.equal(byKey.NEW.totalDevis, 10000)
  // Seul le devis le plus récent du lead compte (le serializer trie déjà).
  assert.equal(byKey.SIGNED.totalDevis, 2500.5)
  assert.equal(byKey.CONTACTED.count, 0)
})

test('groupLeadsByStage : un lead PERDU compte dans `count` mais JAMAIS dans totalDevis (mêmes chiffres que la tuile Pipeline)', () => {
  const leads = [
    { id: 1, stage: 'NEW', date_creation: '2026-06-01', devis: [{ total_ttc: '10000.00' }] },
    { id: 2, stage: 'NEW', perdu: true, date_creation: '2026-06-02', devis: [{ total_ttc: '5000.00' }] },
  ]
  const byKey = Object.fromEntries(groupLeadsByStage(leads).map((c) => [c.key, c]))
  assert.equal(byKey.NEW.count, 2)
  assert.equal(byKey.NEW.totalDevis, 10000)
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

test('WREF — la référence client du site retrouve le lead', () => {
  const leads = [
    { id: 1, stage: 'NEW', nom: 'Alaoui', client_ref: 'TQ-PKEA' },
    { id: 2, stage: 'NEW', nom: 'Bennani' },
  ]
  // Le code remis au client sur l'écran de succès du site (casse indifférente).
  assert.deepEqual(filterLeads(leads, { q: 'tq-pkea' }).map((l) => l.id), [1])
  assert.deepEqual(filterLeads(leads, { q: 'PKEA' }).map((l) => l.id), [1])
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

test('LB4 : funnelRank — COLD au rang -1 (parking, PAS le plus avancé), miroir apps/crm/services.py _rang_funnel', () => {
  assert.equal(funnelRank('COLD'), -1)
  assert.equal(funnelRank('NEW'), 0)
  assert.equal(funnelRank('CONTACTED'), 1)
  assert.equal(funnelRank('QUOTE_SENT'), 2)
  assert.equal(funnelRank('FOLLOW_UP'), 3)
  assert.equal(funnelRank('SIGNED'), 4)
  // COLD est bien SOUS toute étape active (y compris NEW, rang 0).
  assert.ok(funnelRank('COLD') < funnelRank('NEW'))
})

test('LB4 : isStageMoveAllowed — miroir byte-à-byte de _bulk_stage_allowed', () => {
  // même étape → non (rien à faire).
  assert.equal(isStageMoveAllowed('NEW', 'NEW'), false)
  assert.equal(isStageMoveAllowed('COLD', 'COLD'), false)
  // Froid → n'importe quelle étape active → oui (réactivation, bug #7).
  assert.equal(isStageMoveAllowed('COLD', 'NEW'), true)
  assert.equal(isStageMoveAllowed('COLD', 'CONTACTED'), true)
  assert.equal(isStageMoveAllowed('COLD', 'SIGNED'), true)
  // vers Froid → oui, mise au parking autorisée depuis n'importe où.
  assert.equal(isStageMoveAllowed('NEW', 'COLD'), true)
  assert.equal(isStageMoveAllowed('SIGNED', 'COLD'), true)
  // sinon → uniquement vers une étape PLUS avancée (jamais de recul).
  assert.equal(isStageMoveAllowed('NEW', 'CONTACTED'), true)
  assert.equal(isStageMoveAllowed('FOLLOW_UP', 'NEW'), false) // recul refusé
  assert.equal(isStageMoveAllowed('SIGNED', 'CONTACTED'), false) // recul refusé
  assert.equal(isStageMoveAllowed('QUOTE_SENT', 'FOLLOW_UP'), true)
})

test("ordre fondateur 2026-08-01 : isStageMoveBackward — « ce mouvement RECULE ? »", () => {
  // Question COMPLÉMENTAIRE, jamais un élargissement d'isStageMoveAllowed :
  // celui-ci reste le miroir byte-à-byte de _bulk_stage_allowed (le bulk
  // demeure en avant seulement).
  assert.equal(isStageMoveBackward('NEW', 'NEW'), false)
  assert.equal(isStageMoveBackward('FOLLOW_UP', 'NEW'), true)
  assert.equal(isStageMoveBackward('SIGNED', 'CONTACTED'), true)
  assert.equal(isStageMoveBackward('CONTACTED', 'QUOTE_SENT'), false)
  // COLD est HORS recul dans les DEUX sens : y aller est un parking, en venir
  // est une réactivation — isStageMoveAllowed les autorise déjà, ils n'ont
  // donc JAMAIS besoin d'une confirmation (c'est le piège du bug #7, où COLD
  // classé au rang le plus haut faisait passer COLD→actif pour un recul).
  assert.equal(isStageMoveBackward('SIGNED', 'COLD'), false)
  assert.equal(isStageMoveBackward('COLD', 'NEW'), false)
  assert.equal(isStageMoveBackward('COLD', 'SIGNED'), false)
})

test('ordre fondateur 2026-08-01 : les deux prédicats sont EXCLUSIFS et COUVRANTS', () => {
  // C'est l'invariant sur lequel reposent les trois surfaces (drag, sélecteur
  // de carte, liste) : « autorisé = avance OU recul-confirmé » ne peut laisser
  // aucun couple d'étapes sans réponse, ni en donner deux contradictoires.
  for (const a of PIPELINE_STAGES) {
    for (const b of PIPELINE_STAGES) {
      const avance = isStageMoveAllowed(a, b)
      const recule = isStageMoveBackward(a, b)
      assert.ok(!(avance && recule), `${a}→${b} classé dans les DEUX sens`)
      assert.equal(avance || recule, a !== b, `${a}→${b} sans réponse`)
    }
  }
})

test('LB24 : filterLeads — relance "aujourdhui" (tuile KPI « Dû aujourd\'hui »)', () => {
  const pad = (n) => String(n).padStart(2, '0')
  const local = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
  const past = new Date(); past.setDate(past.getDate() - 5)
  const todayD = new Date()
  const future = new Date(); future.setDate(future.getDate() + 2)
  const leads = [
    { id: 1, stage: 'NEW', nom: 'Retard', relance_date: local(past) },
    { id: 2, stage: 'NEW', nom: "Aujourd'hui", relance_date: local(todayD) },
    { id: 3, stage: 'NEW', nom: 'Demain', relance_date: local(future) },
    { id: 4, stage: 'NEW', nom: 'Sans' },
  ]
  assert.deepEqual(filterLeads(leads, { relance: 'aujourdhui' }).map((l) => l.id), [2])
})

test('LB24 : filterLeads — score "chaud" (tuile KPI « Chauds ») lit score_label du serializer', () => {
  const leads = [
    { id: 1, nom: 'A', score_label: 'Chaud' },
    { id: 2, nom: 'B', score_label: 'Tiède' },
    { id: 3, nom: 'C', score_label: 'Froid' },
    { id: 4, nom: 'D' }, // score_label absent → jamais « chaud »
  ]
  assert.deepEqual(filterLeads(leads, { score: 'chaud' }).map((l) => l.id), [1])
  assert.equal(filterLeads(leads, EMPTY_FILTERS).length, 4)
})

test('EMPTY_FILTERS : score (LB24) rejoint le trio existant, défaut vide', () => {
  assert.equal(EMPTY_FILTERS.score, '')
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
