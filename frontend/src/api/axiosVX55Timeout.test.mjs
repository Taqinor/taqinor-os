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
  const block = AXIOS_SRC.slice(start, start + 900)
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
  assert.match(fetchClientsBody, /crmApi\.getClients\(\{ page \}, \{ signal \}\)/)

  const fetchLeadsBody = CRM_SLICE_SRC.slice(
    CRM_SLICE_SRC.indexOf("export const fetchLeads"),
    CRM_SLICE_SRC.indexOf("export const createLead"))
  // VX163 — fetchLeads est enrobé par createCancellableThunk : signal destructuré
  // du 2e arg (params, { signal }) plutôt que { rejectWithValue, signal }.
  assert.match(fetchLeadsBody, /createCancellableThunk\('crm\/fetchLeads', \(params, \{ signal \}\)/)
  assert.match(fetchLeadsBody, /crmApi\.getLeads\(\{ \.\.\.\(params \?\? \{\}\), page \}, \{ signal \}\)/)
})

test('VX55 : fetchDevis transmet le signal du thunk à chaque page', () => {
  const fetchDevisBody = VENTES_SLICE_SRC.slice(
    VENTES_SLICE_SRC.indexOf("export const fetchDevis"),
    VENTES_SLICE_SRC.indexOf("export const createDevis"))
  // VX163 — fetchDevis enrobé par createCancellableThunk : (_, { signal }).
  assert.match(fetchDevisBody, /createCancellableThunk\('ventes\/fetchDevis', \(_, \{ signal \}\)/)
  assert.match(fetchDevisBody, /ventesApi\.getDevis\(\{ page \}, \{ signal \}\)/)
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
  const start = DEVIS_LIST_SRC.indexOf('const thunk = dispatch(fetchDevis())')
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
