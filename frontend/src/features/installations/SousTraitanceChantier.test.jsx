import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT55 — Sous-traitance chantier : ordres, factures/règlements,
   attestations, évaluations, retenues de garantie, depuis la fiche d'un
   sous-traitant sans quitter l'écran. */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const SOUS_TRAITANT = {
  id: 5, raison_sociale: 'Terrassements Atlas', metier: 'terrassement',
  metier_display: 'Terrassement', actif: true,
}

const inst = vi.hoisted(() => ({
  getSousTraitants: vi.fn(() => Promise.resolve({ data: { count: 1, results: [
    { id: 5, raison_sociale: 'Terrassements Atlas', metier: 'terrassement', metier_display: 'Terrassement', actif: true },
  ] } })),
  createSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  getInstallations: vi.fn(() => Promise.resolve({ data: { count: 1, results: [{ id: 9, reference: 'CH-009' }] } })),
  getOrdresSousTraitance: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createOrdreSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
  emettreOrdreSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
  receptionnerOrdreSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
  cloturerOrdreSousTraitance: vi.fn(() => Promise.resolve({ data: {} })),
  getFacturesSousTraitant: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createFactureSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  annulerFactureSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  getPaiementsSousTraitant: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createPaiementSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  deletePaiementSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  getAttestationsSousTraitant: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createAttestationSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  getAffectabiliteSousTraitant: vi.fn(() => Promise.resolve({ data: { sous_traitant: 5, affectable: true, actif: true, pieces_expirees: [] } })),
  getEvaluationsSousTraitant: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createEvaluationSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  getScorecardSousTraitant: vi.fn(() => Promise.resolve({ data: { sous_traitant: 5, nb_evaluations: 0, note_qualite: null, note_delai: null, note_securite: null, note_globale: null } })),
  getRetenuesGarantieSousTraitant: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  createRetenueGarantieSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
  leverRetenueGarantieSousTraitant: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))

import SousTraitanceChantier from './SousTraitanceChantier'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SousTraitanceChantier (PACT55)', () => {
  it('charge l\'annuaire et affiche la fiche du sous-traitant sélectionné', async () => {
    render(<SousTraitanceChantier />)
    expect(await screen.findByText('Terrassements Atlas')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Terrassements Atlas' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Ordres' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Factures & règlements' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Attestations' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Évaluation' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Retenues de garantie' })).toBeInTheDocument()
  })

  it('affiche l\'état vide quand l\'annuaire est vide', async () => {
    inst.getSousTraitants.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    render(<SousTraitanceChantier />)
    expect(await screen.findByText('Aucun sous-traitant')).toBeInTheDocument()
  })

  it('crée un ordre de travaux depuis la fiche', async () => {
    const user = userEvent.setup()
    render(<SousTraitanceChantier />)
    await screen.findByText('Terrassements Atlas')
    await waitFor(() => expect(inst.getOrdresSousTraitance).toHaveBeenCalledWith(
      expect.objectContaining({ sous_traitant: 5 })))
    await user.click(screen.getByRole('button', { name: /Nouvel ordre/ }))
    await user.type(screen.getByLabelText('Prestation'), 'Terrassement plateforme')
    await user.type(screen.getByLabelText('Montant (MAD)'), '15000')
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(inst.createOrdreSousTraitance).toHaveBeenCalledWith(
      expect.objectContaining({ sous_traitant: 5, prestation: 'Terrassement plateforme', montant: '15000' })))
  })

  it('émet un ordre brouillon depuis la liste', async () => {
    inst.getOrdresSousTraitance.mockResolvedValue({ data: { count: 1, results: [
      { id: 41, reference: 'OST-202608-0001', statut: 'brouillon', statut_display: 'Brouillon', prestation: 'Terrassement', montant: '15000' },
    ] } })
    const user = userEvent.setup()
    render(<SousTraitanceChantier />)
    expect(await screen.findByTestId('ordre-41')).toBeInTheDocument()
    await user.click(within(screen.getByTestId('ordre-41')).getByRole('button', { name: 'Émettre' }))
    await waitFor(() => expect(inst.emettreOrdreSousTraitance).toHaveBeenCalledWith(41))
  })

  it('ajoute une facture puis un règlement sans quitter l\'écran', async () => {
    inst.getFacturesSousTraitant.mockResolvedValue({ data: { count: 1, results: [
      { id: 71, numero: 'FA-2026-01', reference: 'FRN-0071', statut: 'validee', statut_display: 'Validée', montant_ttc: '12000', reste_a_payer: '12000' },
    ] } })
    const user = userEvent.setup()
    render(<SousTraitanceChantier />)
    await screen.findByText('Terrassements Atlas')
    await user.click(screen.getByRole('tab', { name: 'Factures & règlements' }))
    expect(await screen.findByTestId('facture-71')).toBeInTheDocument()
    await user.click(within(screen.getByTestId('facture-71')).getByRole('button', { name: 'Ajouter un règlement' }))
    await user.type(screen.getByLabelText('Montant (MAD)'), '5000')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(inst.createPaiementSousTraitant).toHaveBeenCalledWith(
      expect.objectContaining({ facture: 71, montant: '5000' })))
  })

  it('affiche le statut d\'affectabilité sur l\'onglet attestations', async () => {
    const user = userEvent.setup()
    render(<SousTraitanceChantier />)
    await screen.findByText('Terrassements Atlas')
    await user.click(screen.getByRole('tab', { name: 'Attestations' }))
    expect(await screen.findByText('Affectable')).toBeInTheDocument()
  })

  it('lève une retenue de garantie une fois l\'ordre choisi', async () => {
    inst.getOrdresSousTraitance.mockResolvedValue({ data: { count: 1, results: [
      { id: 41, reference: 'OST-202608-0001', statut: 'clos', statut_display: 'Clos', prestation: 'Terrassement', montant: '15000' },
    ] } })
    inst.getRetenuesGarantieSousTraitant.mockResolvedValue({ data: { count: 1, results: [
      { id: 3, ordre: 41, pourcentage: '10', levee: false, montant_retenu: '1500' },
    ] } })
    const user = userEvent.setup()
    render(<SousTraitanceChantier />)
    await screen.findByText('Terrassements Atlas')
    await user.click(screen.getByRole('tab', { name: 'Retenues de garantie' }))
    await screen.findByRole('option', { name: 'OST-202608-0001' })
    await user.selectOptions(screen.getByLabelText('Ordre de travaux'), '41')
    expect(await screen.findByTestId('retenue-3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Lever la retenue' }))
    await waitFor(() => expect(inst.leverRetenueGarantieSousTraitant).toHaveBeenCalledWith(3))
  })
})
