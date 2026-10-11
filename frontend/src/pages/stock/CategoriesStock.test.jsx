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

// ASTK252 — stockApi RÉEL : seule la frontière HTTP `../../api/axios` est
// simulée ; les assertions portent sur la méthode et l'URL réellement appelées.
const http = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
}))
vi.mock('../../api/axios', () => ({ default: http }))
vi.mock('../../api/stockApi', () => vi.importActual('../../api/stockApi'))

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
  http.get.mockImplementation(async (url) => ({ data: url === '/stock/categories/'
    ? [{ id: 4, nom: 'Onduleurs', ordre: 1, nb_produits: 3, type_equipement: '' }] : [] }))
  http.delete.mockRejectedValue({ response: { status: 400, data: { detail: DETAIL } } })
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
    await waitFor(() => expect(http.delete).toHaveBeenCalledWith('/stock/categories/4/'))
    expect(http.get).toHaveBeenCalledWith('/stock/categories/', { params: { ordering: 'ordre' } })
    expect(await screen.findByText(DETAIL)).toBeInTheDocument()
    expect(screen.queryByText(/peut être protégée/)).toBeNull()
  })
})
