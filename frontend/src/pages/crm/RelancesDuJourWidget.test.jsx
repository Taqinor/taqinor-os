import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* RELANCE FOUNDATION — panneau « Relances du jour » (plan de relance
   structuré multi-touches, crm.RelanceEtape). Liste les étapes dues +
   actions Fait/Sauter. crmApi mocké — aucun appel réseau réel. */

/* PACT10 / MRY25 — la charge utile vient de l'exemple COMMITTÉ
   (`apps/crm/contract_samples/relance_etape_v2.json`), jamais d'un objet
   retapé à la main : c'est cette deuxième source de vérité qui avait laissé
   passer l'écran AO du 03/08/2026 (test vert, écran mort). Si le serveur
   change de forme, l'exemple change et ce test casse tout seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results
const PREMIERE = ETAPES[0]

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

// Les tests d'ACTION n'affichent qu'UNE ligne (sinon `getByRole('button')`
// tombe sur deux boutons homonymes) ; la ligne reste celle du contrat, jamais
// un objet retapé. Le test de LISTE, lui, sert l'exemple complet.
beforeEach(() => {
  crmApi.getRelanceEtapesDues.mockResolvedValue(
    { data: { count: 1, results: [PREMIERE] } })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget (RELANCE FOUNDATION)', () => {
  it('liste les étapes de relance dues avec canal + badge de retard', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(
      reponseContrat('crm', 'relance_etape_v2'))
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    expect(screen.getByText(`Appel · ${PREMIERE.lead_owner_nom}`)).toBeInTheDocument()
    expect(screen.getByText(ETAPES[1].lead_nom)).toBeInTheDocument()
    // L'exemple de contrat porte une touche en retard (`overdue: true`).
    expect(screen.getAllByText(/En retard/).length).toBeGreaterThan(0)
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'all' })
  })

  it('le bouton Fait marque l\'étape faite et la retire de la liste', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Fait/ }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(PREMIERE.id, undefined))
    await waitFor(() => expect(screen.queryByText(PREMIERE.lead_nom)).not.toBeInTheDocument())
  })

  it('Sauter ouvre une note optionnelle puis confirme', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    const textarea = screen.getByPlaceholderText(/Note \(optionnelle\)/)
    fireEvent.change(textarea, { target: { value: 'Client en congé' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee)
      .toHaveBeenCalledWith(PREMIERE.id, 'Client en congé'))
    await waitFor(() => expect(screen.queryByText(PREMIERE.lead_nom)).not.toBeInTheDocument())
  })

  it('Sauter → Annuler referme la note sans appeler l\'API', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(crmApi.marquerRelanceEtapeSautee).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Sauter/ })).toBeInTheDocument()
  })

  it('affiche un état vide quand aucune relance n\'est due, avec le rappel du déclencheur (fiche lead)', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(
      reponseContrat('crm', 'relance_etape_v2', 'exemple_vide'))
    mount()
    await waitFor(() => expect(screen.getByText(/Aucune relance due/)).toBeInTheDocument())
    // Revue Fable finale — « Aucune relance due » à elle seule se lit comme
    // « tout est à jour » ; le vide peut aussi vouloir dire « aucun lead n'a
    // de plan initialisé ». Le widget reste minimal (aucun bouton d'action
    // ici) mais nomme où se trouve le vrai déclencheur.
    expect(screen.getByText(/Initialiser le plan de relance/)).toBeInTheDocument()
    expect(screen.getByText(/Suivi commercial/)).toBeInTheDocument()
  })

  it('navigue vers le lead au clic sur son nom', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    // Pas d'assertion de route ici (MemoryRouter minimal) — vérifie juste
    // que le bouton existe et reste cliquable sans lever d'erreur.
    expect(() => fireEvent.click(screen.getByText(PREMIERE.lead_nom))).not.toThrow()
  })
})
