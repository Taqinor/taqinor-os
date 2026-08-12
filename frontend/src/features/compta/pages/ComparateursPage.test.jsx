import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT36 — Comparateurs commerciaux (FG212, FG221) : calcul pur, aucun
   stockage. Fixtures alignées sur `services.comparer_cash_vs_financement`
   (apps/compta/services.py) — {cash:{cout_total,payback_annees},
   financement:{mensualite,cout_credit,cout_total,payback_annees},
   surcout_financement}. */

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
  comparerDevis: vi.fn(),
  comparerFinancement: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    comparateurDevis: { comparer: mocks.comparerDevis },
    comparateurFinancement: { comparer: mocks.comparerFinancement },
  },
}))

import ComparateursPage from './ComparateursPage.jsx'

function mount(initialEntries = ['/']) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider><ComparateursPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ComparateursPage — versions de devis (PACT36)', () => {
  it('affiche le diff champ à champ renvoyé par le serveur', async () => {
    mocks.comparerDevis.mockResolvedValueOnce({
      data: {
        a: { total_ttc: 100000 }, b: { total_ttc: 120000 },
        diff: { total_ttc: { a: 100000, b: 120000 } },
      },
    })
    mount()

    fireEvent.change(screen.getByLabelText(/Devis A/i), { target: { value: '1' } })
    fireEvent.change(screen.getByLabelText(/Devis B/i), { target: { value: '2' } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Comparer$/i })[0])

    await waitFor(() => expect(mocks.comparerDevis).toHaveBeenCalledWith('1', '2'))
    expect((await screen.findAllByText('total_ttc')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('100000').length).toBeGreaterThan(0)
    expect(screen.getAllByText('120000').length).toBeGreaterThan(0)
  })
})

describe('ComparateursPage — cash vs financement (PACT36)', () => {
  it('affiche le surcoût de financement renvoyé par le serveur', async () => {
    mocks.comparerFinancement.mockResolvedValueOnce({
      data: {
        cash: { cout_total: 100000, payback_annees: '5.0' },
        financement: { mensualite: 2000, cout_credit: 20000, cout_total: 120000, payback_annees: '6.0' },
        surcout_financement: 20000,
      },
    })
    mount(['/?onglet=financement'])

    fireEvent.change(screen.getByLabelText(/^Montant\s*\*?$/i), { target: { value: '100000' } })
    fireEvent.change(screen.getByLabelText(/Durée \(mois\)/i), { target: { value: '60' } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Comparer$/i })[0])

    await waitFor(() => expect(mocks.comparerFinancement).toHaveBeenCalled())
    expect((await screen.findAllByText(/Surcoût du financement/)).length).toBeGreaterThan(0)
  })
})
