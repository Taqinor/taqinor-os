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
      getEmployes: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Bennani', prenom: 'Youssef' }] })),
      getCompetences: vi.fn(() => Promise.resolve({ data: [{ id: 4, code: 'PV1', libelle: 'Installation PV' }] })),
      createCompetenceEmploye: vi.fn(),
      createHabilitation: vi.fn(),
      createCertification: vi.fn(),
      createVisiteMedicale: vi.fn(),
      createQuizFormation: vi.fn(),
      updateQuizFormation: vi.fn(),
      deleteQuizFormation: vi.fn(),
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
})
