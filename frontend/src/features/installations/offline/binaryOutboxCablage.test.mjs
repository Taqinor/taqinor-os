// EZ8 — câblage de la file binaire, vérifié à la source (node:test).
// Ce que le test de logique ne montre pas : UN SEUL outbox (jamais un 2ᵉ), le
// rejeu par l'endpoint multipart EXISTANT, la compression AVANT la file, la
// purge au logout, le badge unique, et le fichier réservé par NTMOB1 intact.
//
//   node --test src/features/installations/offline/binaryOutboxCablage.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const read = (p) => readFileSync(join(HERE, p), 'utf8')

const OUTBOX = read('outbox.js')
const FIELD = read('fieldOutbox.js')
const IDB = read('idbStore.js')
const HOOK = read('useFieldOutbox.js')
const BADGE = read('OfflineSyncIndicator.jsx')
const PANEL = read('../InterventionFieldExecution.jsx')

test('la file binaire vit dans l’outbox EXISTANT (jamais un 2ᵉ module)', () => {
  assert.match(OUTBOX, /export class BinaryOutbox/)
  assert.match(FIELD, /export const binaryOutbox = new BinaryOutbox\(/)
  // NTMOB1 réserve `src/lib/offlineOutbox.js` : EZ8 n'y touche pas.
  assert.equal(
    existsSync(join(HERE, '../../../lib/offlineOutbox.js')), false,
    'le fichier réservé par NTMOB1 ne doit pas être créé ici')
})

test('rejeu par l’endpoint multipart EXISTANT (aucun endpoint nouveau)', () => {
  const uploader = FIELD.slice(FIELD.indexOf('async function binaryUploader'),
    FIELD.indexOf('export const binaryOutbox'))
  assert.match(uploader, /installationsApi\.ajouterPhoto\(/)
  assert.equal(uploader.includes('api.post('), false)
})

test('ArrayBuffer, jamais Blob (IndexedDB Safari instable)', () => {
  assert.match(OUTBOX, /bytes instanceof ArrayBuffer/)
  assert.match(FIELD, /await blob\.arrayBuffer\(\)/)
  // …et la file binaire n'a PAS de repli localStorage (un buffer y mourrait).
  const bin = IDB.slice(IDB.indexOf('export function createBinaryOutboxStore'))
  assert.equal(bin.includes('localStorageAdapter'), false)
  assert.match(bin, /persistent: false/)
})

test('la photo est COMPRESSÉE avant d’entrer en file (VX77)', () => {
  // `filerPhoto` ne reçoit que `toSend`, le blob déjà compressé.
  assert.match(PANEL, /const toSend = await compressPhotoForUpload\(/)
  assert.match(PANEL, /filerPhoto\(toSend, \{ intervention: id, slot \}\)/)
  assert.equal(/filerPhoto\(file[,)]/.test(PANEL), false,
    'la photo brute (4-8 Mo) ne doit jamais être filée')
})

test('plus de « photo PERDUE » sur une coupure réseau', () => {
  assert.equal(PANEL.includes('Photo NON envoyée — réseau indisponible. Reprenez-la'), false)
  assert.match(PANEL, /Photo en file — envoi automatique au retour du réseau/)
  // Le message « reprenez-la » ne survit que pour un échec de MISE EN FILE.
  assert.match(PANEL, /réseau indisponible et mise en file impossible/)
})

test('quota : message clair, jamais un échec muet', () => {
  assert.match(OUTBOX, /export class OutboxQuotaError/)
  assert.match(OUTBOX, /navigator\.storage\.estimate/)
  assert.match(PANEL, /OutboxQuotaError \|\| e\?\.quota/)
})

test('UN badge, compteur exact (actions + photos) et honnêteté iOS', () => {
  assert.match(HOOK, /pendingPhotos/)
  assert.match(BADGE, /const enAttente = pending \+ pendingPhotos/)
  assert.match(BADGE, /photo\(s\) en attente d’envoi/)
  assert.match(BADGE, /Safari peut les effacer après ~7 jours/)
  // Le badge ne se tait plus tant qu'une photo attend.
  assert.match(BADGE, /pending === 0 && pendingPhotos === 0 && !hasFailed\) return null/)
})

test('purge à la déconnexion (patron LW45)', () => {
  assert.match(FIELD, /LOGOUT_EVENT = 'taqinor:auth-logout'/)
  assert.match(FIELD, /binaryOutbox\.clear\(\)/)
  assert.match(FIELD, /window\.addEventListener\(LOGOUT_EVENT, purgeOutboxes\)/)
})

test('retry automatique au retour du réseau (le hook flushe les DEUX files)', () => {
  assert.match(HOOK, /binaryOutbox\.flush\(\)/)
  // `queuePhoto` demande une Background Sync juste après l'enfilage.
  const queue = FIELD.slice(FIELD.indexOf('export async function queuePhoto'),
    FIELD.indexOf('export { OutboxQuotaError }'))
  assert.match(queue, /requestBackgroundSync\(\)/)
})
