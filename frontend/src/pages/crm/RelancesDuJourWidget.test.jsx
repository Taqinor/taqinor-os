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
// F2 — le helper toast (lib/toast) est mocké pour PROUVER qu'un échec réseau
// prévient l'agent (jamais le catch muet d'avant), sans dépendre du rendu
// visuel réel de sonner.
vi.mock('../../lib/toast', () => ({ toastError: vi.fn() }))

import crmApi from '../../api/crmApi'
import { toastError } from '../../lib/toast'
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

  it('F1 — Reporter envoie {rappel_le, rappel_heure} (forme sûre ancrée Casablanca, jamais un due_at fuseau-navigateur)', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-09-10' } })
    fireEvent.change(screen.getByLabelText('Heure'), { target: { value: '11:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      PREMIERE.id, { rappel_le: '2026-09-10', rappel_heure: '11:00' }))
    await waitFor(() => expect(screen.queryByText(PREMIERE.lead_nom)).not.toBeInTheDocument())
  })

  it('F1 — Reporter sans heure saisie retombe sur 09:00 (jamais un due_at calculé côté écran)', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: '2026-09-10' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      PREMIERE.id, { rappel_le: '2026-09-10', rappel_heure: '09:00' }))
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

  it('F2 — un échec réseau affiche un toast d\'erreur et laisse la ligne cliquable (jamais un catch muet)', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(new Error('boom'))
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalled())
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Action impossible pour le moment.'))
    // La ligne n'a PAS été retirée (retirer() jamais appelé sur l'échec) et
    // redevient cliquable (busyId remis à null) — jamais un état bloqué.
    expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled())
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

  // MRY32 — sélecteur « Aujourd'hui + retard | Demain | 7 jours ».
  it('MRY32 — « Demain » interroge scope=tomorrow et les lignes futures se lisent seulement (pas de bouton Fait)', async () => {
    // Échéance FUTURE (demain, Africa/Casablanca) — `readOnly` du widget
    // compare au jour courant, jamais au scope demandé : une ligne dont
    // l'échéance est déjà passée resterait actionnable même sous scope=
    // tomorrow, ce que ce test ne doit PAS prouver par accident.
    const [y, m, d] = new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' })
      .format(new Date()).split('-').map(Number)
    const demain = new Date(Date.UTC(y, m - 1, d + 1)).toISOString().slice(0, 10)
    crmApi.getRelanceEtapesDues.mockResolvedValue({
      data: { count: 1, results: [{ ...PREMIERE, id: 999, due_date: demain }] },
    })
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('radio', { name: 'Demain' }))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'tomorrow' }))
    expect(screen.queryByRole('button', { name: /^Fait$/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Sauter/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Reporter/ })).not.toBeInTheDocument()
  })

  it('MRY32 — « 7 jours » interroge scope=week', async () => {
    mount()
    await waitFor(() => expect(screen.getByText(PREMIERE.lead_nom)).toBeInTheDocument())
    fireEvent.click(screen.getByRole('radio', { name: '7 jours' }))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'week' }))
  })
})
