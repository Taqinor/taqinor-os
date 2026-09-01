import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR237 — La suspension d'un abonnement de supervision était SANS RETOUR
   depuis l'écran : aucun bouton ne le ramenait à l'état actif, donc il ne
   redevenait jamais facturable. Le bouton « Reprendre » n'apparaît QUE sur une
   ligne suspendue (jamais sur un abonnement actif ou résilié) et appelle
   `reactiverAbonnement`. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getAbonnements: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, client_id: 42, periodicite: 'mensuel', montant: '500.00', statut: 'actif', prochaine_echeance: '2026-08-01' },
        { id: 2, client_id: 42, periodicite: 'mensuel', montant: '300.00', statut: 'suspendu', prochaine_echeance: '2026-08-01' },
        { id: 3, client_id: 42, periodicite: 'annuel', montant: '900.00', statut: 'resilie', prochaine_echeance: null },
      ],
    })),
    createAbonnement: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
    facturerAbonnement: vi.fn(() => Promise.resolve({
      data: {
        facture_id: 9, reference: 'FAC-2026-009', montant_ttc: '600.00',
        // WIR237 — l'échéance avancée revient dans la réponse.
        prochaine_echeance: '2026-09-01',
      },
    })),
    suspendreAbonnement: vi.fn(() => Promise.resolve({ data: {} })),
    reactiverAbonnement: vi.fn(() => Promise.resolve({ data: {} })),
    resilierAbonnement: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [{ id: 42, nom: 'Amrani Solar' }] })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import AbonnementsPage from './AbonnementsPage'

describe('AbonnementsPage (WIR237 — reprise d’un abonnement suspendu)', () => {
  it('affiche « Reprendre » sur la ligne suspendue et appelle reactiverAbonnement', async () => {
    const user = userEvent.setup()
    renderPage(<AbonnementsPage />)
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))

    // DataTable rend bureau + mobile : une paire de boutons par ligne.
    const boutons = await screen.findAllByRole('button', { name: 'Reprendre' })
    expect(boutons.length).toBeGreaterThan(0)
    await user.click(boutons[0])
    await waitFor(() => expect(monitoringApi.reactiverAbonnement).toHaveBeenCalledWith(2))
  })

  it('« Reprendre » ne s’affiche QUE sur la ligne suspendue', async () => {
    renderPage(<AbonnementsPage />)
    await waitFor(() => expect(screen.getAllByText('Amrani Solar').length).toBeGreaterThan(0))
    // DataTable rend chaque ligne DEUX fois (bureau + cartes mobiles) : on
    // raisonne en PROPORTIONS, jamais sur un compte absolu qui dépendrait de
    // ce détail de rendu. 3 lignes : 1 active, 1 suspendue, 1 résiliée.
    const actives = screen.getAllByRole('button', { name: 'Facturer la période due' }).length
    expect(actives).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Suspendre' })).toHaveLength(actives)
    expect(screen.getAllByRole('button', { name: 'Reprendre' })).toHaveLength(actives)
    // « Résilier » : toutes les lignes SAUF la résiliée → deux fois plus.
    expect(screen.getAllByRole('button', { name: 'Résilier' })).toHaveLength(actives * 2)
  })
})
