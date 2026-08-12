import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import DemandesAllocation from './DemandesAllocation.jsx'

/* PACT83 — Demandes d'allocation de congés. Valider une demande doit mettre à
   jour le solde affiché À PARTIR DE LA RÉPONSE SERVEUR (rechargement de
   getSoldesConge), jamais un recalcul côté client. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getDemandesAllocation: vi.fn(() => Promise.resolve({
        data: [{ id: 5, employe: 9, employe_nom: 'Bennani Youssef', type_absence_code: 'RTT', jours: 2, statut: 'soumise', statut_display: 'Soumise' }],
      })),
      getSoldesConge: vi.fn(empty),
      validerDemandeAllocation: vi.fn(),
      refuserDemandeAllocation: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DemandesAllocation />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DemandesAllocation (PACT83)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et liste les demandes soumises', async () => {
    renderScreen()
    expect((await screen.findAllByText('Demandes d’allocation de congés')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Bennani Youssef')).length).toBeGreaterThan(0)
  })

  it('valide une demande via rhApi.validerDemandeAllocation puis recharge les soldes', async () => {
    rhApi.validerDemandeAllocation.mockResolvedValueOnce({ data: { id: 5, statut: 'validee' } })
    renderScreen()
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click((await screen.findAllByRole('button', { name: 'Valider' }))[0])

    await waitFor(() => expect(rhApi.validerDemandeAllocation).toHaveBeenCalledWith(5))
    await waitFor(() => expect(rhApi.getSoldesConge).toHaveBeenCalledTimes(2))
  })
})
