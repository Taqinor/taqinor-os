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
  readRecentEntities, pushRecentEntity,
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
