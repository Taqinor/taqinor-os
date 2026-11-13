import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* AERR115 — la liste des visites n'affiche que la réponse de la DERNIÈRE
   demande : « Mes visites » lent + bascule immédiate vers « Toutes » rapide. */

const { getVisites } = vi.hoisted(() => ({ getVisites: vi.fn() }))
vi.mock('../../api/visitesApi', () => ({
  default: { getVisites: (...a) => getVisites(...a) },
}))

import VisitesListPage from './VisitesListPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const visite = (id, nom) => ({
  id, lead_nom: nom, statut: 'en_cours', complet: false, manquants_count: 1,
})

describe('VisitesListPage — AERR115', () => {
  it('réponses dans le désordre : la dernière demande gagne', async () => {
    let resoudreMine
    getVisites
      .mockImplementationOnce(() => new Promise((r) => { resoudreMine = r }))
      .mockResolvedValueOnce({ data: { results: [visite(2, 'Visite Toutes')] } })
    render(<MemoryRouter><VisitesListPage /></MemoryRouter>)
    await waitFor(() => expect(getVisites).toHaveBeenCalledTimes(1))
    expect(getVisites.mock.calls[0][0]).toMatchObject({ mine: 1 })

    fireEvent.click(screen.getByRole('radio', { name: 'Toutes' }))
    expect(await screen.findByText('Visite Toutes')).toBeInTheDocument()

    // La réponse lente de « Mes visites » arrive APRÈS : ignorée.
    await act(async () => { resoudreMine({ data: { results: [visite(1, 'Visite Mine')] } }) })
    expect(screen.getByText('Visite Toutes')).toBeInTheDocument()
    expect(screen.queryByText('Visite Mine')).not.toBeInTheDocument()
  })
})
