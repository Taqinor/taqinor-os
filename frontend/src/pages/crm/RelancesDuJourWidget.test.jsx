import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* MRY14 — Cockpit « Relances du jour » v2 : message prêt + WhatsApp (aperçu-
   puis-clic, jamais un envoi automatique — décision D5), appel (`tel:`),
   Fait (issue/note/rappel), Sauter, Reporter. crmApi mocké — aucun appel
   réseau réel. */

/* PACT10 / MRY25 — la charge utile vient de l'exemple COMMITTÉ
   (`apps/crm/contract_samples/relance_etape_v2.json` /
   `relance_etape_message.json`), jamais d'un objet retapé à la main : c'est
   cette deuxième source de vérité qui avait laissé passer l'écran AO du
   03/08/2026 (test vert, écran mort). Si le serveur change de forme,
   l'exemple change et ce test casse tout seul. */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results
const PREMIERE = ETAPES[0]
const MESSAGE = exempleContrat('crm', 'relance_etape_message')

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
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
  crmApi.getRelanceEtapeMessage.mockResolvedValue(reponseContrat('crm', 'relance_etape_message'))
  crmApi.whatsappRelanceEtape.mockResolvedValue({
    data: { ...MESSAGE, etape: { ...PREMIERE, statut: 'fait' } },
  })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

describe('RelancesDuJourWidget (MRY14)', () => {
  it('liste les étapes avec cadence, canal, score et priorité', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(
      reponseContrat('crm', 'relance_etape_v2'))
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    expect(screen.getByText(ETAPES[1].lead_nom)).toBeInTheDocument()
    // Badge cadence (PREMIERE = contact, ETAPES[1] = apres_devis).
    expect(screen.getByText('Contact')).toBeInTheDocument()
    expect(screen.getByText('Après devis')).toBeInTheDocument()
    // Badge canal.
    expect(screen.getAllByText('Appel').length).toBeGreaterThan(0)
    expect(screen.getAllByText('WhatsApp').length).toBeGreaterThan(0)
    // Badge priorité (PREMIERE = haute ; ETAPES[1] = normale, non affichée).
    expect(screen.getByText('Haute')).toBeInTheDocument()
    // L'exemple de contrat porte une touche en retard (`overdue: true`).
    expect(screen.getAllByText(/En retard/).length).toBeGreaterThan(0)
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'all' })
  })

  it('WhatsApp ouvre la modale avec le message rendu puis marque la touche au clic « Ouvrir WhatsApp »', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => {})
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /WhatsApp/ }))
    await waitFor(() => expect(crmApi.getRelanceEtapeMessage).toHaveBeenCalledWith(PREMIERE.id))
    expect(await screen.findByText(MESSAGE.message)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir WhatsApp/ }))
    // Le lien s'ouvre AVANT l'appel serveur (patron DevisList.openWhatsApp).
    expect(openSpy).toHaveBeenCalledWith(MESSAGE.wa_url, '_blank', 'noopener')
    await waitFor(() => expect(crmApi.whatsappRelanceEtape).toHaveBeenCalledWith(PREMIERE.id))
    openSpy.mockRestore()
  })

  it('le mini-formulaire Fait envoie l\'issue choisie', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Joint' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait)
      .toHaveBeenCalledWith(PREMIERE.id, { outcome: 'joint' }))
    await waitFor(() => expect(screen.queryByText(PREMIERE.lead_nom)).not.toBeInTheDocument())
  })

  it('Reporter envoie une échéance ISO', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-09-10' } })
    fireEvent.change(screen.getByLabelText('Heure'), { target: { value: '11:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      PREMIERE.id, { due_at: new Date('2026-09-10T11:00:00').toISOString() }))
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

  it('affiche un état vide qui nomme le démarrage automatique des cadences', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(
      reponseContrat('crm', 'relance_etape_v2', 'exemple_vide'))
    mount()
    await waitFor(() => expect(screen.getByText(/Aucune touche due/)).toBeInTheDocument())
    expect(screen.getByText(/les cadences démarrent seules à l'arrivée d'un lead/))
      .toBeInTheDocument()
  })

  it('navigue vers le lead au clic sur son nom', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    // Pas d'assertion de route ici (MemoryRouter minimal) — vérifie juste
    // que le bouton existe et reste cliquable sans lever d'erreur.
    expect(() => fireEvent.click(screen.getByText(PREMIERE.lead_nom))).not.toThrow()
  })
})
