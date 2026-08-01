import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import VentesCockpit from './VentesCockpit'

/* ODY16 — rendu smoke du cockpit Ventes (ModuleHero + actions rapides + KPI).
   Aucun appel réseau réel : `fetchDevis`/`fetchFactures` sont mockés en
   no-op (même patron que ClientList.test.jsx / CrmCockpit.test.jsx). Les
   compteurs KPI utilisent UNIQUEMENT le statut DOCUMENT du devis/facture
   (règle #4 : brouillon/envoye/accepte/…) — jamais une clé du funnel
   STAGES.py (règle #2). */

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
    fetchFactures: () => ({ type: 'ventes/fetchFactures/noop' }),
  }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore({ devis = [], factures = [] } = {}) {
  return configureStore({
    reducer: {
      ventes: (state = { devis, factures, loading: false, error: null }) => state,
    },
  })
}

function mount(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/cockpit']}>
        <ThemeProvider>
          <VentesCockpit />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('VentesCockpit — rendu smoke (ODY16)', () => {
  it('affiche le titre Ventes (ModuleHero) et les actions rapides', () => {
    mount()
    expect(screen.getByRole('heading', { name: 'Ventes' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nouveau devis/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Bons de commande/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Relances/ })).toBeInTheDocument()
  })

  it('affiche les compteurs KPI dérivés des devis/factures chargés (statuts DOCUMENT, règle #4)', () => {
    mount({
      devis: [
        { id: 1, statut: 'brouillon' },
        { id: 2, statut: 'envoye' },
        { id: 3, statut: 'accepte' },
      ],
      factures: [
        { id: 1, statut: 'emise', montant_du: '500' },
        { id: 2, statut: 'payee', montant_du: '0' },
        { id: 3, statut: 'brouillon', montant_du: '200' },
      ],
    })
    const stats = screen.getByTestId('ventes-cockpit-stats')
    expect(stats).toHaveTextContent('Devis en cours')
    expect(stats).toHaveTextContent('2')
    expect(stats).toHaveTextContent('Devis acceptés')
    expect(stats).toHaveTextContent('1')
    // Une seule facture impayée compte (statut brouillon exclu volontairement).
    expect(stats).toHaveTextContent('Factures impayées')
    expect(stats).toHaveTextContent('1 ·')
  })
})
