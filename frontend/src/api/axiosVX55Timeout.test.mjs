// VX55 — Discipline réseau : timeout axios global + annulation des requêtes
// obsolètes. Aucun `timeout` n'existait sur l'instance axios et ZÉRO
// AbortController dans l'app : sur 3G qui cale, un écran gelait indéfiniment,
// et une réponse tardive pouvait écraser l'état d'un AUTRE écran après
// navigation. Verified against SOURCE (no node_modules in this worktree/lane
// — axios.js pulls in ../lib/toast → sonner/React, unrunnable standalone).
//   node --test src/api/axiosVX55Timeout.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const AXIOS_SRC = readFileSync(join(HERE, 'axios.js'), 'utf8')
const CRM_API_SRC = readFileSync(join(HERE, 'crmApi.js'), 'utf8')
const VENTES_API_SRC = readFileSync(join(HERE, 'ventesApi.js'), 'utf8')
const CRM_SLICE_SRC = readFileSync(join(HERE, '../features/crm/store/crmSlice.js'), 'utf8')
const VENTES_SLICE_SRC = readFileSync(join(HERE, '../features/ventes/store/ventesSlice.js'), 'utf8')
const LEADS_PAGE_SRC = readFileSync(join(HERE, '../pages/crm/leads/LeadsPage.jsx'), 'utf8')
const DEVIS_LIST_SRC = readFileSync(join(HERE, '../pages/ventes/DevisList.jsx'), 'utf8')
const CLIENT_LIST_SRC = readFileSync(join(HERE, '../pages/crm/ClientList.jsx'), 'utf8')

test('VX55 : l\'instance axios porte un timeout de 20 s', () => {
  assert.match(AXIOS_SRC, /const REQUEST_TIMEOUT_MS = 20000/)
  assert.match(AXIOS_SRC, /axios\.create\(\{[\s\S]*?timeout: REQUEST_TIMEOUT_MS,[\s\S]*?\}\)/)
})

test('VX55 : ECONNABORTED déclenche un toast FR distinct — jamais le message générique', () => {
  const start = AXIOS_SRC.indexOf("if (!originalRequest.suppressErrorToast")
  // ERR-AGNR40-IDEMPOTENCE-EN-VOL a ajouté l'exception 409 « idempotency_en_cours »
  // avant le toast générique : la fenêtre couvre tout le bloc du pont de toasts.
  const block = AXIOS_SRC.slice(start, start + 2000)
  assert.match(block, /error\.code === 'ECONNABORTED'/)
  assert.match(block, /La connexion a expiré/)
  // La branche ECONNABORTED doit sortir AVANT le toast générique (return).
  const econnIdx = block.indexOf("error.code === 'ECONNABORTED'")
  const genericIdx = block.indexOf('toastError(errorMessageFrom(error))')
  assert.ok(econnIdx < genericIdx && econnIdx !== -1 && genericIdx !== -1)
})

test('VX55 : une annulation (AbortController/isCancel) ne toaste jamais', () => {
  assert.match(AXIOS_SRC, /!axios\.isCancel\?\.\(error\)/)
})

test('VX55 : getLeads/getClients/getDevis acceptent un config (signal) optionnel', () => {
  assert.match(CRM_API_SRC, /getClients: \(params, config\) => api\.get\('\/crm\/clients\/', \{ params, \.\.\.config \}\)/)
  assert.match(CRM_API_SRC, /getLeads: \(params, config\) => api\.get\('\/crm\/leads\/', \{ params, \.\.\.config \}\)/)
  assert.match(VENTES_API_SRC, /getDevis: \(params, config\) => api\.get\('\/ventes\/devis\/', \{ params, \.\.\.config \}\)/)
})

