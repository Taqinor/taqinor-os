import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { toast } from '../../../ui'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT32 — Clés de répartition (NTFIN20) et engagements comptables (NTFIN23).
   Piège de nommage vérifié : `comptaApi.engagementsComptables` porte le VRAI
   backend /compta/engagements/ — jamais l'ancien homonyme français de
   EngagementsPage.jsx (retenues de garantie…). */

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
  cles: vi.fn(),
  valider: vi.fn(),
  allocations: vi.fn(),
  allocationsRecurrentes: vi.fn(),
  engagements: vi.fn(),
  liquider: vi.fn(),
  centres: vi.fn(),
  comptes: vi.fn(),
  referentiels: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    clesRepartition: { list: mocks.cles, valider: mocks.valider },
    lignesCleRepartition: { list: vi.fn() },
    allocations: { list: mocks.allocations },
    allocationsRecurrentes: { list: mocks.allocationsRecurrentes },
    engagementsComptables: { list: mocks.engagements, liquider: mocks.liquider },
    centresCout: { list: mocks.centres },
    comptes: { list: mocks.comptes },
    referentielsComptables: { list: mocks.referentiels },
  },
}))

import AllocationsEngagementsPage from './AllocationsEngagementsPage.jsx'

function mount(initialEntries = ['/']) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider><AllocationsEngagementsPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('AllocationsEngagementsPage — clés de répartition (PACT32)', () => {
  it('rejette visiblement une clé dont les coefficients ne totalisent pas 100 %', async () => {
    mocks.cles.mockResolvedValue({
      data: [{ id: 1, code: 'FG', libelle: 'Frais généraux', type_cle: 'manuel',
        type_display: 'Manuel (coefficients saisis)', base: 'm2', total_coefficients: '80.0000',
        actif: true, lignes: [] }],
    })
    mocks.valider.mockRejectedValueOnce({
      response: { data: { detail: 'Les coefficients de la clé FG totalisent 80 %, pas 100 %.' } },
    })
    const erreur = vi.spyOn(toast, 'error')
    mount()

    const bouton = (await screen.findAllByRole('button', { name: /Valider \(Σ = 100 %\)/i }))[0]
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.valider).toHaveBeenCalledWith(1))
    // Même raison qu'ailleurs : le refus serveur passe par le toast. On
    // vérifie qu'il est relayé mot pour mot.
    expect(erreur).toHaveBeenCalledWith('Les coefficients de la clé FG totalisent 80 %, pas 100 %.')
  })
})

describe('AllocationsEngagementsPage — engagements comptables (PACT32)', () => {
  it("liquide un engagement partiellement soldé (pas l'homonyme retenues de garantie)", async () => {
    mocks.cles.mockResolvedValue({ data: [] })
    mocks.engagements.mockResolvedValue({
      data: [{ id: 9, reference: 'BC-001', type_engagement: 'bon_commande',
        type_display: 'Bon de commande', compte: 4, montant_engage: '5000.00',
        montant_residuel: '5000.00', statut: 'engage', statut_display: 'Engagé' }],
    })
    mocks.liquider.mockResolvedValueOnce({ data: {} })
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('2000')
    mount(['/?onglet=engagements'])

    const bouton = (await screen.findAllByRole('button', { name: /Liquider/i }))[0]
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.liquider).toHaveBeenCalledWith(9, { montant: 2000 }))
    promptSpy.mockRestore()
  })
})
