// ACAL345 — harnais partagé des tests de ProduitForm (select natif à la place
// du Select Radix, faux stockApi, wrapper Redux + Router + Theme) au lieu
// d'être recopié dans chaque fichier. Les `vi.mock` restent dans le test
// (hissés par vitest) et délèguent ici via une fabrique asynchrone.
import { vi } from 'vitest'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// eslint-disable-next-line react-refresh/only-export-components -- fixture de test, pas de HMR
const Passthrough = ({ children }) => <>{children}</>

// eslint-disable-next-line react-refresh/only-export-components -- fixture de test, pas de HMR
const SelectNatif = ({ value, onValueChange, children }) => {
  const kids = Array.isArray(children) ? children : [children]
  const trigger = kids.find((k) => k?.props?.id)
  return (
    <select id={trigger?.props?.id} value={value} onChange={(e) => onValueChange(e.target.value)}>
      {kids}
    </select>
  )
}

/** `../../ui` réel, dont le Select Radix devient un <select> natif. */
export const uiAvecSelectNatif = (actual) => ({
  ...actual,
  Select: SelectNatif,
  SelectTrigger: Passthrough,
  SelectValue: () => null,
  SelectContent: Passthrough,
  SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
})

/** Espions partagés (UNE instance par module de test) : fiches techniques
 *  et produit du faux stockApi. */
export const espionsStock = {
  getFichesTechniques: vi.fn(() => Promise.resolve({ data: [] })),
  createFicheTechnique: vi.fn(() => Promise.resolve({ data: { id: 501 } })),
  updateFicheTechnique: vi.fn(() => Promise.resolve({ data: {} })),
  createProduitApi: vi.fn((data) => Promise.resolve({ data: { id: 42, ...data } })),
  updateProduitApi: vi.fn((id, data) => Promise.resolve({ data: { id, ...data } })),
}

/** Le default de `api/stockApi` simulé, branché sur `espionsStock`. */
export const stockApiSimule = ({
  getFichesTechniques, createFicheTechnique, updateFicheTechnique,
  createProduitApi, updateProduitApi,
} = espionsStock) => ({
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
})

const storeAdmin = configureStore({
  reducer: {
    auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
    stock: (s = { categories: [], fournisseurs: [], produits: [] }) => s,
  },
})

/** Option `wrapper` de `render` : admin Directeur, stock vide, routeur, thème. */
export function wrapperProduitForm({ children }) {
  return (
    <Provider store={storeAdmin}>
      <MemoryRouter><ThemeProvider>{children}</ThemeProvider></MemoryRouter>
    </Provider>
  )
}