test('VX55 : fetchLeads/fetchClients transmettent le signal du thunk à chaque page', () => {
  const fetchClientsBody = CRM_SLICE_SRC.slice(
    CRM_SLICE_SRC.indexOf("export const fetchClients"),
    CRM_SLICE_SRC.indexOf("export const createClient"))
  assert.match(fetchClientsBody, /\{ rejectWithValue, signal \}/)
  assert.match(fetchClientsBody, /crmApi\.getClients\(\{ page, page_size: pageSize \}, \{ signal \}\)/)

  const fetchLeadsBody = CRM_SLICE_SRC.slice(
    CRM_SLICE_SRC.indexOf("export const fetchLeads"),
    CRM_SLICE_SRC.indexOf("export const createLead"))
  // VX163 — fetchLeads est enrobé par createCancellableThunk. PERF-CRM
  // (2026-09-01) : le thunk garde le thunkAPI ENTIER (dispatch du flux
  // progressif) — le signal est transmis à chaque page via thunkAPI.signal,
  // le CONTRAT VX55 (annulation par page) est inchangé.
  assert.match(fetchLeadsBody, /createCancellableThunk\('crm\/fetchLeads', \(params, thunkAPI\)/)
  assert.match(fetchLeadsBody, /\{ signal: thunkAPI\.signal \}/)
})

test('VX55 : fetchDevis transmet le signal du thunk à chaque page', () => {
  const fetchDevisBody = VENTES_SLICE_SRC.slice(
    VENTES_SLICE_SRC.indexOf("export const fetchDevis"),
    VENTES_SLICE_SRC.indexOf("export const createDevis"))
  // VX163 — fetchDevis enrobé par createCancellableThunk : (requete, { signal }).
  // T4-X4-005 — l'écran Devis demande UNE page (`requete`) : le signal du thunk
  // suit les DEUX chemins (toutes les pages sans requête, une page avec), et la
  // synthèse par statut lue à côté de la page est annulée avec elle.
  assert.match(fetchDevisBody, /createCancellableThunk\('ventes\/fetchDevis', \(requete, \{ signal \}\)/)
  assert.match(fetchDevisBody, /ventesApi\.getDevis\(\{ page, page_size: pageSize \}, \{ signal \}\)/)
  assert.match(fetchDevisBody, /chargerPageDevis\(requete, signal\)/)
  const pageBody = VENTES_SLICE_SRC.slice(
    VENTES_SLICE_SRC.indexOf('async function chargerPageDevis'),
    VENTES_SLICE_SRC.indexOf('export const fetchDevis'))
  assert.match(pageBody, /ventesApi\.getDevis\(requete, \{ signal \}\)/)
  assert.match(pageBody, /ventesApi\.getDevisSynthese\(\{ signal \}\)/)
})

test('VX55 : LeadsPage annule le thunk fetchLeads au cleanup d\'effet (démontage/changement de filtre)', () => {
  // LB6 — `refetch` est désormais useCallback (bug #4) : la déclaration
  // littérale a changé, l'effet d'annulation (thunk.abort) ci-dessous n'a
  // PAS bougé (effet séparé, indépendant de `refetch`).
  const start = LEADS_PAGE_SRC.indexOf('const refetch = useCallback(')
  assert.ok(start > 0, 'refetch introuvable')
  const block = LEADS_PAGE_SRC.slice(start, start + 600)
  assert.match(block, /const thunk = dispatch\(fetchLeads\(archivedParam\(filters\.archived\)\)\)/)
  assert.match(block, /return \(\) => thunk\??\.abort\??\.\(\)/)
})

test('VX55 : DevisList annule le thunk fetchDevis au cleanup d\'effet (démontage)', () => {
  // T4-X4-005 — la liste charge la page demandée (`requete`) : même annulation.
  const start = DEVIS_LIST_SRC.indexOf('const thunk = dispatch(fetchDevis(requete))')
  assert.notEqual(start, -1)
  const block = DEVIS_LIST_SRC.slice(start, start + 100)
  assert.match(block, /return \(\) => thunk\??\.abort\??\.\(\)/)
})

test('VX55 : ClientList annule le thunk fetchClients au cleanup d\'effet (démontage)', () => {
  const start = CLIENT_LIST_SRC.indexOf('const thunk = dispatch(fetchClients())')
  assert.notEqual(start, -1)
  const block = CLIENT_LIST_SRC.slice(start, start + 100)
  assert.match(block, /return \(\) => thunk\??\.abort\??\.\(\)/)
})

test('CE2E8 : fetchDevis relance la requête si la promesse partagée a été annulée par un autre montage', () => {
  const body = VENTES_SLICE_SRC.slice(
    VENTES_SLICE_SRC.indexOf("export const fetchDevis"),
    VENTES_SLICE_SRC.indexOf("export const createDevis"))
  assert.match(body, /isCancelledError\(err\) && !signal\.aborted \? charger\(\)/)
})

test('ADEV112 : un corps d’erreur en Blob ou `{erreurs}` toaste le message SERVI (jamais le générique)', () => {
  const start = AXIOS_SRC.indexOf("if (!originalRequest.suppressErrorToast")
  const block = AXIOS_SRC.slice(start, start + 2000)
  assert.match(AXIOS_SRC, /import \{ apiErrorMessageServi \} from '\.\.\/lib\/apiError'/)
  assert.match(block, /corps instanceof Blob\) \|\| corps\?\.erreurs\)/)
  assert.match(block, /apiErrorMessageServi\(error\)\.then\(\(m\) => \{ toastError\(m\); return Promise\.reject\(error\) \}\)/)
  // Le décodage précède le toast générique, toujours derrière la garde suppressErrorToast.
  assert.ok(block.indexOf('apiErrorMessageServi(error)') < block.indexOf('toastError(errorMessageFrom(error))'))
})

