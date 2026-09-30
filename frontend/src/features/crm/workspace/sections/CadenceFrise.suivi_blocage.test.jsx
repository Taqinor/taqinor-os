import { useState } from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../../test/fixtures/contractSamples'

/* SUIVI-BLOCAGE (30/09/2026) — fiche du lead : la frise RECHARGE après chaque
   geste. Avant : « Visite acceptée » envoyait la réponse, la frise rechargeait,
   la ligne close n'était plus actionnable, et la fenêtre de planification
   (enfant de la ligne) disparaissait — l'étape « Planifier la visite » se
   reposait en boucle. Et l'étape devis, née pour demain après « Client
   joint », n'avait pas de « Fait » le jour même. */

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results
const APPEL = { ...ETAPES.find((e) => e.canal === 'appel' && e.cadence === 'contact') }

vi.mock('../../../../api/crmApi', () => ({
  default: {
    getRelanceEtapesLead: vi.fn(),
    getLeadVisites: vi.fn(() => Promise.resolve({ data: { visites: [] } })),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
    getRelanceEtapeMessage: vi.fn(() => Promise.resolve({ data: { message: 'Bonjour', langue: 'fr' } })),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    planifierVisiteLead: vi.fn(() => Promise.resolve({ data: { visite: { id: 1 }, prochaine_touche: null } })),
    getPanneauAppel: vi.fn(() => Promise.reject(new Error('indisponible'))),
  },
}))
vi.mock('../../../../lib/toast', () => ({
  toastError: vi.fn(), toastInfo: vi.fn(), toastSuccess: vi.fn(),
}))

import crmApi from '../../../../api/crmApi'
import { toastError } from '../../../../lib/toast'
import CadenceFrise from './CadenceFrise'

const jour = (decalage) => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date(Date.now() + decalage * 24 * 3600 * 1000))

afterEach(() => { cleanup(); vi.clearAllMocks() })

// Le parent réel (SectionPipeline) incrémente `reloadToken` à chaque geste.
function Fiche({ onEtapes, seulementActionnable = false, appelOuvert = false }) {
  const [token, setToken] = useState(0)
  return (
    <MemoryRouter>
      <CadenceFrise
        leadId={APPEL.lead} reloadToken={token} onChanged={() => setToken((t) => t + 1)}
        onEtapes={onEtapes} seulementActionnable={seulementActionnable} appelOuvert={appelOuvert}
      />
    </MemoryRouter>
  )
}

describe('SUIVI-BLOCAGE — frise de la fiche', () => {
  it('« Visite acceptée » : la fenêtre de planification RESTE à l’écran (rien n’est envoyé avant la date)', async () => {
    const ouverte = { ...APPEL, statut: 'a_faire', due_date: jour(0), overdue: false }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [ouverte] } })
    render(<Fiche />)
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
    expect(crmApi.marquerRelanceEtapeFait).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(1)
    // Après la planification : la frise est relue, la touche close (par le
    // serveur) disparaît des lignes actionnables, la suite est affichée.
    const close = { ...ouverte, statut: 'fait', traite_le: new Date().toISOString(), suites: {} }
    const confirmation = {
      ...ouverte, id: ouverte.id + 1000, cadence: 'apres_devis', ordre: 90, cle: 'confirmation',
      libelle: 'Confirmer la visite (veille)', canal: 'whatsapp', template_cle: 'visite_confirmation',
      due_date: jour(2),
    }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [close, confirmation] } })
    fireEvent.change(screen.getByLabelText(/Date prévue/), { target: { value: jour(3) } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    await waitFor(() => expect(crmApi.planifierVisiteLead).toHaveBeenCalledWith(
      APPEL.lead, { date_prevue: jour(3), etape: ouverte.id }))
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByText(/Confirmer la visite \(veille\)/)).toBeInTheDocument())
  })

  it('après « Client joint », l’étape « Préparer et envoyer le devis » (née pour DEMAIN) est traitable le jour même', async () => {
    const devis = {
      ...APPEL, id: APPEL.id + 2000, cadence: 'generique', ordre: 1, cle: 'devis',
      libelle: 'Préparer et envoyer le devis (ou fixer un rappel)', template_cle: '',
      statut: 'a_faire', due_date: jour(1), overdue: false,
      due_at: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
    }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [devis] } })
    render(<Fiche />)
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    // Le devis est parti le jour même (hors ERP) : « Fait » doit être possible.
    expect(screen.getByRole('button', { name: /^Fait$/ })).toBeInTheDocument()
  })

  it('« À rappeler le… » sur une étape déplacée à demain : la ligne garde ses boutons (plus jamais une ligne vide)', async () => {
    const ouverte = { ...APPEL, statut: 'a_faire', due_date: jour(0), overdue: false }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [ouverte] } })
    render(<Fiche />)
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'À rappeler le…' }))
    fireEvent.change(screen.getByLabelText('Rappeler le'), { target: { value: jour(1) } })
    // Le serveur déplace la MÊME touche à demain : la frise la relit ouverte.
    crmApi.getRelanceEtapesLead.mockResolvedValue({
      data: { results: [{ ...ouverte, due_date: jour(1) }] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalled())
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByRole('button', { name: /Appeler/ })).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Reporter/ })).toBeInTheDocument()
    expect(screen.getByTestId('touche-en-avance')).toBeInTheDocument()
  })

  it('mode « fenêtre d’appel » : seule la ligne actionnable, panneau d’appel ouvert, et l’appelant sait s’il reste une touche', async () => {
    const passee = { ...APPEL, id: 1, statut: 'fait', traite_le: '2026-09-01T10:00:00Z', due_date: '2026-09-01' }
    const ouverte = { ...APPEL, id: 2, statut: 'a_faire', due_date: jour(0), overdue: false }
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [passee, ouverte] } })
    const onEtapes = vi.fn()
    render(<Fiche seulementActionnable appelOuvert onEtapes={onEtapes} />)
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    expect(screen.getAllByTestId('cadence-frise-etape')).toHaveLength(1)
    expect(screen.queryByText(/touche\(s\) passée\(s\)/)).not.toBeInTheDocument()
    expect(await screen.findByRole('button', { name: /Saisir l’issue de l’appel/ })).toBeInTheDocument()
    await waitFor(() => expect(onEtapes).toHaveBeenCalled())
    expect(onEtapes.mock.calls.at(-1)[0].map((e) => e.id)).toEqual([2])
  })

  it('mode « fenêtre d’appel » sans aucune touche ouverte : rien n’est rendu et l’appelant reçoit une liste vide', async () => {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [] } })
    const onEtapes = vi.fn()
    render(<Fiche seulementActionnable appelOuvert onEtapes={onEtapes} />)
    await waitFor(() => expect(onEtapes).toHaveBeenCalledWith([]))
    expect(screen.queryByText(/Aucune cadence/)).not.toBeInTheDocument()
  })
})

