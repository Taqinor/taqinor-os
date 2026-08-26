import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* WIR189/NTCRD23 — pastille d'état crédit sur DevisList.
   Deux garanties testées ici :
   1. UN SEUL appel réseau `getBadges(ids)` pour toute la page (jamais un appel
      par ligne) — la clé est la liste dédupliquée des ids clients ;
   2. dégradation SILENCIEUSE : un 403 (vendeur sans module crédit) ne rend
      aucune pastille et ne fait pas tomber l'écran. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})

vi.mock('../../api/creditApi', () => ({
  default: { getBadges: vi.fn(() => Promise.resolve({ data: {} })) },
}))

import DevisList from './DevisList'
import creditApi from '../../api/creditApi'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

function renderList(devis) {
  const store = configureStore({
    reducer: {
      ventes: (state = { devis, loading: false, error: null }) => state,
      auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <ThemeProvider>
          <DevisList />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Trois devis, deux clients seulement (le client 3 revient deux fois) : la
// déduplication doit se voir dans les ids envoyés.
const DEVIS = [
  {
    id: 1, reference: 'DEV-0001', statut: 'envoye', is_active: true,
    client: 3, client_nom: 'Amine', date_creation: '2026-07-01', total_ttc: '1000',
  },
  {
    id: 2, reference: 'DEV-0002', statut: 'brouillon', is_active: true,
    client: 4, client_nom: 'Btissam', date_creation: '2026-07-02', total_ttc: '2000',
  },
  {
    id: 3, reference: 'DEV-0003', statut: 'brouillon', is_active: true,
    client: 3, client_nom: 'Amine', date_creation: '2026-07-03', total_ttc: '3000',
  },
]

describe('DevisList — WIR189 pastille crédit (batch)', () => {
  it('fait UN SEUL appel batch avec les ids clients dédupliqués et rend les 3 couleurs', async () => {
    creditApi.getBadges.mockResolvedValueOnce({ data: { 3: 'rouge', 4: 'orange' } })
    const { container } = renderList(DEVIS)

    await waitFor(() => expect(creditApi.getBadges).toHaveBeenCalledTimes(1))
    expect(creditApi.getBadges).toHaveBeenCalledWith(['3', '4'])

    // Client 3 = rouge (2 lignes), client 4 = orange (1 ligne).
    await waitFor(() => {
      expect(container.querySelectorAll('[data-credit-badge="rouge"]')).toHaveLength(2)
    })
    expect(container.querySelectorAll('[data-credit-badge="orange"]')).toHaveLength(1)
    expect(screen.getAllByTestId('credit-badge')).toHaveLength(3)
  })

  it('rend une pastille verte quand le crédit est sain', async () => {
    creditApi.getBadges.mockResolvedValueOnce({ data: { 3: 'vert', 4: 'vert' } })
    const { container } = renderList(DEVIS)
    await waitFor(() => {
      expect(container.querySelectorAll('[data-credit-badge="vert"]')).toHaveLength(3)
    })
  })

  it('dégrade en silence sur 403 : aucune pastille, écran intact', async () => {
    creditApi.getBadges.mockRejectedValueOnce({ response: { status: 403 } })
    const { container } = renderList(DEVIS)

    await waitFor(() => expect(creditApi.getBadges).toHaveBeenCalledTimes(1))
    expect(screen.getByText('DEV-0001')).toBeInTheDocument()
    expect(container.querySelectorAll('[data-credit-badge]')).toHaveLength(0)
  })

  it('ne rend aucune pastille quand le batch revient vide', async () => {
    creditApi.getBadges.mockResolvedValueOnce({ data: {} })
    const { container } = renderList(DEVIS)
    await waitFor(() => expect(creditApi.getBadges).toHaveBeenCalledTimes(1))
    expect(container.querySelectorAll('[data-credit-badge]')).toHaveLength(0)
  })
})
