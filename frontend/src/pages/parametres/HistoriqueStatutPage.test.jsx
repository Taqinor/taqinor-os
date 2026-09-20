import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  getHistoriqueStatut: vi.fn(),
  prefillIncident: vi.fn(),
}))

vi.mock('../../api/statuspageApi', () => ({
  default: {
    getHistoriqueStatut: mocks.getHistoriqueStatut,
    prefillIncident: mocks.prefillIncident,
  },
}))

import HistoriqueStatutPage from './HistoriqueStatutPage'

const LOGS = [
  {
    id: 1, composant: 'API', region: 'eu-west', ancien_statut: 'operational',
    nouveau_statut: 'degraded', created_at: '2026-09-19T10:00:00Z',
  },
  {
    id: 2, composant: 'Base de données', region: '', ancien_statut: '',
    nouveau_statut: 'operational', created_at: '2026-09-18T08:00:00Z',
  },
]

describe('HistoriqueStatutPage (NTOBS33)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getHistoriqueStatut.mockResolvedValue({ data: LOGS })
  })

  it('affiche les changements de statut avec ancien → nouveau', async () => {
    render(<HistoriqueStatutPage />)
    const ligneApi = (await screen.findByText('API')).closest('li')
    expect(within(ligneApi).getByText('Opérationnel')).toBeInTheDocument()
    expect(within(ligneApi).getByText('Dégradé')).toBeInTheDocument()
    expect(screen.getByText('Base de données')).toBeInTheDocument()
    // Deux occurrences d'« Opérationnel » (ancien de la ligne API, nouveau
    // de la ligne « Base de données ») : jamais fusionnées par accident.
    expect(screen.getAllByText('Opérationnel')).toHaveLength(2)
  })

  it('affiche un état vide sans changement détecté', async () => {
    mocks.getHistoriqueStatut.mockResolvedValue({ data: [] })
    render(<HistoriqueStatutPage />)
    expect(await screen.findByText('Aucun changement de statut détecté.')).toBeInTheDocument()
  })

  it('pré-remplit un incident depuis un événement sans en créer un', async () => {
    mocks.prefillIncident.mockResolvedValue({
      data: {
        titre: '', severite: 'majeure', region: 'eu-west',
        composants: ['API'], debute_le: '2026-09-19T10:00:00Z',
      },
    })
    render(<HistoriqueStatutPage />)
    await screen.findByText('API')
    fireEvent.click(screen.getAllByText('Créer un incident depuis cet événement')[0])

    await waitFor(() => expect(mocks.prefillIncident).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Pré-remplissage de l’incident')).toBeInTheDocument()
    expect(screen.getByText('Majeure')).toBeInTheDocument()
    expect(screen.getByText('API', { selector: 'dd' })).toBeInTheDocument()
  })
})
