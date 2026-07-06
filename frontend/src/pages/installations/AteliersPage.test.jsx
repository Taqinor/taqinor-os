import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XMFG1-16 — AteliersPage : câble le sous-système MRP-lite (ordres
   d'assemblage / démontage, kits). On vérifie : (1) le chargement liste les
   ordres d'assemblage et rend une ligne par ordre ; (2) le bouton de création
   est masqué pour un rôle sans écriture (normal) ; (3) le passage à l'onglet
   Démontage recharge la bonne source. Tout le réseau est mocké. */

const api = vi.hoisted(() => ({
  getOrdresAssemblage: vi.fn(),
  getOrdresDemontage: vi.fn(),
  getKitsAssemblage: vi.fn(),
  bonAssemblageUrl: (id) => `/api/x/${id}/bon-pdf/`,
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

import AteliersPage from './AteliersPage'

function authReducer(role) {
  return (state = { role }) => state
}

function renderPage(role = 'responsable') {
  const store = configureStore({ reducer: { auth: authReducer(role) } })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>
          <AteliersPage />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  api.getOrdresAssemblage.mockResolvedValue({
    data: [
      { id: 1, reference: 'ASM-001', kit_nom: 'Kit onduleur', quantite: 2, statut: 'planifie', date_creation: '2026-01-01' },
    ],
  })
  api.getOrdresDemontage.mockResolvedValue({
    data: [
      { id: 9, reference: 'DSM-001', kit_nom: 'Kit batterie', quantite: 1, statut: 'planifie', date_creation: '2026-01-02' },
    ],
  })
  api.getKitsAssemblage.mockResolvedValue({
    data: [{ id: 3, nom: 'Kit onduleur', reference_interne: 'K-ONP', active: true }],
  })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AteliersPage (XMFG1-16)', () => {
  it("charge et liste les ordres d'assemblage", async () => {
    renderPage('responsable')
    await waitFor(() => expect(api.getOrdresAssemblage).toHaveBeenCalled())
    // DataTable rend potentiellement desktop + mobile → getAllByText.
    await waitFor(() =>
      expect(screen.getAllByText('ASM-001').length).toBeGreaterThan(0))
  })

  it('masque la création pour un rôle sans écriture', async () => {
    renderPage('normal')
    await waitFor(() => expect(api.getOrdresAssemblage).toHaveBeenCalled())
    expect(screen.queryByText(/Ordre d'assemblage$/)).toBeNull()
  })

  it('bascule sur le démontage et affiche ses ordres', async () => {
    renderPage('responsable')
    await waitFor(() => expect(api.getOrdresDemontage).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('radio', { name: 'Démontage' }))
    await waitFor(() =>
      expect(screen.getAllByText('DSM-001').length).toBeGreaterThan(0))
  })
})
