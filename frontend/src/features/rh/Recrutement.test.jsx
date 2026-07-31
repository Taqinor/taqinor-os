import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import Recrutement from './Recrutement.jsx'

/* XRH17-23 / ZRH7-9 — ATS complet : smoke de rendu + présence des nouveaux
   onglets (Vivier / Statistiques / Gabarits) branchés sur les endpoints ATS.
   Le module ne doit jamais planter au chargement, même quand tout est vide.
   WIR34 — « Nouveau candidat » et « Nouveau modèle » câblent respectivement
   `rhApi.createCandidature` et `rhApi.createModeleEvaluation` (jusqu'ici
   définis sans appelant).
   WIR131 — l'action de ligne « Feedback 360° » (onglet Évaluations) câble
   `rhApi.createRetourFeedback360` (invitation d'un répondant) et
   `rhApi.getSyntheseFeedback360` (synthèse agrégée), tous deux définis dans
   rhApi.js sans aucun appelant jusqu'ici. */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getEpiCatalogue: vi.fn(empty),
      getDotationsEpi: vi.fn(empty),
      getOuverturesPoste: vi.fn(empty),
      getCandidatures: vi.fn(empty),
      getVivier: vi.fn(empty),
      getRecrutementStatistiques: vi.fn(() => Promise.resolve({ data: {} })),
      getGabaritsEmailRecrutement: vi.fn(empty),
      getModelesEvaluation: vi.fn(empty),
      getCampagnesEvaluation: vi.fn(empty),
      getEvaluationsEmploye: vi.fn(empty),
      getSanctions: vi.fn(empty),
      createCandidature: vi.fn(),
      createModeleEvaluation: vi.fn(),
      // WIR131 — feedback 360°.
      getRetoursFeedback360: vi.fn(empty),
      getSyntheseFeedback360: vi.fn(() => Promise.resolve({
        data: { nb_invites: 0, nb_soumis: 0, anonymise: true, moyennes_par_critere: {} },
      })),
      getEmployes: vi.fn(() => Promise.resolve({
        data: [{ id: 12, nom: 'Alaoui', prenom: 'Sara' }],
      })),
      createRetourFeedback360: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
    },
  }
})

function renderRecrutement() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <Recrutement />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Recrutement — ATS (XRH17-23)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et charge les endpoints ATS (vivier + statistiques)', async () => {
    renderRecrutement()
    expect(
      await screen.findByText('EPI, recrutement & évaluations'),
    ).toBeInTheDocument()
    // Les nouveaux endpoints ATS sont bien appelés au montage.
    expect(rhApi.getVivier).toHaveBeenCalled()
    expect(rhApi.getRecrutementStatistiques).toHaveBeenCalled()
    expect(rhApi.getGabaritsEmailRecrutement).toHaveBeenCalled()
    expect(rhApi.getModelesEvaluation).toHaveBeenCalled()
  })

  it('propose les onglets Vivier / Statistiques / Gabarits', async () => {
    renderRecrutement()
    await screen.findByText('EPI, recrutement & évaluations')
    expect(screen.getByRole('radio', { name: 'Vivier' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Statistiques' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Gabarits' })).toBeInTheDocument()
  })

  it('crée une candidature manuelle via rhApi.createCandidature (WIR34)', async () => {
    rhApi.getOuverturesPoste.mockResolvedValue({ data: [{ id: 5, intitule: 'Technicien PV' }] })
    rhApi.createCandidature.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Recrutement' }))

    fireEvent.click(await screen.findByRole('button', { name: /Nouveau candidat/ }))
    // Le dialogue est ouvert : « Nouveau candidat » existe aussi sur le bouton,
    // donc on vérifie la présence du dialogue lui-même (getByText matcherait 2).
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Poste visé'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Nom du candidat'), { target: { value: 'Yassine Amrani' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la candidature' }))

    await waitFor(() => expect(rhApi.createCandidature).toHaveBeenCalledWith(
      expect.objectContaining({ ouverture: '5', nom: 'Yassine Amrani' }),
    ))
  })

  it('crée un gabarit d’évaluation via rhApi.createModeleEvaluation (WIR34)', async () => {
    rhApi.createModeleEvaluation.mockResolvedValueOnce({ data: { id: 1 } })
    renderRecrutement()
    await screen.findByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Gabarits' }))

    fireEvent.click(screen.getByRole('button', { name: /Nouveau modèle/ }))
    expect(screen.getByText('Nouveau modèle d’évaluation')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Nom du modèle'), { target: { value: 'Entretien annuel' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le modèle' }))

    await waitFor(() => expect(rhApi.createModeleEvaluation).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Entretien annuel', questions: [] }),
    ))
  })

  it('invite un répondant au feedback 360° via rhApi.createRetourFeedback360 (WIR131)', async () => {
    rhApi.getEvaluationsEmploye.mockResolvedValueOnce({
      data: [{ id: 9, employe_nom: 'Bennani Youssef', statut: 'validee', statut_display: 'Validée' }],
    })
    renderRecrutement()
    await screen.findByText('EPI, recrutement & évaluations')
    fireEvent.click(screen.getByRole('radio', { name: 'Évaluations' }))
    // DataTable rend la table desktop ET le repli carte mobile (CSS seul,
    // les deux existent dans le DOM en jsdom) : getAllBy*, premier match.
    await screen.findAllByText('Bennani Youssef')

    fireEvent.click(screen.getAllByRole('button', { name: 'Feedback 360°' })[0])
    expect(await screen.findByText(/Feedback 360° — Bennani Youssef/)).toBeInTheDocument()
    await waitFor(() => expect(rhApi.getSyntheseFeedback360).toHaveBeenCalledWith({ evaluation: 9 }))

    fireEvent.change(screen.getByLabelText('Répondant'), { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Inviter' }))

    await waitFor(() => expect(rhApi.createRetourFeedback360).toHaveBeenCalledWith({
      evaluation: 9, repondant: 12, relation: 'pair',
    }))
  })
})
