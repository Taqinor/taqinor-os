import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Competences from './Competences.jsx'

/* UX25 — Compétences, habilitations & formation. WIR36 — les boutons
   « Nouvelle évaluation »/« Nouvelle habilitation »/« Nouvelle certification »/
   « Nouvelle visite »/« Nouveau quiz » câblent les wrappers d'écriture ajoutés
   à `rhApi.js` (ViewSets full CRUD jusqu'ici sans appelant côté écriture). */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getCompetencesEmploye: vi.fn(empty),
      getHabilitations: vi.fn(empty),
      getCertifications: vi.fn(empty),
      getVisitesMedicales: vi.fn(empty),
      getSessionsFormation: vi.fn(empty),
      getBesoinsFormation: vi.fn(empty),
      getQuizFormation: vi.fn(empty),
      getArbreDepartements: vi.fn(empty),
      // ZRH10 — rapport d'évolution des compétences.
      getEvolutionCompetences: vi.fn(empty),
      // ZRH17 — recherche « qui maîtrise X au niveau >= N ? ».
      getEmployesParCompetence: vi.fn(empty),
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      getCompetences: vi.fn(() => Promise.resolve({ data: [{ id: 4, code: 'PV1', libelle: 'Installation PV' }] })),
      createCompetenceEmploye: vi.fn(),
      createHabilitation: vi.fn(),
      createCertification: vi.fn(),
      createVisiteMedicale: vi.fn(),
      createQuizFormation: vi.fn(),
      updateQuizFormation: vi.fn(),
      deleteQuizFormation: vi.fn(),
      // WIR239 — « Marquer satisfait » un besoin de formation.
      satisfaireBesoinFormation: vi.fn(),
    },
  }
})

function renderCompetences() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Competences />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Competences — saisie manuelle (WIR36)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et propose l’onglet Visites médicales', async () => {
    renderCompetences()
    expect(await screen.findByText('Compétences & habilitations')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Visites médicales' })).toBeInTheDocument()
  })

  it('évalue une compétence via rhApi.createCompetenceEmploye', async () => {
    rhApi.createCompetenceEmploye.mockResolvedValueOnce({ data: { id: 1 } })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle évaluation/ }))
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.change(screen.getByLabelText('Compétence'), { target: { value: '4' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createCompetenceEmploye).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', competence: '4' }),
    ))
  })

  it('crée une habilitation via rhApi.createHabilitation', async () => {
    rhApi.createHabilitation.mockResolvedValueOnce({ data: { id: 1 } })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')
    fireEvent.click(screen.getByRole('radio', { name: 'Habilitations' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle habilitation/ }))
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createHabilitation).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9' }),
    ))
  })

  it('crée une visite médicale via rhApi.createVisiteMedicale', async () => {
    rhApi.createVisiteMedicale.mockResolvedValueOnce({ data: { id: 1 } })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')
    fireEvent.click(screen.getByRole('radio', { name: 'Visites médicales' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle visite/ }))
    fireEvent.change(screen.getByLabelText('Employé'), { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(rhApi.createVisiteMedicale).toHaveBeenCalledWith(
      expect.objectContaining({ employe: '9', aptitude: 'apte' }),
    ))
  })

  it('crée un quiz via rhApi.createQuizFormation', async () => {
    rhApi.createQuizFormation.mockResolvedValueOnce({ data: { id: 1 } })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')
    fireEvent.click(screen.getByRole('radio', { name: 'Quiz' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau quiz/ }))
    fireEvent.change(screen.getByLabelText('Intitulé'), { target: { value: 'Sécurité chantier' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le quiz' }))

    await waitFor(() => expect(rhApi.createQuizFormation).toHaveBeenCalledWith(
      expect.objectContaining({ intitule: 'Sécurité chantier', score_reussite: 80 }),
    ))
  })
  it('affiche le rapport d’évolution des compétences (ZRH10)', async () => {
    rhApi.getEvolutionCompetences.mockResolvedValueOnce({
      data: [{
        employe_id: 9, employe_nom: 'Bennani Youssef',
        competence_id: 4, competence_libelle: 'Installation PV',
        ancien_niveau: 1, nouveau_niveau: 3, progression: true,
        source: 'manuelle', date: '2026-08-01',
      }],
    })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')
    fireEvent.click(screen.getByRole('radio', { name: 'Évolution' }))

    expect((await screen.findAllByText('Installation PV')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Progression').length).toBeGreaterThan(0)
  })

  it('cherche les employés qualifiés sur une compétence (ZRH17)', async () => {
    rhApi.getEmployesParCompetence.mockResolvedValueOnce({
      data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }],
    })
    renderCompetences()
    await screen.findByText('Compétences & habilitations')

    fireEvent.change(await screen.findByLabelText('Compétence recherchée'), { target: { value: '4' } })
    fireEvent.change(screen.getByLabelText('Niveau minimum'), { target: { value: '2' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(rhApi.getEmployesParCompetence).toHaveBeenCalledWith(
      '4', { niveau_min: '2' },
    ))
    expect(await screen.findByText(/Bennani Youssef/)).toBeInTheDocument()
  })
})

/* WIR239 — l'@action `satisfaire` d'un besoin de formation n'avait aucun
   appelant : un besoin restait « exprimé » à vie. Le garde-fou serveur
   (session liée non réalisée → 400 { session_liee }) doit s'afficher TEL QUEL. */
describe('Competences — WIR239 : besoin de formation « satisfait »', () => {
  const BESOIN = {
    id: 8, employe: 9, employe_nom: 'Bennani Youssef', theme: 'Travail en hauteur',
    priorite: 'haute', priorite_display: 'Haute',
    statut: 'exprime', statut_display: 'Exprimé',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    rhApi.getBesoinsFormation.mockResolvedValue({ data: [BESOIN] })
  })

  const ouvrirFormation = async () => {
    renderCompetences()
    await screen.findByText('Compétences & habilitations')
    fireEvent.click(screen.getByRole('radio', { name: 'Formation' }))
    await screen.findAllByText('Travail en hauteur')
  }

  it('marque le besoin satisfait via rhApi.satisfaireBesoinFormation', async () => {
    rhApi.satisfaireBesoinFormation.mockResolvedValueOnce({ data: { ...BESOIN, statut: 'satisfait' } })
    await ouvrirFormation()

    fireEvent.click((await screen.findAllByRole('button', { name: 'Marquer satisfait' }))[0])
    await waitFor(() => expect(rhApi.satisfaireBesoinFormation).toHaveBeenCalledWith(8))
  })

  it('affiche TEL QUEL le 400 « session liée non réalisée »', async () => {
    rhApi.satisfaireBesoinFormation.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { session_liee: 'La session liée doit être réalisée pour satisfaire le besoin.' },
      },
    })
    await ouvrirFormation()

    fireEvent.click((await screen.findAllByRole('button', { name: 'Marquer satisfait' }))[0])
    expect(await screen.findByText(
      'La session liée doit être réalisée pour satisfaire le besoin.',
    )).toBeInTheDocument()
  })
})
