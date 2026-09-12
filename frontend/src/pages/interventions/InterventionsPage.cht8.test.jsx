// CHT8 — Page interventions : deep-link ?id= ouvre directement la fiche de
// l'intervention ciblée (même patron ?id= que InstallationsPage.jsx —
// prérequis des liens de notification CHT9, règle WIR176 : jamais un
// paramètre qu'aucune page ne lit).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import InterventionsPage from './InterventionsPage'

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInterventions: vi.fn(),
    updateIntervention: vi.fn(),
    getInterventionHistorique: vi.fn(),
    noterIntervention: vi.fn(),
  },
}))
vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: vi.fn(),
  },
}))

import installationsApi from '../../api/installationsApi'
import crmApi from '../../api/crmApi'

const ITEMS = [
  {
    id: 101,
    installation_reference: 'CH-101',
    client_nom: 'Client Cent Un',
    type_intervention: 'pose',
    statut: 'a_preparer',
  },
  {
    id: 202,
    installation_reference: 'CH-202',
    client_nom: 'Client Deux Cent Deux',
    type_intervention: 'controle',
    statut: 'prete',
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  // Vue liste (déterministe) plutôt que le kanban @dnd-kit par défaut — sans
  // incidence sur le comportement du lien profond testé ici.
  try { localStorage.setItem('taqinor.interventions.view', 'liste') } catch { /* indisponible */ }
  installationsApi.getInterventions.mockResolvedValue({ data: ITEMS })
  installationsApi.getInterventionHistorique.mockResolvedValue({ data: [] })
  crmApi.getAssignableUsers.mockResolvedValue({ data: [] })
})

describe('InterventionsPage — CHT8 deep-link ?id=', () => {
  it('?id=<pk> ouvre automatiquement la fiche de la bonne intervention', async () => {
    render(
      <MemoryRouter initialEntries={['/interventions?id=202']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    // La liste charge d'abord (deux interventions).
    // Le nom du client apparaît sur la carte kanban ET dans la fiche ouverte
  // par le deep-link : getAllByText, jamais getByText (strict-mode RTL).
  await waitFor(() => expect(
    screen.getAllByText('Client Deux Cent Deux').length).toBeGreaterThanOrEqual(1))

    // La fiche (Sheet) s'ouvre SANS clic, sur l'intervention #202 désignée par
    // ?id= — jamais sur #101 (première de la liste).
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/CH-202/)).toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).toHaveBeenCalledWith(202)
  })

  it("sans ?id=, aucune fiche ne s'ouvre automatiquement", async () => {
    render(
      <MemoryRouter initialEntries={['/interventions']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    await waitFor(() => expect(screen.getByText('Client Cent Un')).toBeInTheDocument())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).not.toHaveBeenCalled()
  })

  it('?id= introuvable affiche un EmptyState inline (jamais une page blanche)', async () => {
    render(
      <MemoryRouter initialEntries={['/interventions?id=999']}>
        <InterventionsPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Intervention introuvable')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(installationsApi.getInterventionHistorique).not.toHaveBeenCalled()
  })
})
