// MRY15 — frise de cadence de la fiche lead : TOUTES les étapes du lead
// (tous statuts, toutes cadences), depuis le contrat committé
// `apps/crm/contract_samples/relance_etape_v2.json` (PACT10) filtré côté
// `crmApi.getRelanceEtapesLead` (jamais un objet retapé à la main).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'
import { formatDate } from '../../../../lib/format'

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results

// MRY32 — la frise fait désormais elle-même Fait/Sauter/Reporter/WhatsApp
// sur ses touches actionnables : le mock crmApi doit couvrir ces appels en
// plus de la lecture (`getRelanceEtapesLead`).
vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))
vi.mock('../../../../lib/toast', () => ({ toastError: vi.fn() }))

import crmApi from '../../../../api/crmApi'
import CadenceFrise from './CadenceFrise'

beforeEach(() => {
  crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: ETAPES.length, results: ETAPES } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('MRY15 CadenceFrise', () => {
  it('charge la frise du lead avec ?lead=<id>&scope=lead', async () => {
    render(<CadenceFrise leadId={1489} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledWith(1489))
    expect(await screen.findByText(ETAPES[0].libelle)).toBeInTheDocument()
    expect(screen.getByText(ETAPES[1].libelle)).toBeInTheDocument()
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2)
  })

  it('rien à afficher quand le lead n\'a pas de cadence', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 0, results: [] } })
    render(<CadenceFrise leadId={1} />)
    expect(await screen.findByText(/Aucune cadence sur ce lead/)).toBeInTheDocument()
  })

  it('ne charge rien sans leadId (mode création)', () => {
    render(<CadenceFrise leadId={null} />)
    expect(crmApi.getRelanceEtapesLead).not.toHaveBeenCalled()
  })

  it('recharge quand reloadToken change (après Relancer/Arrêter la cadence)', async () => {
    const { rerender } = render(<CadenceFrise leadId={1489} reloadToken={0} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(1))
    rerender(<CadenceFrise leadId={1489} reloadToken={1} />)
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
  })

  it('affiche un état d\'erreur si le serveur échoue', async () => {
    crmApi.getRelanceEtapesLead.mockRejectedValue(new Error('boom'))
    render(<CadenceFrise leadId={1489} />)
    expect(await screen.findByText(/Frise de cadence indisponible/)).toBeInTheDocument()
  })

  // F3 — la frise ne montrait que la DATE (formatDate(due_date)) ; l'heure
  // Casablanca de due_at (comme heureDue de RelancesDuJourWidget.jsx, mais
  // SANS son repli « maintenant » — la frise couvre l'historique, une touche
  // passée garde son heure) doit apparaître à côté.
  it('F3 — une étape avec due_at affiche la date PUIS l\'heure Casablanca', async () => {
    render(<CadenceFrise leadId={1489} />)
    const premiere = ETAPES[0]
    const heureAttendue = new Intl.DateTimeFormat('fr-FR', {
      hour: '2-digit', minute: '2-digit', timeZone: 'Africa/Casablanca',
    }).format(new Date(premiere.due_at))
    const texteAttendu = `${formatDate(premiere.due_date)} ${heureAttendue}`
    expect(await screen.findByText(texteAttendu)).toBeInTheDocument()
  })
})

/* MRY32 — la frise agit directement sur la prochaine touche à faire et sur
   toute touche en retard (Appeler/WhatsApp/Fait/Sauter/Reporter, mode
   compact du composant partagé `RelanceEtapeRow.jsx`) : Meryem fait la
   touche SANS quitter la fiche. Jeu de données DÉDIÉ (dérivé par spread du
   contrat committé, jamais retapé à la main) pour isoler « prochaine à faire »
   vs « déjà faite », ce que l'exemple par défaut (deux étapes À FAIRE) ne
   distingue pas. */
describe('MRY32 — actions directement depuis la frise', () => {
  it('la prochaine touche à faire affiche un bouton Fait ; une touche déjà faite n\'en affiche aucun', async () => {
    const prochaine = { ...ETAPES[0], id: 501, statut: 'a_faire', overdue: false }
    const faite = { ...ETAPES[1], id: 502, statut: 'fait', overdue: false }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 2, results: [prochaine, faite] } })
    render(<CadenceFrise leadId={1489} />)
    // QJ-LISIBILITÉ — les touches passées sont repliées par défaut.
    await waitFor(() => expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(1))
    fireEvent.click(screen.getByRole('button', { name: /touche\(s\) passée\(s\)/ }))
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(2)
    // Une seule ligne d'action rendue (`relance-etape-row`, mode compact) :
    // celle de la prochaine touche à faire — la touche déjà faite n'en a pas.
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
    expect(screen.getByRole('button', { name: /^Fait$/ })).toBeInTheDocument()
  })

  it('une touche en retard affiche aussi ses actions, même si elle n\'est pas la « prochaine »', async () => {
    const prochaine = { ...ETAPES[0], id: 501, statut: 'a_faire', overdue: false }
    const retard = { ...ETAPES[1], id: 503, statut: 'a_faire', overdue: true }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 2, results: [prochaine, retard] } })
    render(<CadenceFrise leadId={1489} />)
    await waitFor(() => expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(2))
  })

  it('clic Fait → Confirmer appelle marquerRelanceEtapeFait et déclenche onChanged (frise ET fiche)', async () => {
    const prochaine = { ...ETAPES[0], id: 501, statut: 'a_faire', overdue: false }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { count: 1, results: [prochaine] } })
    const onChanged = vi.fn()
    render(<CadenceFrise leadId={1489} onChanged={onChanged} />)
    await waitFor(() => expect(screen.getByRole('button', { name: /^Fait$/ })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    // QJ-QUESTIONS — une réponse est désormais OBLIGATOIRE avant Confirmer.
    fireEvent.click(screen.getByRole('button', { name: 'Pas de réponse' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait)
      .toHaveBeenCalledWith(501, { outcome: 'non_joint' }))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })
})
