import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* RELANCE FOUNDATION — panneau « Relances du jour » (plan de relance
   structuré multi-touches, crm.RelanceEtape). Liste les étapes dues +
   actions Fait/Sauter. crmApi mocké — aucun appel réseau réel. */

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(() => Promise.resolve({
      data: {
        count: 1,
        results: [{
          id: 7, lead: 42, lead_nom: 'Prospect Chaud', lead_owner_nom: 'Sami',
          ordre: 1, due_date: '2026-08-20', canal: 'appel', libelle: 'Premier rappel',
          statut: 'a_faire', note: '', overdue: true,
        }],
      },
    })),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { id: 7, statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { id: 7, statut: 'sautee' } })),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget (RELANCE FOUNDATION)', () => {
  it('liste les étapes de relance dues avec canal + badge de retard', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Prospect Chaud')).toBeInTheDocument())
    expect(screen.getByText('Appel · Sami')).toBeInTheDocument()
    expect(screen.getByText(/En retard/)).toBeInTheDocument()
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'all' })
  })

  it('le bouton Fait marque l\'étape faite et la retire de la liste', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Prospect Chaud')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Fait/ }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(7, undefined))
    await waitFor(() => expect(screen.queryByText('Prospect Chaud')).not.toBeInTheDocument())
  })

  it('Sauter ouvre une note optionnelle puis confirme', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Prospect Chaud')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    const textarea = screen.getByPlaceholderText(/Note \(optionnelle\)/)
    fireEvent.change(textarea, { target: { value: 'Client en congé' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee)
      .toHaveBeenCalledWith(7, 'Client en congé'))
    await waitFor(() => expect(screen.queryByText('Prospect Chaud')).not.toBeInTheDocument())
  })

  it('Sauter → Annuler referme la note sans appeler l\'API', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Prospect Chaud')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(crmApi.marquerRelanceEtapeSautee).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Sauter/ })).toBeInTheDocument()
  })

  it('affiche un état vide quand aucune relance n\'est due', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    mount()
    await waitFor(() => expect(screen.getByText(/Aucune relance due/)).toBeInTheDocument())
  })

  it('navigue vers le lead au clic sur son nom', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Prospect Chaud')).toBeInTheDocument())
    // Pas d'assertion de route ici (MemoryRouter minimal) — vérifie juste
    // que le bouton existe et reste cliquable sans lever d'erreur.
    expect(() => fireEvent.click(screen.getByText('Prospect Chaud'))).not.toThrow()
  })
})
