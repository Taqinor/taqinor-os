import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* NTSRV31 — assistant de création d'un Problème depuis un regroupement
   suggéré (NTSRV17).

   Critère d'acceptation : DÉCOCHER un ticket à l'étape 1 l'exclut bien du
   problème créé — la création part en UN seul appel transactionnel. */

const REGROUPEMENT = {
  produit_id: 3,
  produit_nom: 'Onduleur X',
  cause_id: 1,
  cause_libelle: 'Surchauffe',
  titre_suggere: 'Onduleur X — Surchauffe',
  nb_tickets: 3,
  tickets: [
    { id: 11, reference: 'SAV-0011', statut: 'en_cours', priorite: 'haute',
      date_ouverture: '2026-03-01', client: 'Bennani' },
    { id: 12, reference: 'SAV-0012', statut: 'en_cours', priorite: 'normale',
      date_ouverture: '2026-03-04', client: 'Alaoui' },
    { id: 13, reference: 'SAV-0013', statut: 'nouveau', priorite: 'normale',
      date_ouverture: '2026-03-08', client: 'Idrissi' },
  ],
}

const PROBLEME = {
  id: 5, reference: 'PRB-202603-0001', titre: 'Onduleur Y — Usure',
  description: '', statut: 'identifie', statut_display: 'Identifié',
  cause_racine: '', created_at: '2026-03-01T08:00:00Z',
  updated_at: '2026-03-01T08:00:00Z', nb_tickets: 4, anciennete_jours: 6,
  impact: 24,
}

vi.mock('../../api/savApi', () => ({
  default: {
    getProblemes: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getRegroupementsSuggeres: vi.fn(() => Promise.resolve({
      data: { fenetre_jours: 30, seuil: 3, results: [] },
    })),
    creerProblemeDepuisRegroupement: vi.fn(() => Promise.resolve({
      data: { id: 9, reference: 'PRB-202603-0002',
        titre: 'Onduleur X — Surchauffe', nb_tickets: 2 },
    })),
  },
}))

import savApi from '../../api/savApi'
import ProblemesPage from './ProblemesPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function avecRegroupement() {
  savApi.getRegroupementsSuggeres.mockResolvedValue({
    data: { fenetre_jours: 30, seuil: 3, results: [REGROUPEMENT] },
  })
}

async function ouvrirAssistant() {
  avecRegroupement()
  render(<ProblemesPage />)
  const bouton = await screen.findByRole('button', { name: 'Créer le problème' })
  fireEvent.click(bouton)
  await screen.findByText(/étape 1 sur 2/)
}

describe('ProblemesPage (NTSRV16/NTSRV17/NTSRV31)', () => {
  it('liste les problèmes suivis, triés par impact côté serveur', async () => {
    savApi.getProblemes.mockResolvedValue({ data: { results: [PROBLEME] } })
    render(<ProblemesPage />)
    expect(await screen.findByText('PRB-202603-0001')).toBeInTheDocument()
    expect(screen.getByText('Onduleur Y — Usure')).toBeInTheDocument()
    expect(savApi.getProblemes).toHaveBeenCalledWith({ ordering: '-impact' })
  })

  it('annonce l\'absence de regroupement sans en inventer', async () => {
    render(<ProblemesPage />)
    expect(await screen.findByText(/Aucun regroupement suggéré/))
      .toBeInTheDocument()
    expect(savApi.creerProblemeDepuisRegroupement).not.toHaveBeenCalled()
  })

  it('affiche le regroupement suggéré sans rien créer', async () => {
    avecRegroupement()
    render(<ProblemesPage />)
    expect(await screen.findByText(/Onduleur X — Surchauffe — 3 tickets/))
      .toBeInTheDocument()
    expect(savApi.creerProblemeDepuisRegroupement).not.toHaveBeenCalled()
  })

  it('pré-remplit le titre suggéré et coche tous les tickets', async () => {
    await ouvrirAssistant()
    expect(screen.getByLabelText(/Titre du problème/))
      .toHaveValue('Onduleur X — Surchauffe')
    const cases = screen.getAllByRole('checkbox')
    expect(cases).toHaveLength(3)
    cases.forEach((c) => expect(c).toBeChecked())
    expect(screen.getByText('Tickets à rattacher (3 sur 3)'))
      .toBeInTheDocument()
  })

  it('décocher un ticket l\'exclut du problème créé', async () => {
    await ouvrirAssistant()
    // On décoche SAV-0013 (le 3ᵉ).
    fireEvent.click(screen.getByLabelText(/SAV-0013/))
    expect(screen.getByText('Tickets à rattacher (2 sur 3)'))
      .toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    fireEvent.click(screen.getByRole('button', { name: 'Créer le problème' }))
    await waitFor(() =>
      expect(savApi.creerProblemeDepuisRegroupement).toHaveBeenCalledWith({
        titre: 'Onduleur X — Surchauffe',
        cause_racine: '',
        ticket_ids: [11, 12],
      }))
  })

  it('crée en UN seul appel transactionnel', async () => {
    await ouvrirAssistant()
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    fireEvent.click(screen.getByRole('button', { name: 'Créer le problème' }))
    await waitFor(() =>
      expect(savApi.creerProblemeDepuisRegroupement)
        .toHaveBeenCalledTimes(1))
  })

  it('refuse un titre vide en nommant le champ', async () => {
    await ouvrirAssistant()
    fireEvent.change(screen.getByLabelText(/Titre du problème/),
      { target: { value: '  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.getByText('Donnez un titre au problème.'))
      .toBeInTheDocument()
    expect(screen.getByText(/étape 1 sur 2/)).toBeInTheDocument()
  })

  it('refuse un regroupement entièrement décoché', async () => {
    await ouvrirAssistant()
    screen.getAllByRole('checkbox').forEach((c) => fireEvent.click(c))
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    expect(screen.getByText('Cochez au moins un ticket à rattacher.'))
      .toBeInTheDocument()
    expect(savApi.creerProblemeDepuisRegroupement).not.toHaveBeenCalled()
  })

  it('revient à l\'étape 1 sans perdre les cases décochées', async () => {
    await ouvrirAssistant()
    fireEvent.click(screen.getByLabelText(/SAV-0012/))
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    fireEvent.click(screen.getByRole('button', { name: 'Précédent' }))
    expect(screen.getByText('Tickets à rattacher (2 sur 3)'))
      .toBeInTheDocument()
  })

  it('affiche l\'erreur serveur au lieu d\'un message générique', async () => {
    savApi.creerProblemeDepuisRegroupement.mockRejectedValueOnce({
      response: { data: { ticket_ids: ['Ticket inconnu.'] } },
    })
    await ouvrirAssistant()
    fireEvent.click(screen.getByRole('button', { name: 'Suivant' }))
    fireEvent.click(screen.getByRole('button', { name: 'Créer le problème' }))
    expect(await screen.findByText('ticket_ids : Ticket inconnu.'))
      .toBeInTheDocument()
  })
})
