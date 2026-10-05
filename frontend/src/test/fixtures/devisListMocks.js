import { vi } from 'vitest'

/* Mocks PARTAGÉS des tests de la liste des devis (DevisList). Un `vi.mock`
   reste dans chaque test (il est hissé), mais son CORPS vient d'ici :
     vi.mock('../../api/uxviewsApi', async () =>
       (await import('../../test/fixtures/devisListMocks.js')).uxviewsApiMock())
   Aucune valeur n'est inventée : ce sont les neutralisations réseau que ces
   tests recopiaient chacun. */

/** Action « thunk-like » chaînable en `.unwrap()` (comme un createAsyncThunk). */
export function actionDepliable(type, onCall) {
  return (payload) => {
    if (onCall) onCall(payload)
    const action = { type }
    action.unwrap = () => Promise.resolve()
    return action
  }
}

/** ventesSlice : liste sans réseau, PDF/BC neutralisés (`onPdf` capture l'appel). */
export function ventesSliceMock(actual, onPdf) {
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
    genererPdfDevis: actionDepliable('ventes/genererPdfDevis/noop', onPdf),
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
}

/** ventesApi : état du PDF « en cours » + variantes/historique vides. */
export function ventesApiPdfMock(actual, devisId) {
  return {
    ...actual,
    default: {
      ...actual.default,
      etatPdfDevis: vi.fn(() => Promise.resolve({
        data: { devis: devisId, statut: 'en_cours', fichier_pdf: false, erreur: null, date: null },
      })),
      getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
      historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
    },
  }
}

export function crmApiMock(actual) {
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
  }
}

export function uxviewsApiMock() {
  return {
    default: {
      listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
      createSavedView: vi.fn(() => Promise.resolve({ data: { id: 1, ecran: 'ventes.devis' } })),
      updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
      deleteSavedView: vi.fn(() => Promise.resolve({})),
    },
  }
}