/* SUIVI-REFUS (30/09/2026) — la frise de la fiche relançait déjà l'erreur de
   « Fait » à la ligne, mais avalait celle de « Sauter » et « Reporter » : sur
   un double clic (400 `erreurs.etape`, SUIVI E8) le panneau se refermait comme
   réussi et un toast générique passait seul. Comme « Fait » : le panneau reste
   ouvert, le message exact du serveur est sous le geste, la frise n'est PAS
   relue sur un refus (`onChanged` ne suit qu'un succès). */
const DEJA_TRAITEE = 'Cette étape est déjà traitée — rechargez la liste.'
const refus = (status, data) => ({ response: { status, data } })
const refus400 = (erreurs) => refus(400, { erreurs })

describe('SUIVI-REFUS — frise de la fiche : Sauter / Reporter refusés', () => {
  const ouverte = () => ({ ...APPEL, statut: 'a_faire', due_date: jour(0), overdue: false })

  async function monterFrise() {
    crmApi.getRelanceEtapesLead.mockResolvedValue({ data: { results: [ouverte()] } })
    render(<Fiche />)
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
  }
  const confirmer = () => fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
  function ouvrirReporter() {
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: jour(1) } })
  }

  it('« Reporter » refusé (400 erreurs.etape) : panneau ouvert, message exact, frise non relue, aucun toast générique', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await monterFrise()
    ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      APPEL.id, { rappel_le: jour(1), rappel_heure: '09:00' })
    expect(screen.getByLabelText('Reporter au')).toHaveValue(jour(1))
    expect(toastError).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled())
  })

  it('« Sauter » refusé (400 erreurs.etape) : panneau ouvert, message exact, frise non relue, aucun toast générique', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await monterFrise()
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(screen.getByTestId('suite-sauter')).toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
    expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(1)
  })

  it('« Sauter » : un échec RÉSEAU garde son toast (F2) ET la phrase claire sous le geste', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(new Error('Network Error'))
    await monterFrise()
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent('Pas de connexion au serveur')
    expect(toastError).toHaveBeenCalledWith('Action impossible pour le moment.')
  })

  it('succès « Reporter » inchangé : la frise est relue, le panneau se referme (la ligne reste montée)', async () => {
    await monterFrise()
    ouvrirReporter()
    // Le serveur déplace la MÊME touche à demain : la frise la relit ouverte.
    crmApi.getRelanceEtapesLead.mockResolvedValue({
      data: { results: [{ ...ouverte(), due_date: jour(1) }] },
    })
    confirmer()
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalled())
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByLabelText('Reporter au')).not.toBeInTheDocument())
    expect(screen.getByRole('button', { name: /Reporter/ })).toBeInTheDocument()
    expect(screen.queryByTestId('erreur-outcome')).not.toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
  })

  it('succès « Sauter » inchangé : la frise est relue, la touche sautée n’est plus actionnable', async () => {
    await monterFrise()
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
    crmApi.getRelanceEtapesLead.mockResolvedValue({
      data: { results: [{ ...ouverte(), statut: 'sautee', traite_le: new Date().toISOString() }] },
    })
    confirmer()
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalledWith(APPEL.id, ''))
    await waitFor(() => expect(crmApi.getRelanceEtapesLead).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByTestId('relance-etape-row')).not.toBeInTheDocument())
    expect(toastError).not.toHaveBeenCalled()
  })
})
