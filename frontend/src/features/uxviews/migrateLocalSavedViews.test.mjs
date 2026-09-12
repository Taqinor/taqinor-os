import test from 'node:test'
import assert from 'node:assert/strict'

// Stub localStorage AVANT d'importer le module (lu paresseusement via
// `window.localStorage`, même patron que providers/commandActions.test.mjs).
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
  return map
}
const store = installLocalStorage()

const { migrateLocalSavedViewsForEcran, localStorageKeyForEcran } =
  await import('./migrateLocalSavedViews.js')

test('localStorageKeyForEcran — miroir de la convention hooks/useSavedViews.js', () => {
  assert.equal(localStorageKeyForEcran('crm.leads'), 'taqinor.crm.leads.savedViews')
})

test('aucune vue locale : ne crée rien, pose le drapeau « migré »', async () => {
  store.clear()
  const create = async () => { throw new Error('ne doit jamais être appelé') }
  const res = await migrateLocalSavedViewsForEcran('crm.leads', { create })
  assert.equal(res.migrated, 0)
  assert.equal(store.get('taqinor.uxviews.migrated.crm.leads'), '1')
})

test('migre chaque vue locale vers l’API (config = state brut), pose le drapeau si tout a réussi', async () => {
  store.clear()
  store.set('taqinor.crm.leads.savedViews', JSON.stringify([
    { name: 'Chauds cette semaine', state: { stage: 'CONTACTED' } },
    { name: 'À relancer', state: { relance: 'retard' } },
  ]))
  const created = []
  const create = async (payload) => { created.push(payload); return { data: { id: created.length } } }
  const res = await migrateLocalSavedViewsForEcran('crm.leads', { create })
  assert.equal(res.migrated, 2)
  assert.equal(res.total, 2)
  assert.deepEqual(created, [
    { ecran: 'crm.leads', nom: 'Chauds cette semaine', configuration: { stage: 'CONTACTED' } },
    { ecran: 'crm.leads', nom: 'À relancer', configuration: { relance: 'retard' } },
  ])
  assert.equal(store.get('taqinor.uxviews.migrated.crm.leads'), '1')
})

test('déjà migré (drapeau posé) : ne rejoue jamais, aucun appel réseau', async () => {
  store.clear()
  store.set('taqinor.uxviews.migrated.crm.leads', '1')
  store.set('taqinor.crm.leads.savedViews', JSON.stringify([{ name: 'X', state: {} }]))
  let calls = 0
  const create = async () => { calls += 1; return {} }
  const res = await migrateLocalSavedViewsForEcran('crm.leads', { create })
  assert.equal(res.skipped, true)
  assert.equal(calls, 0)
})

test('échec partiel (une vue en erreur) : ne pose PAS le drapeau, les autres sont quand même migrées', async () => {
  store.clear()
  store.set('taqinor.crm.leads.savedViews', JSON.stringify([
    { name: 'OK', state: {} },
    { name: 'KO', state: {} },
  ]))
  const create = async (payload) => {
    if (payload.nom === 'KO') throw new Error('réseau')
    return { data: { id: 1 } }
  }
  const res = await migrateLocalSavedViewsForEcran('crm.leads', { create })
  assert.equal(res.migrated, 1)
  assert.equal(res.total, 2)
  assert.equal(store.get('taqinor.uxviews.migrated.crm.leads'), undefined)
})

test('vue locale sans `name` : ignorée silencieusement (jamais un crash)', async () => {
  store.clear()
  store.set('taqinor.crm.leads.savedViews', JSON.stringify([{ state: {} }, { name: 'Vraie', state: {} }]))
  const created = []
  const create = async (payload) => { created.push(payload); return {} }
  const res = await migrateLocalSavedViewsForEcran('crm.leads', { create })
  assert.equal(created.length, 1)
  assert.equal(res.migrated, 1)
  assert.equal(res.total, 2)
})

test('écran vide/absent : no-op, jamais un crash', async () => {
  store.clear()
  const res = await migrateLocalSavedViewsForEcran('', { create: async () => {} })
  assert.equal(res.skipped, true)
  assert.equal(res.migrated, 0)
})
