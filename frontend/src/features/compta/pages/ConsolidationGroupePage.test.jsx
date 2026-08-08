import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT33 — Consolidation groupe (NTFIN1-9). Un cycle VERROUILLÉ refuse toute
   modification de collecte (400 serveur) — l'écran doit afficher ce refus TEL
   QUEL, jamais planter (Done= de PACT33). EntiteConsolidation reste HORS
   PÉRIMÈTRE (mécanisme séparé, non fondu ici). */

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
  cycles: vi.fn(),
  collecter: vi.fn(),
  exercices: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    cyclesConsolidation: { list: mocks.cycles, collecter: mocks.collecter },
    liassesRemontee: { list: vi.fn().mockResolvedValue({ data: [] }) },
    mappingsConsolidation: { list: vi.fn().mockResolvedValue({ data: [] }) },
    operationsInterco: { list: vi.fn().mockResolvedValue({ data: [] }) },
    margesInternesStock: { list: vi.fn().mockResolvedValue({ data: [] }) },
    eliminationsTitres: { list: vi.fn().mockResolvedValue({ data: [] }) },
    exercices: { list: mocks.exercices },
    comptes: { list: vi.fn().mockResolvedValue({ data: [] }) },
  },
}))

import ConsolidationGroupePage from './ConsolidationGroupePage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><ConsolidationGroupePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ConsolidationGroupePage — cycle verrouillé (PACT33)', () => {
  it('affiche le refus serveur tel quel au lieu de planter', async () => {
    mocks.exercices.mockResolvedValue({ data: [] })
    mocks.cycles.mockResolvedValue({
      data: [{ id: 4, libelle: 'Consolidation 2026', exercice: 1,
        date_debut: '2026-01-01', date_fin: '2026-12-31',
        devise_presentation: 'MAD', statut: 'valide', statut_display: 'Validé',
        verrouille: true, tolerance_interco: '0.00' }],
    })
    mocks.collecter.mockRejectedValueOnce({
      response: { data: { detail: 'Cycle verrouillé : la collecte est refusée.' } },
    })
    mount()

    expect(await screen.findByText('Consolidation 2026')).toBeInTheDocument()
    const bouton = screen.getByRole('button', { name: /Collecter les liasses/i })
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.collecter).toHaveBeenCalledWith(4, {}))
    expect(await screen.findByText('Cycle verrouillé : la collecte est refusée.')).toBeInTheDocument()
    // Un cycle verrouillé propose « Ouvrir » (rouvrir), jamais « Verrouiller ».
    expect(screen.getByRole('button', { name: /Ouvrir \(déverrouiller\)/i })).toBeInTheDocument()
  })
})
