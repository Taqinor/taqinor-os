import { vi } from 'vitest'

/* Neutralisations COMMUNES des suites de la liste `/calepinage` (ENF19) :
   navigation, API calepinage (liste) et API CRM (leads, clients). Importer ce
   module AVANT `CalepinageList` enregistre ces `vi.mock` ; chaque test règle
   ses réponses sur `mocks`. */
export const mocks = {
  list: vi.fn(),
  getLeads: vi.fn(),
  searchClients: vi.fn(),
  navigate: vi.fn(),
}

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})
vi.mock('../api/calepinageApi', () => ({ default: { calepinages: { list: mocks.list } } }))
vi.mock('../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))
