import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import DemandesRh from './DemandesRh.jsx'

/* PACT84 — Guichet des demandes RH (attestations). Le bouton « Traiter » n'est
   JAMAIS masqué côté client selon la permission `salaires_voir` — c'est le
   serveur qui refuse (403) le cas échéant ; ce test vérifie que le bouton est
   toujours proposé et que l'appel serveur est déclenché tel quel. */

vi.mock('../../api/rhApi', () => ({
  default: {
    getDemandesRh: vi.fn(() => Promise.resolve({
      data: [{
        id: 7, employe: 9, employe_nom: 'Bennani Youssef',
        type: 'attestation_salaire', type_display: 'Attestation de salaire',
        statut: 'soumise', statut_display: 'Soumise',
      }],
    })),
    traiterDemandeRh: vi.fn(),
    refuserDemandeRh: vi.fn(),
  },
}))

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <DemandesRh />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('DemandesRh (PACT84)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et propose Traiter sans filtrage de permission côté client', async () => {
    renderScreen()
    expect((await screen.findAllByText('Demandes RH (attestations)')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Bennani Youssef')).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Traiter' })[0]).toBeInTheDocument()
  })

  it('traite une demande via rhApi.traiterDemandeRh et recharge la liste', async () => {
    rhApi.traiterDemandeRh.mockResolvedValueOnce({ data: { id: 7, statut: 'traitee' } })
    renderScreen()
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click(screen.getAllByRole('button', { name: 'Traiter' })[0])

    await waitFor(() => expect(rhApi.traiterDemandeRh).toHaveBeenCalledWith(7))
    await waitFor(() => expect(rhApi.getDemandesRh).toHaveBeenCalledTimes(2))
  })

  it('relaie l’échec serveur (403 salaires_voir) sans planter l’écran', async () => {
    rhApi.traiterDemandeRh.mockRejectedValueOnce({
      response: { data: { detail: "Vous n'avez pas la permission de traiter une attestation de salaire." } },
    })
    renderScreen()
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click(screen.getAllByRole('button', { name: 'Traiter' })[0])

    await waitFor(() => expect(rhApi.traiterDemandeRh).toHaveBeenCalledWith(7))
    // Pas de rechargement après un échec : la ligne reste « soumise ».
    expect(rhApi.getDemandesRh).toHaveBeenCalledTimes(1)
    expect((await screen.findAllByText('Bennani Youssef')).length).toBeGreaterThan(0)
  })
})
