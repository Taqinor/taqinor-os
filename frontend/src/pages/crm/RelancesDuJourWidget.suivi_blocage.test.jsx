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
   Ces tests montent le VRAI cockpit (crmApi mocké) et exigent le contraire.
   SUIVI-REFUS : « Sauter » et « Reporter » refusés par le serveur (voir la fin
   du fichier). */

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
import { toastError } from '../../lib/toast'
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

/* SUIVI-REFUS (30/09/2026) — double clic sur « Reporter » : le serveur répond
   400 `{erreurs: {etape: "Cette étape est déjà traitée — rechargez la liste."}}`
   (SUIVI E8). Avant : le parent avalait l'erreur de « Sauter » et « Reporter »
   (seul « Fait » la relançait) → panneau refermé « comme réussi » + toast
   générique « Action impossible pour le moment. ». Attendu, comme « Fait » : le
   panneau reste ouvert et le message EXACT du serveur s'affiche sous le geste,
   sans toast générique en plus (le toast ne reste que pour réseau/5xx). */
const DEJA_TRAITEE = 'Cette étape est déjà traitée — rechargez la liste.'
const MESSAGE_ROLE = 'Votre rôle ne permet pas de traiter les relances (responsable ou administrateur requis).'
const refus = (status, data) => ({ response: { status, data } })
const refus400 = (erreurs) => refus(400, { erreurs })

describe('SUIVI-REFUS — cockpit « Relances du jour » : Sauter / Reporter refusés', () => {
  beforeEach(() => {
    crmApi.getRelanceEtapesDues.mockResolvedValue({
      data: { count: 1, results: [{ ...APPEL, due_date: jourCasa(0), overdue: false }] },
    })
  })

  async function ouvrirReporter() {
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Reporter/ }))
    fireEvent.change(screen.getByLabelText('Reporter au'), { target: { value: jourCasa(1) } })
  }
  async function ouvrirSauter() {
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Sauter/ }))
  }
  const confirmer = () => fireEvent.click(screen.getByRole('button', { name: 'Confirmer' }))

  it('« Reporter » refusé (400 erreurs.etape) : panneau ouvert, message exact sous le geste, aucun toast générique', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(crmApi.reporterRelanceEtape).toHaveBeenCalledTimes(1)
    expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      APPEL.id, { rappel_le: jourCasa(1), rappel_heure: '09:00' })
    // Rien n'est refermé « comme réussi » : ni le panneau, ni la ligne.
    expect(screen.getByLabelText('Reporter au')).toHaveValue(jourCasa(1))
    expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
    // Le bouton redevient cliquable (le parent remet `busyId` à null).
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled())
  })

  it('« Sauter » refusé (400 erreurs.etape) : panneau ouvert, message exact sous le geste, aucun toast générique', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    await ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('suite-sauter')).toBeInTheDocument()
    expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
    // La touche n'a pas été traitée : rien à « Annuler ».
    expect(screen.queryByTestId('cad50-annuler-liste')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Confirmer' })).not.toBeDisabled())
  })

  it('« Fait » refusé (400 erreurs.etape) : même traitement — message sous le geste, pas de toast générique en plus', async () => {
    crmApi.marquerRelanceEtapeFait.mockRejectedValueOnce(refus400({ etape: DEJA_TRAITEE }))
    mount()
    await waitFor(() => expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /^Fait$/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Client joint' }))
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(DEJA_TRAITEE)
    expect(toastError).not.toHaveBeenCalled()
  })

  it('« Reporter » refusé pour son rôle (403) : phrase de rôle sous le geste, pas de toast', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus(403, { detail: 'Interdit.' }))
    await ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent(MESSAGE_ROLE)
    expect(toastError).not.toHaveBeenCalled()
  })

  it('« Reporter » : la date refusée par le serveur (erreurs.rappel_le) s’affiche sous « Reporter au »', async () => {
    const refusDate = '« Reporter au » : le 22/09/2026 est déjà passé — choisissez aujourd’hui ou une date à venir.'
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus400({ rappel_le: refusDate }))
    await ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-report-date')).toHaveTextContent(refusDate)
    expect(toastError).not.toHaveBeenCalled()
  })

  it('« Sauter » : un échec RÉSEAU garde son toast (F2) ET la phrase claire sous le geste', async () => {
    crmApi.marquerRelanceEtapeSautee.mockRejectedValueOnce(new Error('Network Error'))
    await ouvrirSauter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent('Pas de connexion au serveur')
    expect(toastError).toHaveBeenCalledWith('Action impossible pour le moment.')
    expect(screen.getByTestId('relance-etape-row')).toBeInTheDocument()
  })

  it('« Reporter » : une 500 garde son toast (F2) ET la phrase claire sous le geste', async () => {
    crmApi.reporterRelanceEtape.mockRejectedValueOnce(refus(500, {}))
    await ouvrirReporter()
    confirmer()
    expect(await screen.findByTestId('erreur-outcome')).toHaveTextContent('Le serveur n’a pas pu enregistrer')
    expect(toastError).toHaveBeenCalledWith('Action impossible pour le moment.')
  })

  // La relecture du cockpit part UNE SECONDE après un geste réussi (une touche
  // peut naître du report / de la clôture). On la prouve par ce qu'elle
  // AFFICHE — une autre touche — et non en comptant les appels du mock partagé :
  // les rechargements différés des tests précédents (instances déjà démontées)
  // l'appellent aussi et faussent tout compteur.
  const SUIVANTE = 'Lead relu (suivante)'
  const servirLaSuivante = () => crmApi.getRelanceEtapesDues.mockResolvedValue({
    data: {
      count: 1,
      results: [{ ...APPEL, id: APPEL.id + 500, lead_nom: SUIVANTE, due_date: jourCasa(0), overdue: false }],
    },
  })

  it('succès « Reporter » inchangé : la ligne est retirée, puis la file relue', async () => {
    await ouvrirReporter()
    servirLaSuivante()
    confirmer()
    await waitFor(() => expect(crmApi.reporterRelanceEtape).toHaveBeenCalledWith(
      APPEL.id, { rappel_le: jourCasa(1), rappel_heure: '09:00' }))
    await waitFor(() => expect(screen.queryByTestId('relance-etape-row')).not.toBeInTheDocument())
    expect(toastError).not.toHaveBeenCalled()
    expect(await screen.findByText(SUIVANTE, {}, { timeout: 4000 })).toBeInTheDocument()
  })

  it('succès « Sauter » inchangé : la ligne est retirée, « Annuler » (24 h) proposé, puis la file relue', async () => {
    await ouvrirSauter()
    servirLaSuivante()
    confirmer()
    await waitFor(() => expect(crmApi.marquerRelanceEtapeSautee).toHaveBeenCalledWith(APPEL.id, ''))
    await waitFor(() => expect(screen.queryByTestId('relance-etape-row')).not.toBeInTheDocument())
    expect(screen.getByTestId('cad50-annuler-liste')).toBeInTheDocument()
    expect(toastError).not.toHaveBeenCalled()
    expect(await screen.findByText(SUIVANTE, {}, { timeout: 4000 })).toBeInTheDocument()
  })
})
