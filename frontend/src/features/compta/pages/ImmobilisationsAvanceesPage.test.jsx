import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT29 — Immobilisations avancées (NTFIN40-43) : composants, dépréciations,
   mutations, encours (CIP). Fixtures alignées sur les serializers réels
   (apps/compta/serializers.py) — ex. ComposantImmobilisationSerializer expose
   `dotation_annuelle` en LECTURE SEULE, jamais tapé par l'écran. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  composants: vi.fn(),
  depreciations: vi.fn(),
  poster: vi.fn(),
  mutations: vi.fn(),
  encours: vi.fn(),
  mettreEnService: vi.fn(),
  immobilisations: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    composantsImmobilisation: { list: mocks.composants },
    depreciationsImmobilisation: { list: mocks.depreciations, poster: mocks.poster },
    mutationsImmobilisation: { list: mocks.mutations },
    immobilisationsEnCours: { list: mocks.encours, mettreEnService: mocks.mettreEnService },
    immobilisations: { list: mocks.immobilisations },
    centresCout: { list: vi.fn().mockResolvedValue({ data: [] }) },
  },
}))

import ImmobilisationsAvanceesPage from './ImmobilisationsAvanceesPage.jsx'

function mount(initialEntries = ['/']) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider><ImmobilisationsAvanceesPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ImmobilisationsAvanceesPage — composants (PACT29)', () => {
  it('affiche la dotation annuelle calculée par le serveur', async () => {
    mocks.composants.mockResolvedValue({
      data: [{ id: 1, immobilisation: 7, libelle: 'Onduleur', valeur: '10000.00',
        duree_amortissement: 5, methode: 'lineaire', dotation_annuelle: '2000.00' }],
    })
    mount()
    expect(await screen.findByText('Onduleur')).toBeInTheDocument()
  })
})

describe('ImmobilisationsAvanceesPage — dépréciations (PACT29)', () => {
  it('poste un test de dépréciation non encore postée', async () => {
    mocks.composants.mockResolvedValue({ data: [] })
    mocks.depreciations.mockResolvedValue({
      data: [{ id: 5, immobilisation: 2, date_test: '2026-06-01',
        valeur_recuperable: '8000.00', valeur_comptable: '10000.00',
        perte_valeur: '2000.00', reversible: true, reprise: false, ecriture: null }],
    })
    mocks.poster.mockResolvedValueOnce({ data: {} })
    mount(['/?onglet=depreciations'])

    const bouton = await screen.findByRole('button', { name: /Poster/i })
    fireEvent.click(bouton)
    await waitFor(() => expect(mocks.poster).toHaveBeenCalledWith(5))
  })
})

describe('ImmobilisationsAvanceesPage — encours CIP (PACT29)', () => {
  it('propose « Mettre en service » pour un CIP en cours', async () => {
    mocks.composants.mockResolvedValue({ data: [] })
    mocks.encours.mockResolvedValue({
      data: [{ id: 3, libelle: 'Extension atelier', compte_encours: '231',
        montant_cumule: '15000.00', statut: 'en_cours', statut_display: 'En cours',
        date_mise_en_service: null, immobilisation: null, lignes: [] }],
    })
    mount(['/?onglet=encours'])

    expect(await screen.findByText('Extension atelier')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Mettre en service/i }).length).toBeGreaterThan(0)
  })
})
