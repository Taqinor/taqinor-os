import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT28 — Fiscalité avancée : acomptes IS (NTMAR12), conventions fiscales
   (NTMAR18) et familles TVA non déductible (XACC11). Ces fixtures reprennent
   EXACTEMENT la forme des serializers (apps/compta/serializers.py) — jamais
   un champ inventé (ex. AcompteISSerializer n'a pas de "libelle"). */

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
  acomptesList: vi.fn(),
  marquerPaye: vi.fn(),
  conventionsList: vi.fn(),
  famillesList: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    acomptesIS: { list: mocks.acomptesList, marquerPaye: mocks.marquerPaye },
    conventionsFiscales: { list: mocks.conventionsList },
    famillesTvaNonDeductibles: { list: mocks.famillesList },
  },
}))

import FiscaliteAvanceePage from './FiscaliteAvanceePage.jsx'

function mount(initialEntries = ['/']) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider><FiscaliteAvanceePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('FiscaliteAvanceePage — acomptes IS (PACT28)', () => {
  it('liste les acomptes et marque payé un acompte à payer', async () => {
    mocks.acomptesList.mockResolvedValue({
      data: [
        { id: 1, exercice: 4, rang: 1, montant: '5000.00', date_echeance: '2026-03-31',
          statut: 'a_payer', statut_display: 'À payer', date_creation: '2026-01-01' },
      ],
    })
    mocks.marquerPaye.mockResolvedValueOnce({
      data: { id: 1, exercice: 4, rang: 1, montant: '5000.00', date_echeance: '2026-03-31',
        statut: 'paye', statut_display: 'Payé', date_creation: '2026-01-01' },
    })
    mount()

    expect(await screen.findByText('#4')).toBeInTheDocument()
    const bouton = await screen.findByRole('button', { name: /Marquer payé/i })
    fireEvent.click(bouton)
    await waitFor(() => expect(mocks.marquerPaye).toHaveBeenCalledWith(1))
  })
})

describe('FiscaliteAvanceePage — conventions fiscales (PACT28)', () => {
  it('affiche les conventions fiscales sur son onglet', async () => {
    mocks.acomptesList.mockResolvedValue({ data: [] })
    mocks.conventionsList.mockResolvedValue({
      data: [
        { id: 9, pays: 'France', code_pays: 'FR', taux_conventionnel: '10.00',
          libelle: 'Convention FR-MA', actif: true, date_creation: '2026-01-01' },
      ],
    })
    mount(['/?onglet=conventionsFiscales'])

    expect(await screen.findByText('France')).toBeInTheDocument()
    expect(screen.getByText('10 %')).toBeInTheDocument()
  })
})

describe('FiscaliteAvanceePage — familles TVA non déductible (PACT28)', () => {
  it('affiche les familles sur son onglet', async () => {
    mocks.acomptesList.mockResolvedValue({ data: [] })
    mocks.famillesList.mockResolvedValue({
      data: [
        { id: 3, famille: 'vehicule_tourisme', libelle: 'Véhicules de tourisme',
          actif: true, date_creation: '2026-01-01' },
      ],
    })
    mount(['/?onglet=famillesTva'])

    expect(await screen.findByText('Véhicules de tourisme')).toBeInTheDocument()
  })
})
