import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT37 — Codes promotionnels (FG209). Un code expiré doit rester VISIBLE
   dans la liste avec son état affiché — jamais filtré silencieusement (Done=
   de PACT37). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('../../../api/comptaApi', () => ({
  default: { codesPromotion: { list: mocks.list } },
}))

import CodesPromotionPage from './CodesPromotionPage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><CodesPromotionPage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('CodesPromotionPage — code expiré resté visible (PACT37)', () => {
  it('affiche un code expiré avec son état, jamais filtré', async () => {
    mocks.list.mockResolvedValue({
      data: [{ id: 1, code: 'PROMO2024', libelle: 'Solde 2024', taux_remise: '10.00',
        date_debut: '2024-01-01', date_fin: '2024-12-31', actif: true,
        nb_utilisations: 12, ca_genere: '80000.00', date_creation: '2024-01-01' }],
    })
    mount()

    expect((await screen.findAllByText('PROMO2024')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Expiré')).length).toBeGreaterThan(0)
  })
})
