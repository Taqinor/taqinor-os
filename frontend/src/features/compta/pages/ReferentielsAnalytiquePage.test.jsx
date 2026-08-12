import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT31 — Référentiels comptables parallèles (NTFIN13) et analytique
   multi-axes (NTFIN15-17). Un ajustement GAAP posté doit créer une écriture
   dans le référentiel PARALLÈLE — jamais dans le plan comptable principal
   (apps/compta/services.poster_ajustement_gaap). */

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
  referentiels: vi.fn(),
  seed: vi.fn(),
  ajustements: vi.fn(),
  poster: vi.fn(),
  axes: vi.fn(),
  imputations: vi.fn(),
  centres: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    referentielsComptables: { list: mocks.referentiels, seed: mocks.seed },
    ajustementsGaap: { list: mocks.ajustements, poster: mocks.poster },
    axesAnalytiques: { list: mocks.axes },
    imputationsAxes: { list: mocks.imputations },
    centresCout: { list: mocks.centres },
  },
}))

import ReferentielsAnalytiquePage from './ReferentielsAnalytiquePage.jsx'

function mount(initialEntries = ['/']) {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={initialEntries}>
        <ThemeProvider><ReferentielsAnalytiquePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('ReferentielsAnalytiquePage — référentiels (PACT31)', () => {
  it('liste les référentiels et propose l’amorçage CGNC', async () => {
    mocks.referentiels.mockResolvedValue({
      data: [{ id: 1, code: 'IFRS', code_display: 'IFRS', libelle: 'Livre IFRS',
        devise_fonctionnelle: 'MAD', actif: true, est_principal: false }],
    })
    mount()
    expect((await screen.findAllByText('Livre IFRS')).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: /Amorcer le CGNC/i })[0]).toBeInTheDocument()
  })
})

describe('ReferentielsAnalytiquePage — ajustements GAAP (PACT31)', () => {
  it('poste un ajustement rattaché au référentiel choisi (jamais au plan principal)', async () => {
    mocks.referentiels.mockResolvedValue({
      data: [{ id: 1, code: 'IFRS', code_display: 'IFRS', libelle: 'Livre IFRS' }],
    })
    mocks.ajustements.mockResolvedValue({ data: [] })
    mocks.poster.mockResolvedValueOnce({ data: { id: 5, referentiel: 1 } })
    mount(['/?onglet=ajustements'])

    fireEvent.click((await screen.findAllByRole('button', { name: /Poster un ajustement/i }))[0])
    // Combobox = un bouton `role="combobox"` qui ouvre une liste d'options
    // (jamais un <select> natif) — cf. frontend/src/ui/Combobox.jsx.
    fireEvent.click(await screen.findByRole('combobox'))
    fireEvent.click(await screen.findByRole('option', { name: /IFRS — Livre IFRS/i }))
    fireEvent.change(screen.getByLabelText(/^Motif\s*\*?$/i), { target: { value: 'Retraitement leasing' } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Poster$/i })[0])

    await waitFor(() => expect(mocks.poster).toHaveBeenCalled())
    expect(mocks.poster.mock.calls[0][0].referentiel).toBe(1)
  })
})
