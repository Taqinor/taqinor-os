import test from 'node:test'
import assert from 'node:assert/strict'

// Stub localStorage AVANT d'importer le module (il lit `window.localStorage`
// paresseusement, donc un stub posé ici suffit pour la branche stockage).
function installLocalStorage() {
  const map = new Map()
  globalThis.window = {
    localStorage: {
      getItem: (k) => (map.has(k) ? map.get(k) : null),
      setItem: (k, v) => map.set(k, String(v)),
      removeItem: (k) => map.delete(k),
      clear: () => map.clear(),
    },
  }
  return () => map.clear()
}
const clear = installLocalStorage()

const {
  NAV_ACTIONS, filterActions, CREATE_ACTIONS, filterCreateActions,
  filterContextActions, readRecentEntities, pushRecentEntity, TACHES_ACTIONS, filterTachesActions,
} = await import('./commandActions.js')

test('NAV_ACTIONS: dérivées des raccourcis, bien formées (label + route + puce)', () => {
  assert.ok(NAV_ACTIONS.length >= 4)
  for (const a of NAV_ACTIONS) {
    assert.ok(a.label && a.label.length > 0)
    assert.ok(a.to.startsWith('/'))
    assert.match(a.keys, /^g [a-z]$/) // puce de raccourci « g x »
    assert.ok(a.id && a.id.length > 0)
  }
  // pas d'id en double
  const ids = NAV_ACTIONS.map((a) => a.id)
  assert.equal(new Set(ids).size, ids.length)
})

test('filterActions: requête vide → toutes ; filtre par libellé et par puce', () => {
  assert.equal(filterActions('').length, NAV_ACTIONS.length)
  assert.equal(filterActions('   ').length, NAV_ACTIONS.length)
  // par libellé
  const devis = filterActions('devis')
  assert.ok(devis.length >= 1)
  assert.ok(devis.every((a) => a.label.toLowerCase().includes('devis')))
  // par puce de raccourci (« g d »)
  const byKey = filterActions('g d')
  assert.ok(byKey.some((a) => a.keys === 'g d'))
  // insensible à la casse
  assert.deepEqual(filterActions('DEVIS'), filterActions('devis'))
  // sans correspondance → vide
  assert.equal(filterActions('zzz-introuvable').length, 0)
})

test('VX220(b) : CREATE_ACTIONS dérivées de CREATE_SHORTCUTS, bien formées', () => {
  assert.ok(CREATE_ACTIONS.length >= 3)
  for (const a of CREATE_ACTIONS) {
    assert.ok(a.label && a.label.length > 0)
    assert.ok(a.to.startsWith('/'))
    assert.match(a.keys, /^c [a-z]$/) // puce de raccourci « c x »
    assert.ok(a.id && a.id.length > 0)
  }
  // jamais mélangées à NAV_ACTIONS (section « Créer » distincte de « Actions »)
  const navKeys = new Set(NAV_ACTIONS.map((a) => a.keys))
  for (const a of CREATE_ACTIONS) assert.ok(!navKeys.has(a.keys))
})

test('VX220(b) : filterCreateActions — requête vide → toutes ; filtre par libellé/puce', () => {
  assert.equal(filterCreateActions('').length, CREATE_ACTIONS.length)
  const lead = filterCreateActions('lead')
  assert.ok(lead.length >= 1)
  assert.ok(lead.every((a) => a.label.toLowerCase().includes('lead')))
  const byKey = filterCreateActions('c l')
  assert.ok(byKey.some((a) => a.keys === 'c l'))
  assert.equal(filterCreateActions('zzz-introuvable').length, 0)
})

test('pushRecentEntity: tête de liste, dédoublonnage type+id, troncature à 6', () => {
  clear()
  assert.deepEqual(readRecentEntities(), [])
  pushRecentEntity({ type: 'devis', id: 1, label: 'DV-001' })
  pushRecentEntity({ type: 'lead', id: 2, label: 'Ali' })
  let r = readRecentEntities()
  assert.equal(r.length, 2)
  assert.equal(r[0].type, 'lead') // dernier ajouté en tête
  // ré-ouvrir un devis déjà vu → remonte en tête sans doublon
  pushRecentEntity({ type: 'devis', id: 1, label: 'DV-001' })
  r = readRecentEntities()
  assert.equal(r.length, 2)
  assert.equal(r[0].type, 'devis')
  assert.equal(r[0].id, 1)
  // troncature à 6
  for (let i = 10; i < 20; i += 1) pushRecentEntity({ type: 'client', id: i, label: `C${i}` })
  assert.equal(readRecentEntities().length, 6)
})

