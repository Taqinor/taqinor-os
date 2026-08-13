import { test } from 'node:test'
import assert from 'node:assert/strict'

// Verrouille le CONTRAT REST du chat : chaque méthode appelle l'URL réelle du
// backend (apps/chat). Ces chemins ont été reconciliés avec le backend — toute
// dérive (ex. retour à /chat/share-record/) casse ce test.
//
// On charge messagesApi avec un faux module ./axios via un loader minimal :
// import dynamique + remplacement du default. Comme node:test ne fait pas de
// mock de module ESM nativement ici, on teste plutôt les chaînes d'URL en
// reconstruisant les appels au travers d'un stub d'API injecté.

// Stub qui enregistre la dernière requête (method, url, params, data).
function makeStub() {
  const calls = []
  const rec = (method) => (url, a) => {
    // axios: get(url, {params}) ; post(url, data, {config}) ; delete(url)
    const entry = { method, url }
    if (method === 'get') entry.params = a?.params
    else if (method === 'post') entry.data = a
    calls.push(entry)
    return Promise.resolve({ data: {} })
  }
  return {
    get: rec('get'),
    post: rec('post'),
    patch: rec('patch'),
    delete: rec('delete'),
    _calls: calls,
  }
}

// Le module messagesApi importe `./axios` (effets de bord) : plutôt que de
// mocker ce graphe ESM, on relit la source et on vérifie les chaînes d'URL
// exactes — c'est le contrat qui doit rester verrouillé.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const src = readFileSync(join(here, 'messagesApi.js'), 'utf8')

test('listMessages liste via /chat/messages/?conversation=', () => {
  assert.match(src, /listMessages:[\s\S]*?api\.get\('\/chat\/messages\/'/)
  assert.match(src, /conversation: conversationId/)
})

test('unreadCount → /chat/conversations/unread/', () => {
  assert.match(src, /unreadCount:[\s\S]*?'\/chat\/conversations\/unread\/'/)
})

test('search → /chat/conversations/search/', () => {
  assert.match(src, /search:[\s\S]*?'\/chat\/conversations\/search\/'/)
})

test('toggleReaction → POST /chat/messages/<id>/react/', () => {
  assert.match(src, /toggleReaction:[\s\S]*?api\.post\(`\/chat\/messages\/\$\{messageId\}\/react\/`/)
})

test('unpinMessage → POST /chat/messages/<id>/unpin/', () => {
  assert.match(src, /unpinMessage:[\s\S]*?api\.post\(`\/chat\/messages\/\$\{messageId\}\/unpin\/`/)
})

test('listPinned → /chat/messages/?conversation=&pinned=1', () => {
  assert.match(src, /listPinned:[\s\S]*?api\.get\('\/chat\/messages\/'/)
  assert.match(src, /pinned: 1/)
})

test('uploadAttachment → POST /chat/messages/upload/', () => {
  assert.match(src, /uploadAttachment:[\s\S]*?api\.post\('\/chat\/messages\/upload\/'/)
})

test('getAttachment → /chat/messages/<m>/attachments/<a>/download/', () => {
  assert.match(src, /getAttachment:[\s\S]*?attachments\/\$\{attachmentId\}\/download\//)
})

test('shareRecord → POST /chat/messages/ (pas de route dédiée)', () => {
  assert.match(src, /shareRecord:[\s\S]*?api\.post\('\/chat\/messages\/'/)
  assert.doesNotMatch(src, /share-record/)
})

test('mute / members / leave gardent leurs chemins backend', () => {
  assert.match(src, /muteConversation:[\s\S]*?\/mute\/`/)
  assert.match(src, /addMembers:[\s\S]*?\/members\/`/)
  assert.match(src, /removeMember:[\s\S]*?\/members\/\$\{userId\}\/`/)
  assert.match(src, /leaveConversation:[\s\S]*?\/leave\/`/)
})

// ── WIR155/WIR157 — nouveaux endpoints (fils, rappels/favoris, programmés,
// réponses enregistrées, sondages, rétention/alias/export). ──
test('threads.reply / list / listFollowed → routes XKB24', () => {
  assert.match(src, /reply:[\s\S]*?api\.post\(`\/chat\/messages\/\$\{messageId\}\/reply\/`/)
  assert.match(src, /list:[\s\S]*?api\.get\(`\/chat\/messages\/\$\{messageId\}\/thread\/`/)
  assert.match(src, /listFollowed:[\s\S]*?'\/chat\/messages\/threads\/'/)
})

test('remindMe / toggleBookmark / listBookmarks → routes XKB27', () => {
  assert.match(src, /remindMe:[\s\S]*?\/remind-me\/`/)
  assert.match(src, /toggleBookmark:[\s\S]*?\/bookmark\/`/)
  assert.match(src, /listBookmarks:[\s\S]*?'\/chat\/messages\/bookmarks\/'/)
})

test('scheduled.create / cancel → /chat/scheduled-messages/', () => {
  assert.match(src, /scheduled:[\s\S]*?create:[\s\S]*?'\/chat\/scheduled-messages\/'/)
  assert.match(src, /cancel:[\s\S]*?\/chat\/scheduled-messages\/\$\{id\}\/`/)
})

test('canned.list / create / remove → /chat/canned-responses/', () => {
  assert.match(src, /canned:[\s\S]*?list:[\s\S]*?'\/chat\/canned-responses\/'/)
  assert.match(src, /canned:[\s\S]*?create:[\s\S]*?'\/chat\/canned-responses\/'/)
})

test('poll.create / vote / close / results → routes XKB30', () => {
  assert.match(src, /poll:[\s\S]*?create:[\s\S]*?'\/chat\/messages\/poll\/'/)
  assert.match(src, /vote:[\s\S]*?\/poll-vote\/`/)
  assert.match(src, /close:[\s\S]*?\/poll-close\/`/)
  assert.match(src, /results:[\s\S]*?\/poll-results\/`/)
})

test('retention.list / historique + setChannelAlias + exportConversation (WIR157)', () => {
  assert.match(src, /retention:[\s\S]*?'\/chat\/retention-policies\/'/)
  assert.match(src, /historique:[\s\S]*?'\/chat\/retention-policies\/historique\/'/)
  assert.match(src, /setChannelAlias:[\s\S]*?\/alias-email\/`/)
  assert.match(src, /exportConversation:[\s\S]*?\/export\/`/)
})

// Garde un usage du stub pour éviter un "unused" et documenter la forme.
test('stub d’API enregistre les appels (sanity)', () => {
  const stub = makeStub()
  stub.get('/x', { params: { a: 1 } })
  assert.equal(stub._calls[0].url, '/x')
  assert.deepEqual(stub._calls[0].params, { a: 1 })
})
