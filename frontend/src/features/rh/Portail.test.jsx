import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Portail from './Portail.jsx'

/* UX28 — Portail self-service : smoke de rendu + chemin « aucun dossier ».
   Le portail ne doit jamais planter et doit afficher un état clair quand le
   compte connecté n'a aucun dossier employé lié (404 sur mes-infos). */

vi.mock('../../api/rhApi', () => {
  const emptyList = () => Promise.resolve({ data: [] })
  return {
    default: {
      getMesInfos: vi.fn(),
      getMesSoldes: vi.fn(emptyList),
      getMesConges: vi.fn(emptyList),
      getMesFrais: vi.fn(emptyList),
      getOrdresMission: vi.fn(emptyList),
      getMesBulletins: vi.fn(emptyList),
      getMesDemandes: vi.fn(emptyList),
      getMesEpi: vi.fn(emptyList),
      getMesHabilitations: vi.fn(emptyList),
      getQuizDisponibles: vi.fn(emptyList),
      getMesTentativesQuiz: vi.fn(emptyList),
      getMesEvaluations: vi.fn(emptyList),
      getCampagnesPulse: vi.fn(emptyList),
    },
  }
})

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
