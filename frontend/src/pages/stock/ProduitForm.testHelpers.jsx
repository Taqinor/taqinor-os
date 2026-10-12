/* Harnais partagé des tests ProduitForm.* (ENF19) : mocks api/ui + store + wrapper.
   Les vi.mock() de chaque test chargent ces modules par import dynamique
   (hoisting vitest) ; les vi.fn exportés sont les mêmes instances partout. */
import { vi } from 'vitest'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

export const apiPost = vi.fn()
export const apiGet = vi.fn(() => Promise.resolve({ data: [] }))
export const getFichesTechniques = vi.fn(() => Promise.resolve({ data: [] }))
export const createFicheTechnique = vi.fn(() => Promise.resolve({ data: { id: 501 } }))
export const updateFicheTechnique = vi.fn(() => Promise.resolve({ data: {} }))
// `stockSlice.createProduit`/`updateProduit` (createAsyncThunk RÉELS) appellent
// `stockApi.createProduit`/`updateProduit` : les stubber ici suffit.
export const createProduitApi = vi.fn((data) => Promise.resolve({ data: { id: 42, ...data } }))
export const updateProduitApi = vi.fn((id, data) => Promise.resolve({ data: { id, ...data } }))

export const axiosMock = {
  default: { get: (...args) => apiGet(...args), post: (...args) => apiPost(...args) },
}

/** Select Radix remplacé par un <select> natif. */
export function uiMock(actual) {
  const Passthrough = ({ children }) => <>{children}</>
  const Select = ({ value, onValueChange, children }) => {
    const kids = Array.isArray(children) ? children : [children]
    const trigger = kids.find((k) => k?.props?.id)
    return (
      <select id={trigger?.props?.id} value={value} onChange={(e) => onValueChange(e.target.value)}>
        {kids}
      </select>
    )
  }
  return {
    ...actual,
    Select,
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
}

export const stockApiMock = {
  default: {
    getProduitPrixFournisseurs: () => Promise.resolve({ data: [] }),
    comparerFournisseurs: () => Promise.resolve({ data: [] }),
    comparerTcoFournisseurs: () => Promise.resolve({ data: { fournisseurs: [] } }),
    createPrixFournisseur: () => Promise.resolve({ data: {} }),
    updatePrixFournisseur: () => Promise.resolve({ data: {} }),
    deletePrixFournisseur: () => Promise.resolve({ data: {} }),
    uploadProduitImage: () => Promise.resolve({ data: {} }),
    getFichesTechniques: (...args) => getFichesTechniques(...args),
    createFicheTechnique: (...args) => createFicheTechnique(...args),
    updateFicheTechnique: (...args) => updateFicheTechnique(...args),
    createProduit: (...args) => createProduitApi(...args),
    updateProduit: (...args) => updateProduitApi(...args),
  },
}

const store = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    stock: (s = { categories: [], fournisseurs: [], produits: [] }) => s,
  },
})

export function wrapper({ children }) {
  return (
    <Provider store={store}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}

/** beforeEach commun : remet les stubs de fiche technique à leur défaut. */
export function resetFicheMocks() {
  apiGet.mockResolvedValue({ data: [] })
  getFichesTechniques.mockResolvedValue({ data: [] })
  createFicheTechnique.mockResolvedValue({ data: { id: 501 } })
  updateFicheTechnique.mockResolvedValue({ data: {} })
}
