import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT41 — Échéanciers de paiement en tranches (FG220). `montant_regle` et
   `reste_a_payer` sont des SerializerMethodField calculés côté serveur
   (EcheancierPaiementSerializer.get_reste_a_payer, apps/compta/serializers.py)
   — le solde affiché doit se mettre à jour visiblement dès qu'une tranche
   est réglée (Done= de PACT41), jamais un calcul client figé. */

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
  list: vi.fn(),
  get: vi.fn(),
  regler: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    echeanciersPaiement: { list: mocks.list, get: mocks.get, create: vi.fn() },
    tranchesPaiement: { create: vi.fn(), regler: mocks.regler },
  },
}))

import EcheanciersPaiementPage from './EcheanciersPaiementPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><EcheanciersPaiementPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

const ECHEANCIER = {
  id: 1, facture_id: 5, facture_reference: 'FAC-2026-005', montant_total: '30000.00',
  actif: true, date_creation: '2026-01-01',
  montant_regle: '10000.00', reste_a_payer: '20000.00',
  tranches: [
    { id: 11, echeancier: 1, numero: 1, montant: '10000.00', date_echeance: '2026-02-01',
      montant_regle: '10000.00', date_reglement: '2026-02-01', paye: true },
    { id: 12, echeancier: 1, numero: 2, montant: '20000.00', date_echeance: '2026-03-01',
      montant_regle: null, date_reglement: null, paye: false },
  ],
}

describe('EcheanciersPaiementPage — solde restant mis à jour (PACT41)', () => {
  it('règle une tranche et rafraîchit le reste à payer depuis le serveur', async () => {
    mocks.list.mockResolvedValue({ data: [ECHEANCIER] })
    mocks.regler.mockResolvedValueOnce({ data: { ...ECHEANCIER.tranches[1], paye: true } })
    mocks.get.mockResolvedValueOnce({
      data: { ...ECHEANCIER, montant_regle: '30000.00', reste_a_payer: '0.00',
        tranches: [ECHEANCIER.tranches[0], { ...ECHEANCIER.tranches[1], paye: true }] },
    })
    const promptSpy = vi.spyOn(window, 'prompt').mockReturnValue('20000')
    mount()

    fireEvent.click((await screen.findAllByText('FAC-2026-005'))[0])
    const bouton = (await screen.findAllByRole('button', { name: /Régler/i }))[0]
    fireEvent.click(bouton)

    await waitFor(() => expect(mocks.regler).toHaveBeenCalledWith(12, { montant: 20000 }))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith(1))
    promptSpy.mockRestore()
  })
})
