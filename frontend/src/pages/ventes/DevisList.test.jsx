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

describe('DevisList — U5 : factures + bon de commande générés', () => {
  it('affiche des chips facture (réf + statut) et bon de commande dans la ligne', () => {
    renderList({
      loading: false,
      devis: [{
        id: 7, reference: 'DEV-2026-07-0007', client_nom: 'ACME', statut: 'accepte',
        date_creation: '2026-07-01', total_ttc: 50000, nb_options: 1, version: 1,
        factures_liees: [
          { id: 11, reference: 'FAC-2026-07-0011', statut: 'emise', statut_display: 'Émise', type_facture: 'acompte' },
        ],
        bon_commande_etat: { exists: true, id: 5, reference: 'BC-2026-07-0005', statut: 'confirme', statut_display: 'Confirmé', mismatch: false },
      }],
    })
    const row = screen.getByText('DEV-2026-07-0007').closest('tr')
    // La facture liée apparaît avec sa référence et son libellé de statut.
    expect(within(row).getByText(/FAC-2026-07-0011/)).toBeVisible()
    expect(within(row).getByText(/Émise/)).toBeVisible()
    // Le bon de commande lié apparaît aussi.
    expect(within(row).getByText('BC-2026-07-0005')).toBeVisible()
  })

  it('n\'affiche aucune chip document quand le devis n\'a ni facture ni BC', () => {
    renderList({
      loading: false,
      devis: [{
        id: 8, reference: 'DEV-2026-07-0008', client_nom: 'ACME', statut: 'brouillon',
        date_creation: '2026-07-01', total_ttc: 1000, nb_options: 1, version: 1,
        factures_liees: [], bon_commande_etat: { exists: false, mismatch: false },
      }],
    })
    const row = screen.getByText('DEV-2026-07-0008').closest('tr')
    expect(within(row).queryByText(/FAC-/)).toBeNull()
    expect(within(row).queryByText(/^BC-/)).toBeNull()
  })
})
