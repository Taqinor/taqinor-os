import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, within, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'

// J141 — la liste des devis ne doit toucher aucun réseau pendant le test : on
// neutralise le thunk de chargement (le composant le dispatche au montage).
vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchDevis: () => ({ type: 'ventes/fetchDevis/noop' }),
    genererPdfDevis: () => ({ type: 'ventes/genererPdfDevis/noop' }),
    convertirDevisEnBC: () => ({ type: 'ventes/convertirDevisEnBC/noop' }),
  }
})

import DevisList from './DevisList'

// Réducteurs minimaux : seules les tranches lues par l'écran (ventes + auth).
function makeStore({ devis = [], loading = false, error = null, role = 'admin' } = {}) {
  return configureStore({
    reducer: {
      ventes: (state = { devis, loading, error }) => state,
      auth: (state = { role }) => state,
    },
  })
}

function renderList(opts) {
  const store = makeStore(opts)
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/ventes/devis']}>
        <DevisList />
      </MemoryRouter>
    </Provider>,
  )
}

describe('DevisList — états de chargement (J141)', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers() })

  it('garde l\'en-tête « Devis » visible pendant le chargement (pas de spinner plein écran)', () => {
    renderList({ loading: true })
    // L'en-tête de page reste présent — la mise en page ne saute pas au retour des données.
    expect(screen.getByRole('heading', { name: 'Devis' })).toBeVisible()
  })

  it('affiche un squelette de tableau (et non les vraies lignes) après le seuil', () => {
    renderList({ loading: true })
    // useDelayedLoading bascule sur le squelette à 500 ms (act() flush React).
    act(() => { vi.advanceTimersByTime(600) })
    const table = document.querySelector('table.data-table')
    expect(table).not.toBeNull()
    // Des cellules squelette sont rendues (placeholders animés), aucune vraie référence.
    expect(table.querySelector('.animate-pulse, [class*="animate-pulse"]')).not.toBeNull()
  })
})

describe('DevisList — rendu des données (J141)', () => {
  it('rend les vraies lignes avec une pastille de statut quand le chargement est terminé', () => {
    renderList({
      loading: false,
      devis: [{
        id: 1, reference: 'DEV-2026-07-0001', client_nom: 'ACME', statut: 'envoye',
        date_creation: '2026-07-01', total_ttc: 12000, nb_options: 1, version: 1,
      }],
    })
    const cell = screen.getByText('DEV-2026-07-0001')
    expect(cell).toBeVisible()
    // La pastille de statut (StatusPill) restitue le libellé français dans la
    // ligne du tableau (le libellé apparaît aussi dans les cartes de résumé).
    const row = cell.closest('tr')
    expect(within(row).getByText('Envoyé')).toBeVisible()
  })
})
