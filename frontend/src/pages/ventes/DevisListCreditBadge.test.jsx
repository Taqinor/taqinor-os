import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

/* WIR189/NTCRD23 — la pastille d'état crédit (CreditBadge) était construite
   mais jamais affichée. Elle est désormais rendue à côté du nom client de la
   liste des devis, alimentée par UN SEUL appel batch pour toute la page
   (jamais un appel par ligne — c'était le piège de cette tâche), et dégradée
   en silence sur 403 / réponse vide.

   Charge utile alignée sur `credit.selectors.badges_credit` :
   `{client_id: 'vert'|'orange'|'rouge'}`. */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }) }
})
vi.mock('../../api/uxviewsApi', () => ({
  default: {
    listSavedViews: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    createSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    updateSavedView: vi.fn(() => Promise.resolve({ data: {} })),
    deleteSavedView: vi.fn(() => Promise.resolve({})),
  },
}))
vi.mock('../../api/crmApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getMotifsPerte: vi.fn(() => Promise.resolve({ data: [] })) },
  }
})

const getBadgesMock = vi.fn()
vi.mock('../../api/creditApi', () => ({
  default: { getBadges: (...a) => getBadgesMock(...a) },
}))

import DevisList from './DevisList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const devisBase = {
  reference: 'DEV-2026-07-0001', client_nom: 'ACME', statut: 'brouillon',
  date_creation: '2026-07-01', total_ttc: 12000, version: 1,
}

const TROIS_DEVIS = [
  { ...devisBase, id: 1, client: 10, reference: 'DEV-2026-07-0001', client_nom: 'ACME' },
  { ...devisBase, id: 2, client: 11, reference: 'DEV-2026-07-0002', client_nom: 'BETA' },
  { ...devisBase, id: 3, client: 12, reference: 'DEV-2026-07-0003', client_nom: 'GAMMA' },
]

function renderList(devis) {
  const store = configureStore({
    reducer: {
      ventes: (s = { devis, loading: false, error: null }) => s,
      auth: (s = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => s,
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

describe('WIR189 — pastille crédit dans la liste des devis', () => {
  it('rend les 3 couleurs avec UN SEUL appel réseau pour toute la page', async () => {
    getBadgesMock.mockResolvedValue({ data: { 10: 'vert', 11: 'orange', 12: 'rouge' } })
    renderList(TROIS_DEVIS)

    await waitFor(() => expect(screen.getAllByTestId('credit-badge')).toHaveLength(3))

    // LA garde de la tâche : un appel batch, pas un appel par ligne.
    expect(getBadgesMock).toHaveBeenCalledTimes(1)
    expect(getBadgesMock).toHaveBeenCalledWith([10, 11, 12])

    const pastilles = screen.getAllByTestId('credit-badge')
    const classes = pastilles.map(p => p.className)
    expect(classes.some(c => c.includes('credit-badge--vert'))).toBe(true)
    expect(classes.some(c => c.includes('credit-badge--orange'))).toBe(true)
    expect(classes.some(c => c.includes('credit-badge--rouge'))).toBe(true)
  })

  it('403 : dégradation silencieuse, aucune pastille et aucune erreur affichée', async () => {
    getBadgesMock.mockRejectedValue({
      response: { status: 403, data: { detail: 'Non autorisé.' } },
    })
    renderList(TROIS_DEVIS)

    expect(await screen.findByText('DEV-2026-07-0001')).toBeInTheDocument()
    await waitFor(() => expect(getBadgesMock).toHaveBeenCalledTimes(1))
    expect(screen.queryAllByTestId('credit-badge')).toHaveLength(0)
    expect(screen.queryByText(/Non autorisé/)).toBeNull()
  })

  it('réponse partielle : seuls les clients renvoyés portent une pastille', async () => {
    getBadgesMock.mockResolvedValue({ data: { 11: 'rouge' } })
    renderList(TROIS_DEVIS)

    await waitFor(() => expect(screen.getAllByTestId('credit-badge')).toHaveLength(1))
    const ligne = screen.getByText('DEV-2026-07-0002').closest('tr')
    expect(ligne.querySelector('[data-testid="credit-badge"]')).not.toBeNull()
  })
})
