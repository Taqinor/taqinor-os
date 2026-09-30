import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

/* SUIVI-BLOCAGE (30/09/2026) — « après le script d'appel, ça bloque ».
   Quatre blocages PROUVÉS sur le cockpit réel avant correction :
     1. « Visite acceptée » : la réponse partait, le cockpit retirait la ligne,
        et la fenêtre de planification (enfant de la ligne) disparaissait avec
        elle — l'étape « Planifier la visite » se reposait en boucle ;
     2. une touche datée de DEMAIN (l'étape devis née juste après « Client
        joint », ou un appel passé en avance) : « Saisir l'issue de l'appel »
        désactivé, « Fait » caché — rien n'était enregistrable le jour même.
   Ces tests montent le VRAI cockpit (crmApi mocké) et exigent le contraire. */

const ETAPES = exempleContrat('crm', 'relance_etape_v2').results
const APPEL = { ...ETAPES.find((e) => e.canal === 'appel' && e.cadence === 'contact') }

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(),
    marquerRelanceEtapeFait: vi.fn(() => Promise.resolve({ data: { statut: 'fait' } })),
    marquerRelanceEtapeSautee: vi.fn(() => Promise.resolve({ data: { statut: 'sautee' } })),
    reporterRelanceEtape: vi.fn(() => Promise.resolve({ data: { statut: 'a_faire' } })),
    getRelanceEtapeMessage: vi.fn(() => Promise.resolve({ data: { message: 'Bonjour', langue: 'fr' } })),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: [] })),
    planifierVisiteLead: vi.fn(() => Promise.resolve({ data: { visite: { id: 1 }, prochaine_touche: null } })),
    getPanneauAppel: vi.fn(() => Promise.reject(new Error('indisponible'))),
  },
}))
vi.mock('../../lib/toast', () => ({
  toastError: vi.fn(), toastInfo: vi.fn(), toastSuccess: vi.fn(),
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

const jourCasa = (decalage) => new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Africa/Casablanca', year: 'numeric', month: '2-digit', day: '2-digit',
}).format(new Date(Date.now() + decalage * 24 * 3600 * 1000))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(<MemoryRouter><RelancesDuJourWidget /></MemoryRouter>)
}

describe('SUIVI-BLOCAGE — cockpit « Relances du jour »', () => {
  beforeEach(() => {
    crmApi.getRelanceEtapesDues.mockResolvedValue({
      data: { count: 1, results: [{ ...APPEL, due_date: jourCasa(0), overdue: false }] },
    })
  })

  it('« Visite acceptée » confirmée → la fenêtre de planification est à l’écran, rien n’est encore envoyé', async () => {
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    expect(await screen.findByText('Planifier la visite technique')).toBeInTheDocument()
    expect(crmApi.marquerRelanceEtapeFait).not.toHaveBeenCalled()
    // La date saisie : UNE requête de planification, qui porte la touche
    // (`etape`) — le serveur la clôt « visite acceptée » lui-même.
    fireEvent.change(screen.getByLabelText(/Date prévue/), { target: { value: jourCasa(3) } })
    fireEvent.click(screen.getByRole('button', { name: 'Planifier la visite' }))
    await waitFor(() => expect(crmApi.planifierVisiteLead).toHaveBeenCalledWith(
      APPEL.lead, { date_prevue: jourCasa(3), etape: APPEL.id }))
    expect(crmApi.marquerRelanceEtapeFait).not.toHaveBeenCalled()
    // La file est relue (la touche close en sort).
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledTimes(2))
  })

  it('« Visite acceptée » puis « Date pas encore fixée » → la réponse part seule (le serveur pose « Planifier la visite »)', async () => {
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Visite acceptée' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Date pas encore fixée' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(
      APPEL.id, { outcome: 'visite_acceptee' }))
  })

  it('étape datée de DEMAIN, appel passé aujourd’hui → l’issue peut être saisie', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue({
      data: { count: 1, results: [{ ...APPEL, due_date: jourCasa(1), overdue: false }] },
    })
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    // « Fait » nu reste caché (CAD44 : on ne coche pas un geste non fait)…
    expect(screen.queryByRole('button', { name: /^Fait$/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Appeler/ }))
    // … mais l'issue d'un appel qui vient d'avoir lieu se saisit.
    const bouton = await screen.findByRole('button', { name: /Saisir l’issue de l’appel/ })
    expect(bouton).not.toBeDisabled()
    fireEvent.click(bouton)
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(
      APPEL.id, { outcome: 'joint' }))
  })

  it('l’étape « Préparer et envoyer le devis » née pour DEMAIN est traitable le jour même (tâche, sans script d’appel d’office)', async () => {
    const devis = {
      ...APPEL, id: APPEL.id + 2000, cadence: 'generique', ordre: 1, cle: 'devis',
      libelle: 'Préparer et envoyer le devis (ou fixer un rappel)', template_cle: '',
      due_date: jourCasa(1), overdue: false,
      due_at: new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
    }
    crmApi.getRelanceEtapesDues.mockResolvedValue({ data: { count: 1, results: [devis] } })
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    expect(screen.queryByTestId('panneau-script-appel')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Sauter/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    expect(screen.getByText('Où en est le devis ?')).toBeInTheDocument()
    // Aucune réponse d'appel sur une tâche qui n'en est pas un.
    expect(screen.queryByRole('button', { name: 'Répondeur' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Devis envoyé — passer à la suite' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(crmApi.marquerRelanceEtapeFait).toHaveBeenCalledWith(devis.id, {}))
  })
})
