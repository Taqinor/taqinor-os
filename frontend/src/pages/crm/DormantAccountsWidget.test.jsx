import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* NTCRM15 — widget dashboard « Comptes à réactiver » (comptes dormants,
   NTCRM14). Liste + bouton one-click de relance. crmApi mocké. */

vi.mock('../../api/crmApi', () => ({
  default: {
    getComptesDormants: vi.fn(() => Promise.resolve({
      data: {
        seuil: 90,
        count: 1,
        results: [{ id: 42, nom: 'Client froid', derniere_activite: '2026-01-01', jours_inactivite: 100 }],
      },
    })),
    relancerDormance: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  },
}))

import crmApi from '../../api/crmApi'
import DormantAccountsWidget from './DormantAccountsWidget'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <DormantAccountsWidget />
    </MemoryRouter>,
  )
}

describe('DormantAccountsWidget (NTCRM15)', () => {
  it('liste les comptes dormants réels', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Client froid')).toBeInTheDocument())
    expect(screen.getByText('100 j sans activité')).toBeInTheDocument()
  })

  it('le bouton crée une activité de relance', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Client froid')).toBeInTheDocument())
    fireEvent.click(screen.getByText('Créer une relance'))
    await waitFor(() => expect(crmApi.relancerDormance).toHaveBeenCalledWith(42))
    await waitFor(() => expect(screen.getByText('Relancé')).toBeInTheDocument())
  })

  it('affiche un état vide quand aucun compte n\'est dormant', async () => {
    crmApi.getComptesDormants.mockResolvedValueOnce({ data: { seuil: 90, count: 0, results: [] } })
    mount()
    await waitFor(() => expect(screen.getByText(/Aucun compte dormant/)).toBeInTheDocument())
  })
})
