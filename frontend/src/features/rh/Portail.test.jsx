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
      // ZRH13 / XRH28 — allocations self-service + annuaire interne.
      getMesAllocations: vi.fn(emptyList),
      getAnnuaire: vi.fn(emptyList),
      demanderConge: vi.fn(),
      demanderAllocation: vi.fn(),
      declarerFrais: vi.fn(),
      demanderAttestation: vi.fn(),
      telechargerDemandeUrl: vi.fn((id) => `/rh/portail/${id}/mes-demandes-telecharger/`),
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

  it('soumet une demande d’attestation avec les champs réels du serveur (PACT155)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.demanderAttestation.mockResolvedValueOnce({ data: { id: 1 } })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('radio', { name: 'Mes demandes' }))
    fireEvent.click(screen.getByRole('button', { name: 'Demander une attestation' }))
    fireEvent.change(screen.getByLabelText('Type de document'), { target: { value: 'attestation_domiciliation' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer la demande' }))

    // DemandeRHSerializer (backend/django_core/apps/rh/serializers.py) n'accepte
    // que `type`/`message` — jamais `type_demande`/`motif`.
    await waitFor(() => expect(rhApi.demanderAttestation).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'attestation_domiciliation', message: '' }),
    ))
    expect(rhApi.demanderAttestation).toHaveBeenCalledWith(
      expect.not.objectContaining({ type_demande: expect.anything() }),
    )
  })

  it('affiche le libellé serveur `type_display` dans la liste des demandes (PACT155)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.getMesDemandes.mockResolvedValueOnce({
      data: [{
        id: 5,
        type: 'attestation_domiciliation',
        type_display: 'Attestation de domiciliation',
        statut: 'soumise',
        statut_display: 'Soumise',
        date_creation: '2026-08-01',
      }],
    })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('radio', { name: 'Mes demandes' }))
    expect(await screen.findByText('Attestation de domiciliation')).toBeInTheDocument()
  })

  it('liste l’annuaire interne et le filtre côté client (XRH28)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.getAnnuaire.mockResolvedValueOnce({
      data: [
        { id: 1, nom: 'Bennani', prenom: 'Youssef', poste_nom: 'Technicien', departement_nom: 'Chantier' },
        { id: 2, nom: 'Cherkaoui', prenom: 'Nadia', poste_nom: 'Comptable', departement_nom: 'Finance' },
      ],
    })
    renderPortail()
    await screen.findByText('Mon portail RH')

    fireEvent.click(screen.getByRole('radio', { name: 'Annuaire' }))
    expect(await screen.findByText('Bennani Youssef')).toBeInTheDocument()
    expect(screen.getByText('Cherkaoui Nadia')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Rechercher'), { target: { value: 'comptable' } })
    await waitFor(() => expect(screen.queryByText('Bennani Youssef')).not.toBeInTheDocument())
    expect(screen.getByText('Cherkaoui Nadia')).toBeInTheDocument()
  })

  it('affiche mes demandes d’allocation dans l’onglet congés (ZRH13)', async () => {
    rhApi.getMesInfos.mockResolvedValueOnce({ data: { nom: 'Alaoui', prenom: 'Sara' } })
    rhApi.getMesAllocations.mockResolvedValueOnce({
      data: [{
        id: 9, type_absence_code: 'CP', jours: '3.0',
        statut: 'soumise', statut_display: 'Soumise',
      }],
    })
    renderPortail()
    await screen.findByText('Mon portail RH')

    expect(await screen.findByText('Allocation · CP')).toBeInTheDocument()
    expect(screen.getByText('Soumise')).toBeInTheDocument()
  })
})
