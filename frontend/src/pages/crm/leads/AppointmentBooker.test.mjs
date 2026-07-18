// Régressions LW6 (recon 05 P2#10/#11) : AppointmentBooker.jsx. Comme
// SigneDialog.test.mjs, on vérifie des invariants de SOURCE (le fichier est
// du JSX, donc non importable par node:test).
// NB : ce fichier n'est PAS encore câblé dans le job CI
// (.github/workflows/ci.yml, hors périmètre de ce lane) ; à exécuter :
//   node --test src/pages/crm/leads/AppointmentBooker.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'AppointmentBooker.jsx'), 'utf8')

// P2#10 — <form> imbriqué dans le <form> de LeadForm (HTML invalide, Enter
// fragile). Le fix retire TOUTE balise <form> du fichier : la soumission
// (clic + Entrée) est gérée localement sur un div role="group".
test('LW6 : plus aucune balise <form> (HTML invalide imbriqué dans LeadForm)', () => {
  assert.doesNotMatch(SRC, /<form/)
  assert.match(SRC, /role="group"/)
  assert.match(SRC, /id="appt-booker-form"/) // hook conservé (aria-controls du disclosure)
})

test('LW6 : soumission au clic (bouton) ET à Entrée (onKeyDown local, jamais un submit natif)', () => {
  assert.match(SRC, /onKeyDown=\{/)
  assert.match(SRC, /e\.key === 'Enter'/)
  assert.match(SRC, /onClick=\{handleBook\}/)
  // handleBook n'exige plus un SubmitEvent — appelable au clic ET au clavier.
  assert.match(SRC, /e\?\.preventDefault\?\.\(\)/)
})

// P2#11 — l'échec d'annulation était avalé en silence (catch {}) : le
// commercial croyait le RDV annulé alors qu'il tenait toujours. Le fix
// affiche un toast d'erreur explicite et n'appelle PAS load() en échec (la
// liste reste honnête : le RDV encore là parce qu'il n'a pas été annulé).
test('LW6 : échec d\'annulation surfacé par un toast.error (jamais avalé en silence)', () => {
  assert.match(SRC, /import \{ toast \} from '\.\.\/\.\.\/\.\.\/ui\/confirm'/)
  const handleCancelBlock = SRC.slice(
    SRC.indexOf('async function handleCancel'),
    SRC.indexOf('async function handleDownloadIcs'),
  )
  assert.match(handleCancelBlock, /toast\.error\(/)
  // load() n'est appelé QUE dans le chemin de succès (try), jamais en catch.
  const tryBlock = handleCancelBlock.slice(0, handleCancelBlock.indexOf('catch'))
  const catchBlock = handleCancelBlock.slice(handleCancelBlock.indexOf('catch'))
  assert.match(tryBlock, /load\(\)/)
  assert.doesNotMatch(catchBlock.slice(0, catchBlock.indexOf('finally')), /load\(\)/)
})

test('LW6 : bouton Annuler désactivé pendant la requête d\'annulation en cours', () => {
  assert.match(SRC, /cancellingId/)
  assert.match(SRC, /disabled=\{cancellingId === a\.id\}/)
  assert.match(SRC, /setCancellingId\(apptId\)/)
  assert.match(SRC, /setCancellingId\(null\)/)
})
