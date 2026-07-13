// VX215 — boucle de retour « pris en charge » : après « Contacter mon
// supérieur », le vendeur voit si sa demande a été VUE par le(s) supérieur(s)
// notifié(s) (backend minime `GET .../superior-contact-status/`, lecture
// seule, jamais le contenu des notifications d'autrui — seulement l'état
// `read` + qui a lu). Verified against SOURCE (no node_modules in this
// worktree/lane).
//   node --test src/pages/ventes/DevisListVX215SuperieurStatus.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisList.jsx'), 'utf8')
const API_SRC = readFileSync(join(HERE, '../../api/ventesApi.js'), 'utf8')

test('VX215 : ventesApi expose superiorContactStatus (GET, lecture seule)', () => {
  assert.match(
    API_SRC,
    /superiorContactStatus: \(id\) => api\.get\(`\/ventes\/devis\/\$\{id\}\/superior-contact-status\/`\)/)
})

test('VX215 : handleContacterSuperieur rafraîchit le statut APRÈS succès (jamais avant)', () => {
  const body = SRC.slice(
    SRC.indexOf('const handleContacterSuperieur = async'),
    SRC.indexOf('const handleContacterSuperieur = async') + 400)
  assert.match(body, /ventesApi\.contacterSuperieur\(d\.id\)/)
  assert.match(body, /refreshSuperieurStatus\(d\.id\)/)
  // L'ordre compte : le rafraîchissement suit l'appel réussi, pas l'inverse.
  const contacterIdx = body.indexOf('ventesApi.contacterSuperieur(d.id)')
  const refreshIdx = body.indexOf('refreshSuperieurStatus(d.id)')
  assert.ok(contacterIdx < refreshIdx)
})

test('VX215 : le sondage (useVisibilityAwarePolling) est désactivé sans demande en attente', () => {
  assert.match(SRC, /import useVisibilityAwarePolling from '..\/..\/hooks\/useVisibilityAwarePolling'/)
  assert.match(
    SRC,
    /useVisibilityAwarePolling\(\s*\[\{ fn: \(\) => pendingSuperieurIds\.forEach\(refreshSuperieurStatus\), intervalMs: \d+ \}\],\s*\{ enabled: pendingSuperieurIds\.length > 0 \}/)
})

test('VX215 : pendingSuperieurIds exclut les demandes déjà vues (jamais de sondage sur du « vu »)', () => {
  const body = SRC.slice(
    SRC.indexOf('const pendingSuperieurIds = useMemo('),
    SRC.indexOf('const pendingSuperieurIds = useMemo(') + 250)
  assert.match(body, /s\?\.requested && !s\.seen/)
})

test('VX215 : la ligne du devis rend « Pris en charge » quand vu, « en attente » sinon', () => {
  assert.match(SRC, /superieurStatus\[d\.id\]\?\.requested/)
  assert.match(SRC, /Pris en charge/)
  assert.match(SRC, /Avis demandé — en attente/)
})

test('VX215 : superieurStatus est bien passé dans le rowCtx (DevisRow le reçoit)', () => {
  const rowDestructure = SRC.slice(
    SRC.indexOf('function DevisRow({ d, ctx }) {'),
    SRC.indexOf('} = ctx') + 10)
  assert.match(rowDestructure, /superieurStatus/)
})
