// NTMOB27 — cache de LECTURE hors-ligne (logique pure, store injecté).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createReadCache, memoryStore, cleFiche, CAP_DEFAUT } from './readCache.js'

test('NTMOB27: relit une fiche déjà consultée, avec son horodatage', async () => {
  const cache = createReadCache({ store: memoryStore() })
  await cache.put('chantier', 12, { nom: 'Toit Bouskoura' }, 1_700_000_000_000)
  const entree = await cache.get('chantier', 12)
  assert.deepEqual(entree.data, { nom: 'Toit Bouskoura' })
  assert.equal(entree.cachedAt, 1_700_000_000_000)
})

test('NTMOB27: une fiche jamais consultée renvoie null (jamais une invention)', async () => {
  const cache = createReadCache({ store: memoryStore() })
  assert.equal(await cache.get('chantier', 999), null)
})

test('NTMOB27: le cap par défaut est de 30 fiches, éviction de la plus ancienne', async () => {
  assert.equal(CAP_DEFAUT, 30)
  const cache = createReadCache({ store: memoryStore(), cap: 3 })
  await cache.put('lead', 1, { n: 1 }, 1000)
  await cache.put('lead', 2, { n: 2 }, 2000)
  await cache.put('lead', 3, { n: 3 }, 3000)
  await cache.put('lead', 4, { n: 4 }, 4000)
  assert.equal(await cache.taille(), 3)
  assert.equal(await cache.get('lead', 1), null)   // la plus ancienne évincée
  assert.ok(await cache.get('lead', 4))
})

test('NTMOB27: les types de fiches ne se collisionnent pas', async () => {
  const cache = createReadCache({ store: memoryStore() })
  await cache.put('lead', 1, { quoi: 'lead' })
  await cache.put('devis', 1, { quoi: 'devis' })
  assert.equal((await cache.get('lead', 1)).data.quoi, 'lead')
  assert.equal((await cache.get('devis', 1)).data.quoi, 'devis')
  assert.equal(cleFiche('lead', 1), 'lead:1')
})

test('NTMOB27: un store indisponible ne fait jamais échouer l\'app', async () => {
  const casse = {
    async load() { throw new Error('quota') },
    async save() { throw new Error('quota') },
  }
  const cache = createReadCache({ store: casse })
  await assert.rejects(() => cache.put('lead', 1, { a: 1 }))
  // Les appelants entourent TOUJOURS le cache d'un `.catch` (cf. MaJourneePage) :
  // ce test documente que le module ne prétend pas avaler les erreurs du store.
})
