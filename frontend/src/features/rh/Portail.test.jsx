import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Portail from './Portail.jsx'

/* UX28 — Portail self-service : smoke de rendu + chemin « aucun dossier ».
   Le portail ne doit jamais planter et doit afficher un état clair quand le
   compte connecté n'a aucun dossier employé lié (404 sur mes-infos).
   WIR35 — les boutons « Nouvelle demande » (congé/allocation/frais) câblent
   `rhApi.demanderConge`/`demanderAllocation`/`declarerFrais` (jusqu'ici
   définis sans appelant). */

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
      getTypesAbsence: vi.fn(emptyList),
      demanderConge: vi.fn(),
      demanderAllocation: vi.fn(),
      declarerFrais: vi.fn(),
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

  it('soumet une demande de congé via rhApi.demanderConge (WIR35)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.getTypesAbsence.mockResolvedValue({ data: [{ id: 3, code: 'CP', libelle: 'Congé payé' }] })
    rhApi.demanderConge.mockResolvedValueOnce({ data: { id: 1 } })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('button', { name: 'Nouvelle demande de congé' }))
    fireEvent.change(screen.getByLabelText('Type d’absence'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-08-01' } })
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-08-05' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))

    await waitFor(() => expect(rhApi.demanderConge).toHaveBeenCalledWith(
      expect.objectContaining({ type_absence: '3', date_debut: '2026-08-01', date_fin: '2026-08-05' }),
    ))
  })

  it('soumet une demande d’allocation via rhApi.demanderAllocation (WIR35)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.getTypesAbsence.mockResolvedValue({ data: [{ id: 3, code: 'CP', libelle: 'Congé payé' }] })
    rhApi.demanderAllocation.mockResolvedValueOnce({ data: { id: 1 } })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('button', { name: 'Demander une allocation' }))
    fireEvent.change(screen.getByLabelText('Type d’absence'), { target: { value: '3' } })
    fireEvent.change(screen.getByLabelText('Jours demandés'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))

    await waitFor(() => expect(rhApi.demanderAllocation).toHaveBeenCalledWith(
      expect.objectContaining({ type_absence: '3', jours: '2' }),
    ))
  })

  it('déclare une note de frais via rhApi.declarerFrais (WIR35)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.declarerFrais.mockResolvedValueOnce({ data: { id: 1 } })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('radio', { name: 'Mes frais' }))
    fireEvent.click(screen.getByRole('button', { name: 'Nouvelle note de frais' }))
    fireEvent.change(screen.getByLabelText('Montant (MAD)'), { target: { value: '150' } })
    fireEvent.change(screen.getByLabelText('Date de la dépense'), { target: { value: '2026-08-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Déclarer la dépense' }))

    await waitFor(() => expect(rhApi.declarerFrais).toHaveBeenCalledWith(
      expect.objectContaining({ montant: '150', date_frais: '2026-08-01' }),
    ))
  })
})
