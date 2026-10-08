import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   ASTK83 (C-ASTK-017) — supprimer une catégorie utilisée : la confirmation
   annonce combien de produits l'utilisent (`nb_produits` servi par le
   serializer) et l'erreur affichée est le `detail` RÉEL du serveur (ASTK82 :
   « Catégorie utilisée par 3 produits : réaffectez-les avant de la
   supprimer. »), plus le texte faux « peut être protégée ».
   Composant réel ; seule l'API est simulée (frontière réseau).
   ========================================================================== */

vi.mock('../../api/stockApi', () => ({
  default: {
    getCategories: vi.fn(),
    getMarques: vi.fn(() => Promise.resolve({ data: [] })),
    deleteCategorie: vi.fn(),
    patchCategorie: vi.fn(),
    createCategorie: vi.fn(),
    saveMarque: vi.fn(),
    deleteMarque: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import CategoriesStock from './CategoriesStock.jsx'

const DETAIL = 'Catégorie utilisée par 3 produits : réaffectez-les avant de la supprimer.'

function renderPage() {
  const store = configureStore({
    reducer: {
      auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
      stock: (s = { produits: [] }) => s,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter><ThemeProvider><CategoriesStock /></ThemeProvider></MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  stockApi.getCategories.mockResolvedValue({
    data: [{ id: 4, nom: 'Onduleurs', ordre: 1, nb_produits: 3, type_equipement: '' }],
  })
  stockApi.deleteCategorie.mockRejectedValue({ response: { status: 400, data: { detail: DETAIL } } })
  // ASTK231 — l'AlertDialog commune remplace la boîte native (jamais appelée).
  vi.spyOn(window, 'confirm')
})

afterEach(() => { window.confirm.mockRestore() })

describe('CategoriesStock — suppression d\'une catégorie utilisée (ASTK83)', () => {
  it('suppression refusée affiche le detail serveur', async () => {
    renderPage()
    fireEvent.click(await screen.findByLabelText('Supprimer la catégorie'))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/Catégorie utilisée par 3 produits/)).toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Supprimer' }))
    expect(window.confirm).not.toHaveBeenCalled()
    await waitFor(() => expect(stockApi.deleteCategorie).toHaveBeenCalledWith(4))
    expect(await screen.findByText(DETAIL)).toBeInTheDocument()
    expect(screen.queryByText(/peut être protégée/)).toBeNull()
  })
})
