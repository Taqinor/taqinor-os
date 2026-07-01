import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Portail from './Portail.jsx'

/* UX28 — Portail self-service : smoke de rendu + chemin « aucun dossier ».
   Le portail ne doit jamais planter et doit afficher un état clair quand le
   compte connecté n'a aucun dossier employé lié (404 sur mes-infos). */

vi.mock('../../api/rhApi', () => ({
  default: {
    getMesInfos: vi.fn(),
    getMesSoldes: vi.fn(() => Promise.resolve({ data: [] })),
    getMesConges: vi.fn(() => Promise.resolve({ data: [] })),
    getMesFrais: vi.fn(() => Promise.resolve({ data: [] })),
    getOrdresMission: vi.fn(() => Promise.resolve({ data: [] })),
    getMesBulletins: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

function renderPortail() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Portail />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Portail RH (UX28)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche l’état « aucun dossier » quand mes-infos renvoie 404', async () => {
    rhApi.getMesInfos.mockRejectedValueOnce({ response: { status: 404 } })
    renderPortail()
    expect(
      await screen.findByText('Aucun dossier employé lié à votre compte'),
    ).toBeInTheDocument()
  })

  it('rend le tableau de bord personnel quand un dossier existe', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({
      data: { nom: 'Alaoui', prenom: 'Sara', poste: 'Technicienne' },
    })
    renderPortail()
    expect(await screen.findByText('Mon portail RH')).toBeInTheDocument()
    expect(screen.getByText(/Solde congés/)).toBeInTheDocument()
  })
})