test('ADEV112 : les aperçus PDF (liste, panneau du lead) gèrent leur message — pas de toast global', () => {
  const useDevisPdf = readFileSync(join(HERE, '../pages/ventes/devisList/useDevisPdf.js'), 'utf8')
  const panneau = readFileSync(join(HERE, '../pages/crm/leads/LeadDevisPanel.jsx'), 'utf8')
  assert.match(useDevisPdf, /getProposalPdf\(d\.id, params, \{ suppressErrorToast: true \}\)/)
  assert.match(panneau, /\{ signal, suppressErrorToast: true \}\)/)
  // Le panneau affiche le `detail` décodé (même chemin messageErreurBlob que la liste), repli fixe sinon.
  assert.match(panneau, /messageErreurBlob\(err, \{ fallback: MESSAGE_APERCU_SERVEUR \}\)/)
  assert.match(panneau, /serverMessage=\{preview\.errorMessage \|\| MESSAGE_APERCU_SERVEUR\}/)
})

test("ACAL1351 : `silencieuxExpiration` coupe le seul toast d'expiration ; sans l'option le toast reste", () => {
  const start = AXIOS_SRC.indexOf("if (error.code === 'ECONNABORTED')")
  const block = AXIOS_SRC.slice(start, start + 600)
  const optionIdx = block.indexOf('originalRequest.silencieuxExpiration')
  const toastIdx = block.indexOf("toastError('La connexion a expiré")
  assert.ok(optionIdx !== -1 && toastIdx !== -1 && optionIdx < toastIdx)
  assert.match(block, /if \(originalRequest\.silencieuxExpiration\) return Promise\.reject\(error\)/)
  // L'option n'est lue qu'à cet endroit de l'intercepteur ; le délai global reste 20 s.
  assert.equal(AXIOS_SRC.split('originalRequest.silencieuxExpiration').length - 1, 1)
  assert.match(AXIOS_SRC, /const REQUEST_TIMEOUT_MS = 20000/)
})

test("J3 : le toast d'expiration porte un id FIXE (un seul à la fois, jamais empilé)", () => {
  assert.match(AXIOS_SRC, /const ID_TOAST_EXPIRATION = 'connexion-expiree'/)
  assert.match(AXIOS_SRC, /toastError\('La connexion a expiré\. Vérifiez votre connexion et réessayez\.', \{ id: ID_TOAST_EXPIRATION \}\)/)
})

test('J3 : les lectures lourdes du relevé et du démarrage de l’atelier sont lentes et silencieuses', () => {
  const CALEPINAGE = readFileSync(join(HERE, 'calepinageApi.js'), 'utf8')
  const SIMULATION = readFileSync(join(HERE, 'calepinage/simulation.js'), 'utf8')
  const SORTIES = readFileSync(join(HERE, 'calepinage/sorties.js'), 'utf8')
  assert.match(CALEPINAGE, /const detailLent = \{ get: \(id\) => api\.get\(pivot\(id\), \{ silencieuxExpiration: true, timeout: 60000 \}\) \}/)
  assert.match(CALEPINAGE, /\(crud\('calepinages'\)\),\s*\n\s*\.\.\.detailLent,/)
  for (const chemin of ['layout', 'photos', 'resultat']) {
    assert.match(CALEPINAGE, new RegExp(`${chemin}: \\(id\\) => api\\.get\\(\`\\$\\{pivot\\(id\\)\\}${chemin}/\`, \\{ silencieuxExpiration: true, timeout: 60000 \\}\\)`))
  }
  assert.match(SIMULATION, /parcours: \(id\) => api\.get\(`\$\{pivot\(id\)\}parcours\/`, LECTURE_LENTE\)/)
  assert.match(SORTIES, /releve: \(id\) => api\.get\(`\$\{pivot\(id\)\}releve\/`, \{ silencieuxExpiration: true, timeout: 60000 \}\)/)
})

test("ACAL1351 : `pret-a-envoyer/` et `design-context/` posent l'option et un délai de 60 s", () => {
  const SIMULATION = readFileSync(join(HERE, 'calepinage/simulation.js'), 'utf8')
  const CALEPINAGE = readFileSync(join(HERE, 'calepinageApi.js'), 'utf8')
  assert.match(SIMULATION, /LECTURE_LENTE = \{ silencieuxExpiration: true, timeout: 60000 \}/)
  assert.match(SIMULATION, /pret-a-envoyer\/`,\s*\{ \.\.\.LECTURE_LENTE/)
  assert.match(CALEPINAGE, /design-context\/`, \{ silencieuxExpiration: true, timeout: 60000, params \}/)
})
