import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'

/* PACT35 — Balance d'ouverture (COMPTA3). `services.importer_balance_ouverture`
   est IDEMPOTENT par exercice : un second import renvoie {ok:true,
   deja_importee:true} — jamais une erreur, mais l'écran doit le dire
   distinctement d'un import neuf (jamais un second succès muet). Un fichier
   invalide renvoie {detail, erreurs:[{ligne, raison}]} en 400 — jamais un 500. */

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
  exercices: vi.fn(),
  importer: vi.fn(),
}))

vi.mock('../../../api/comptaApi', () => ({
  default: {
    exercices: { list: mocks.exercices },
    balanceOuverture: { gabarit: vi.fn(), importer: mocks.importer },
    downloadBlob: vi.fn(),
  },
}))

import BalanceOuverturePage from './BalanceOuverturePage.jsx'

function mount() {
  const store = configureStore({
    reducer: { auth: () => ({ role: 'admin', role_nom: null, permissions: [] }) },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider><BalanceOuverturePage /></ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

describe('BalanceOuverturePage — import idempotent (PACT35)', () => {
  it("distingue un second import (déjà importée) d'un import neuf", async () => {
    mocks.exercices.mockResolvedValue({ data: [{ id: 1, libelle: 'Exercice 2026' }] })
    mocks.importer.mockResolvedValueOnce({
      data: { ok: true, deja_importee: true, ecriture_id: 9, reference: 'AN-OUV-1', total: '50000.00' },
    })
    mount()

    fireEvent.click(await screen.findByRole('combobox'))
    fireEvent.click(await screen.findByRole('option', { name: /Exercice 2026/i }))
    const input = screen.getByLabelText(/Fichier CSV/i)
    const fichier = new File(['numero,libelle,debit,credit\n1111,Caisse,100,0'], 'balance.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [fichier] } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Importer$/i })[0])

    await waitFor(() => expect(mocks.importer).toHaveBeenCalledWith(fichier, 1))
    expect(await screen.findByText(
      /déjà été importée pour cet exercice — écriture existante : AN-OUV-1/,
    )).toBeInTheDocument()
  })

  it('affiche le détail ligne à ligne sur un fichier invalide (jamais un 500)', async () => {
    mocks.exercices.mockResolvedValue({ data: [{ id: 1, libelle: 'Exercice 2026' }] })
    mocks.importer.mockRejectedValueOnce({
      response: { data: { detail: 'Fichier invalide.', erreurs: [{ ligne: 3, raison: 'compte inconnu' }] } },
    })
    mount()

    fireEvent.click(await screen.findByRole('combobox'))
    fireEvent.click(await screen.findByRole('option', { name: /Exercice 2026/i }))
    const input = screen.getByLabelText(/Fichier CSV/i)
    const fichier = new File(['x'], 'balance.csv', { type: 'text/csv' })
    fireEvent.change(input, { target: { files: [fichier] } })
    fireEvent.click(screen.getAllByRole('button', { name: /^Importer$/i })[0])

    expect((await screen.findAllByText('compte inconnu')).length).toBeGreaterThan(0)
  })
})
