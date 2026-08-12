import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT60 — Consultation fournisseurs et comparatif d'offres (FG311, XPUR20/21). */

function mockMatchMedia() {
  window.matchMedia = (query) => ({
    matches: false, media: query, onchange: null,
    addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false,
  })
}
beforeAll(() => { if (typeof window.matchMedia !== 'function') mockMatchMedia() })

const RFQ_ROW = {
  id: 6, reference: 'RFQ-202608-0001', objet: 'Panneaux 550W lot 3',
  statut: 'envoyee', statut_display: 'Envoyée', date_limite_reponse: '2026-08-15',
  offres: [
    { id: 41, fournisseur: 8, fournisseur_nom: 'Solar Import SARL', fournisseur_nom_libre: null, montant_ht: '95000', delai_jours: 10, retenue: false },
    { id: 42, fournisseur: null, fournisseur_nom: null, fournisseur_nom_libre: 'Fournisseur B', montant_ht: '98000', delai_jours: 7, retenue: false },
  ],
  consultations: [
    { id: 71, fournisseur: 8, fournisseur_nom: 'Solar Import SARL', a_repondu: true, nb_relances: 0 },
  ],
  comparatif: { nb_offres: 2, moins_chere_id: 41, plus_rapide_id: 42, retenue_id: null },
}

const inst = vi.hoisted(() => ({
  getRFQs: vi.fn(() => Promise.resolve({ data: { count: 1, results: [] } })),
  getRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  createRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  envoyerRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  cloturerRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  retenirOffreRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  consulterFournisseurRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  envoyerConsultationsRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  relancerNonRepondantsRFQ: vi.fn(() => Promise.resolve({ data: {} })),
  createRFQOffre: vi.fn(() => Promise.resolve({ data: {} })),
  getRFQConsultations: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
  getDemandesAchat: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
}))
vi.mock('../../api/installationsApi', () => ({ default: inst }))
vi.mock('../../api/stockApi', () => ({ default: {
  getFournisseurs: () => Promise.resolve({ data: { count: 1, results: [{ id: 8, nom: 'Solar Import SARL' }] } }),
} }))

import RFQ from './RFQ'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RFQ (PACT60)', () => {
  it('affiche le comparatif des offres avec les badges moins-chère/plus-rapide', async () => {
    inst.getRFQs.mockResolvedValue({ data: { count: 1, results: [RFQ_ROW] } })
    render(<RFQ />)
    expect(await screen.findByTestId('offre-41')).toBeInTheDocument()
    expect(within(screen.getByTestId('offre-41')).getByText('Moins chère')).toBeInTheDocument()
    expect(within(screen.getByTestId('offre-42')).getByText('Plus rapide')).toBeInTheDocument()
  })

  it('affiche l\'état vide quand aucune RFQ n\'existe', async () => {
    // Le test POSE son propre état : sans `beforeEach` de remise à zéro, le
    // `mockResolvedValue` d'un test précédent fuit et la liste n'est plus
    // vide — l'assertion dépendait alors de l'ORDRE d'exécution.
    inst.getRFQs.mockResolvedValue({ data: { count: 0, results: [] } })
    render(<RFQ />)
    expect((await screen.findAllByText('Aucune RFQ')).length).toBeGreaterThan(0)
  })

  it('crée une RFQ', async () => {
    inst.getRFQs.mockResolvedValue({ data: { count: 1, results: [RFQ_ROW] } })
    const user = userEvent.setup()
    render(<RFQ />)
    await screen.findByTestId('rfq-6')
    await user.click(screen.getAllByRole('button', { name: 'Nouvelle RFQ' })[0])
    await user.type(screen.getByLabelText('Objet'), 'Onduleurs lot 4')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createRFQ).toHaveBeenCalledWith(
      expect.objectContaining({ objet: 'Onduleurs lot 4' })))
  })

  it('consulte un fournisseur puis envoie les consultations', async () => {
    inst.getRFQs.mockResolvedValue({ data: { count: 1, results: [RFQ_ROW] } })
    const user = userEvent.setup()
    render(<RFQ />)
    await screen.findByTestId('rfq-6')
    await user.click(screen.getAllByRole('button', { name: /Consulter/ })[0])
    await screen.findByRole('option', { name: 'Solar Import SARL' })
    await user.selectOptions(screen.getByLabelText('Fournisseur'), '8')
    await user.click(screen.getAllByRole('button', { name: 'Ajouter' })[0])
    await waitFor(() => expect(inst.consulterFournisseurRFQ).toHaveBeenCalledWith(6, 8))
    await user.click(screen.getAllByRole('button', { name: 'Envoyer aux fournisseurs' })[0])
    await waitFor(() => expect(inst.envoyerConsultationsRFQ).toHaveBeenCalledWith(6))
  })

  it('saisit une offre puis la retient', async () => {
    inst.getRFQs.mockResolvedValue({ data: { count: 1, results: [RFQ_ROW] } })
    const user = userEvent.setup()
    render(<RFQ />)
    await screen.findByTestId('rfq-6')
    await user.click(screen.getAllByRole('button', { name: /Nouvelle offre/ })[0])
    await user.type(screen.getByLabelText('Ou nom libre (si hors annuaire)'), 'Fournisseur C')
    await user.type(screen.getByLabelText('Montant HT (MAD)'), '90000')
    await user.click(screen.getAllByRole('button', { name: 'Créer' })[0])
    await waitFor(() => expect(inst.createRFQOffre).toHaveBeenCalledWith(
      expect.objectContaining({ rfq: 6, montant_ht: '90000' })))

    await user.click(within(screen.getByTestId('offre-41')).getByRole('button', { name: 'Retenir' }))
    await waitFor(() => expect(inst.retenirOffreRFQ).toHaveBeenCalledWith(6, 41))
  })
})
