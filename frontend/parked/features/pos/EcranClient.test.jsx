import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* NTRET31 — Écran client (customer-facing display), route
   /pos/ecran-client/:session_id. LECTURE SEULE : reflète le panier poussé
   par la caisse via un polling léger (±2s), aucune action exposée. */

const { getPanierCourant } = vi.hoisted(() => ({
  getPanierCourant: vi.fn(),
}))

vi.mock('../../api/posApi', () => ({
  default: { getPanierCourant: (...a) => getPanierCourant(...a) },
}))

import EcranClient from './EcranClient'

const renderScreen = (sessionId = '42') => render(
  <MemoryRouter initialEntries={[`/pos/ecran-client/${sessionId}`]}>
    <Routes>
      <Route path="/pos/ecran-client/:session_id" element={<EcranClient />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  getPanierCourant.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('EcranClient', () => {
  it('affiche un état vide tant qu’aucune ligne n’est poussée', async () => {
    getPanierCourant.mockResolvedValue({ data: { panier: null } })
    renderScreen()
    await waitFor(() => expect(getPanierCourant).toHaveBeenCalledWith('42'))
    expect(await screen.findByText('Panier vide')).toBeTruthy()
  })

  it('affiche les lignes et le total du panier poussé par la caisse', async () => {
    getPanierCourant.mockResolvedValue({
      data: {
        panier: {
          lignes: [{ nom: 'Câble solaire', quantite: 2, prix_ttc: 50 }],
          total: 100,
        },
      },
    })
    renderScreen()
    expect(await screen.findByText(/Câble solaire/)).toBeTruthy()
    const total = await screen.findByTestId('ecran-client-total')
    expect(total.textContent).toMatch(/100/)
  })

  it('aucune action (bouton/lien) n’est jamais rendue — écran lecture seule', async () => {
    getPanierCourant.mockResolvedValue({
      data: { panier: { lignes: [{ nom: 'X', quantite: 1, prix_ttc: 10 }], total: 10 } },
    })
    renderScreen()
    await screen.findByTestId('ecran-client-total')
    expect(screen.queryAllByRole('button')).toHaveLength(0)
    expect(screen.queryAllByRole('link')).toHaveLength(0)
  })

  it('re-sonde le panier périodiquement (±2s)', async () => {
    getPanierCourant.mockResolvedValue({ data: { panier: null } })
    renderScreen()
    await waitFor(() => expect(getPanierCourant).toHaveBeenCalledTimes(1))
    await vi.advanceTimersByTimeAsync(2000)
    await waitFor(() => expect(getPanierCourant).toHaveBeenCalledTimes(2))
  })

  it('une erreur réseau affiche un message discret sans planter l’écran', async () => {
    getPanierCourant.mockRejectedValue(new Error('offline'))
    renderScreen()
    expect(await screen.findByText(/Connexion à la caisse en attente/)).toBeTruthy()
  })
})