test('pushRecentEntity: NTUX11 — chaque entrée porte un horodatage `ts` (Date.now())', () => {
  clear()
  const before = Date.now()
  pushRecentEntity({ type: 'client', id: 42, label: 'Alaoui' })
  const [entry] = readRecentEntities()
  assert.ok(typeof entry.ts === 'number')
  assert.ok(entry.ts >= before)
})

test('pushRecentEntity: entité invalide ignorée', () => {
  clear()
  pushRecentEntity(null)
  pushRecentEntity({ type: 'devis' }) // pas d'id
  pushRecentEntity({ id: 5 }) // pas de type
  assert.deepEqual(readRecentEntities(), [])
})

test('readRecentEntities: JSON corrompu toléré', () => {
  clear()
  globalThis.window.localStorage.setItem('taqinor.cmdk.recent', '{pas du json')
  assert.deepEqual(readRecentEntities(), [])
})

test('LW26 : filterContextActions — requête vide → toutes ; filtre par libellé seul (pas de puce)', () => {
  const actions = [
    { id: 'lw-archive', label: 'Archiver le lead' },
    { id: 'lw-convert', label: 'Convertir en client' },
    { id: 'lw-goto-toiture', label: 'Aller à : Toiture & site' },
  ]
  assert.equal(filterContextActions(actions, '').length, 3)
  assert.equal(filterContextActions(actions, '   ').length, 3)
  const toiture = filterContextActions(actions, 'toiture')
  assert.equal(toiture.length, 1)
  assert.equal(toiture[0].id, 'lw-goto-toiture')
  // insensible à la casse
  assert.deepEqual(filterContextActions(actions, 'ARCHIVER'), filterContextActions(actions, 'archiver'))
  assert.equal(filterContextActions(actions, 'zzz-introuvable').length, 0)
})

test('LW26 : filterContextActions — actions absentes/nulles → []', () => {
  assert.deepEqual(filterContextActions(null, 'x'), [])
  assert.deepEqual(filterContextActions(undefined, ''), [])
  assert.deepEqual(filterContextActions([], ''), [])
})

test('TCH119 : « g j » mène à Aujourd’hui des Tâches, « g t » reste au SAV', async () => {
  const { GOTO_SHORTCUTS } = await import('./shortcuts.js')
  const gj = NAV_ACTIONS.find((a) => a.keys === 'g j')
  assert.deepEqual(gj, { id: 'g-j', label: "Aujourd'hui", to: '/taches/aujourdhui', keys: 'g j' })
  assert.equal(NAV_ACTIONS.find((a) => a.keys === 'g t').to, '/sav')
  // une seule entrée par séquence (aucune collision avec le noyau)
  const sequences = GOTO_SHORTCUTS.map((s) => s.keys)
  assert.equal(new Set(sequences).size, sequences.length)
})

test('TCH119 : « c t » ouvre la saisie par événement, jamais une navigation de la palette', async () => {
  const { CREATE_SHORTCUTS } = await import('./shortcuts.js')
  const ct = CREATE_SHORTCUTS.find((s) => s.keys === 'c t')
  assert.deepEqual(ct, { keys: 'c t', event: 'taqinor:taches:saisir', label: 'Créer une tâche' })
  // filtrée de CREATE_ACTIONS (la palette ferait navigate(undefined)) ; les autres restent
  assert.equal(CREATE_ACTIONS.some((a) => a.keys === 'c t'), false)
  assert.equal(CREATE_ACTIONS.every((a) => typeof a.to === 'string'), true)
  assert.deepEqual(CREATE_ACTIONS.map((a) => a.keys), ['c l', 'c d', 'c c'])
})

test('Raccord F2 Tâches : la recherche en tête, puis Nouveau projet, Faire le bilan et les onglets (routes réelles)', () => {
  const vide = filterTachesActions('')
  assert.deepEqual(vide.map((a) => a.label), ['Chercher dans mes tâches', 'Nouveau projet', 'Faire le bilan', 'À trier', 'Projets', 'Agenda'])
  for (const a of vide) assert.ok(a.to.startsWith('/taches/'))
  assert.equal(new Set(TACHES_ACTIONS.map((a) => a.id)).size, TACHES_ACTIONS.length)
  const devis = filterTachesActions('devis Settat')
  assert.equal(devis[0].label, 'Chercher « devis Settat » dans mes tâches')
  assert.equal(devis[0].to, '/taches/recherche?q=devis%20Settat')
  assert.deepEqual(filterTachesActions('agen').map((a) => a.label), ['Chercher « agen » dans mes tâches', 'Agenda'])
})