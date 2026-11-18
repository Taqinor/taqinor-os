import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// AIC8 — contrat partagé (PACT10/PACT13) : la réponse de la note vient de
// l'exemple committé, jamais d'une charge utile tapée à la main.
import CONTRAT from '../../../../backend/django_core/apps/agent/contract_samples/assistant_evenement.json'

vi.mock('../../api/iaApi', () => ({
  default: {
    queryAgent: vi.fn(),
    getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
    clearChatHistory: vi.fn(() => Promise.resolve({})),
    noterEvenement: vi.fn(),
    getSuggestions: vi.fn(),
  },
}))

import iaApi from '../../api/iaApi'
import iaReducer from './store/iaSlice'
import CopilotPanel from './CopilotPanel'
import { EVENEMENT_OUVRIR } from './copilotMessages'
import {
  installerEcouteurOuverture, reinitialiserEcouteurOuverture,
} from './ecouteurOuverture'
// TCH118 / A12 — les quatre demandes prêtes de Tâches (client Tâches mocké sur les contrats committés).
import { MemoryRouter } from 'react-router-dom'
import * as tachesApi from '../../api/tachesApi'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/tachesApi', () => ({
  proposerJournee: vi.fn(), lirePriorites: vi.fn(), lirePoint: vi.fn(), saisieRapide: vi.fn(),
  listerToutesLesTaches: vi.fn(), lireAujourdhui: vi.fn(),
}))

/* Nouveau fichier car : aucun module vitest n'héberge le panneau Copilote
   (copilotMessages.test.mjs est un test node pur, sans DOM). */

const EVENEMENT_ID = CONTRAT.exemple.id

function monter({ ouvert = true } = {}) {
  const initial = iaReducer(undefined, { type: '@@init' })
  const store = configureStore({
    reducer: { ia: iaReducer },
    preloadedState: { ia: { ...initial, copilotOpen: ouvert } },
  })
  render(<Provider store={store}><CopilotPanel /></Provider>)
  return store
}

const CONTEXTE_VIDE = { lead_id: null, devis_id: null, touche_id: null, diagnostic: null }

afterEach(() => { reinitialiserEcouteurOuverture() })

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  iaApi.queryAgent.mockClear()
  iaApi.noterEvenement.mockClear()
  iaApi.queryAgent.mockResolvedValue({
    data: { answer: CONTRAT.exemple.resume_reponse, evenement_id: EVENEMENT_ID },
  })
  iaApi.noterEvenement.mockResolvedValue({ data: CONTRAT.ecriture_commercial.exemple })
  iaApi.getSuggestions.mockResolvedValue({ data: [] })
})

async function poserUneQuestion(user) {
  await user.type(screen.getByPlaceholderText(/Posez votre question/), CONTRAT.exemple.question)
  await user.click(screen.getByRole('button', { name: 'Envoyer' }))
  await screen.findByText(CONTRAT.exemple.resume_reponse)
}

describe('CopilotPanel — note de la réponse (AIC8)', () => {
  it('clic 👎 puis Envoyer ⇒ noterEvenement(id, −1) et « merci »', async () => {
    const user = userEvent.setup()
    const store = monter()
    await poserUneQuestion(user)
    await user.click(screen.getByRole('button', { name: 'Réponse fausse' }))
    await user.type(screen.getByLabelText('Commentaire sur la réponse'),
      CONTRAT.ecriture_commercial.exemple_corps.commentaire)
    await user.click(screen.getByRole('button', { name: 'Envoyer le retour' }))
    expect(iaApi.noterEvenement).toHaveBeenCalledWith(
      EVENEMENT_ID, -1, CONTRAT.ecriture_commercial.exemple_corps.commentaire)
    await screen.findByText('Merci pour votre retour.')
    const dernier = store.getState().ia.messages.at(-1)
    expect(dernier.note).toBe(-1)
    expect(dernier.evenement_id).toBe(EVENEMENT_ID)
  })

  it('clic 👍 ⇒ noterEvenement(id, 1) sans commentaire', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    await user.click(screen.getByRole('button', { name: 'Réponse utile' }))
    await waitFor(() => expect(iaApi.noterEvenement).toHaveBeenLastCalledWith(EVENEMENT_ID, 1, null))
  })

  it('aucune note proposée sans événement journalisé', async () => {
    iaApi.queryAgent.mockResolvedValue({ data: { answer: 'Sans journal.' } })
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'bonjour')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await screen.findByText('Sans journal.')
    expect(screen.queryByTestId('note-reponse')).toBeNull()
  })
})

describe('CopilotPanel — entrée contextuelle (AIC9)', () => {
  it('l\'événement EVENEMENT_OUVRIR ouvre le panneau et transmet le contexte', async () => {
    const store = monter({ ouvert: false })
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id,
        question: CONTRAT.exemple.question, envoyer: true },
    }))
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(store.getState().ia.copilotOpen).toBe(true)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question,
      { ...CONTEXTE_VIDE, ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id }, expect.any(String))
  })

  it('sans événement, le contexte est la route courante (lead null)', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question, { ...CONTEXTE_VIDE, ecran: window.location.pathname }, expect.any(String))
  })

  it('affiche les trois questions du manifeste pour l\'écran', async () => {
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 du lead ?', 'Q2 du lead ?', 'Q3 du lead ?'] })
    monter()
    await screen.findByRole('button', { name: 'Q1 du lead ?' })
    expect(screen.getByRole('button', { name: 'Q3 du lead ?' })).toBeTruthy()
    expect(iaApi.getSuggestions).toHaveBeenCalledWith(window.location.pathname)
  })
})

describe('CopilotPanel — contexte lu à l\'envoi (COP-F5)', () => {
  it('le contexte d\'un événement ne vaut que pour SA question : la suivante repart de la route', async () => {
    const user = userEvent.setup()
    monter({ ouvert: false })
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: '/crm/leads/12', lead_id: 12, question: 'Résume ce lead', envoyer: true },
    }))
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/12', lead_id: 12 }, expect.any(String))
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Et le stock ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(2))
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Et le stock ?', { ...CONTEXTE_VIDE, ecran: window.location.pathname }, expect.any(String))
  })

  it('PREMIER clic : une demande émise AVANT le montage du panneau ouvre le tiroir et envoie', async () => {
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({ reducer: { ia: iaReducer }, preloadedState: { ia: initial } })
    installerEcouteurOuverture(() => Promise.resolve({ store }))
    window.dispatchEvent(new CustomEvent(EVENEMENT_OUVRIR, {
      detail: { ecran: '/crm/leads/7', lead_id: 7, question: 'Résume ce lead', envoyer: true },
    }))
    await waitFor(() => expect(store.getState().ia.copilotOpen).toBe(true))
    // Le panneau (lazy dans l'app) se monte APRÈS : il reprend la demande en attente.
    render(<Provider store={store}><CopilotPanel /></Provider>)
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    expect(iaApi.queryAgent).toHaveBeenCalledTimes(1)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/7', lead_id: 7 }, expect.any(String))
  })
})

describe('CopilotPanel — « Signaler un bug » (COP-F7)', () => {
  it('une phrase libre part avec le tampon technique dans contexte.diagnostic', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(screen.getByRole('button', { name: 'Signaler un bug' }))
    await user.type(screen.getByLabelText('Que faisiez-vous ?'), 'Je cliquais sur Fait')
    await user.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(1))
    const [question, contexte] = iaApi.queryAgent.mock.calls[0]
    expect(question).toBe('Signaler un bug : Je cliquais sur Fait')
    expect(Array.isArray(contexte.diagnostic.requetes)).toBe(true)
    expect(Array.isArray(contexte.diagnostic.erreurs)).toBe(true)
  })

  it('le même tampon part tout seul quand le message dit une panne, jamais sinon', async () => {
    const user = userEvent.setup()
    monter()
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Le bouton Fait ne marche pas')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(1))
    expect(iaApi.queryAgent.mock.calls[0][1].diagnostic).not.toBeNull()
    await screen.findByText(CONTRAT.exemple.resume_reponse)
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Combien de leads aujourd\'hui ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(2))
    expect(iaApi.queryAgent.mock.calls[1][1].diagnostic).toBeNull()
  })
})

describe('CopilotPanel — les quatre demandes prêtes de Tâches (A12, TCH118)', () => {
  const contrat = (nom) => ({ data: structuredClone(exempleContrat('taches', nom)) })
  const DEMANDES = ['Planifie ma journée', 'Aide-moi à prioriser', 'Range ma liste', 'Où j\'en suis ?']

  function monterAvecDroits(permissions) {
    const initial = iaReducer(undefined, { type: '@@init' })
    const store = configureStore({
      reducer: { ia: iaReducer, auth: (etat = { permissions }) => etat },
      preloadedState: { ia: { ...initial, copilotOpen: true } },
    })
    render(<Provider store={store}><MemoryRouter><CopilotPanel /></MemoryRouter></Provider>)
    return store
  }

  beforeEach(() => {
    vi.clearAllMocks() // appels comptés par test (les réponses posées plus haut restent)
    tachesApi.proposerJournee.mockResolvedValue(contrat('journee_proposition'))
    tachesApi.lirePriorites.mockResolvedValue(contrat('priorites'))
    tachesApi.lirePoint.mockResolvedValue(contrat('point'))
    tachesApi.saisieRapide.mockResolvedValue(contrat('saisie_apercu'))
    tachesApi.listerToutesLesTaches.mockResolvedValue([exempleContrat('taches', 'tache')])
    tachesApi.lireAujourdhui.mockResolvedValue(contrat('aujourdhui'))
    iaApi.getSuggestions.mockRejectedValue(new Error('service IA injoignable'))
  })

  // F3 acceptation ERR 3 — textes du panneau ouvert depuis un écran Tâches (textes.md §5.2), mot pour mot.
  it('ERR 3 — sur /taches : sous-titre « ouvert depuis {écran} » et champ « Écris ou dicte… »', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('group', { name: 'Demandes prêtes' })
    expect(screen.getByText('ouvert depuis À trier')).toBeTruthy()
    expect(screen.getByPlaceholderText('Écris ou dicte…')).toBeTruthy()
    expect(screen.queryByText(/Posez une question sur vos données/)).toBeNull()
  })

  it('ERR 3 — hors /taches, rien ne change (sous-titre et champ de l’ERP)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?'] })
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(screen.getByText('Posez une question sur vos données — réponses en temps réel.')).toBeTruthy()
    expect(screen.getByPlaceholderText('Posez votre question en français…')).toBeTruthy()
    expect(screen.queryByText(/ouvert depuis/)).toBeNull()
  })

  it('ERR 3 — « Planifie ma journée » répond « Tu as gardé {e} essentielles… » avec les nombres du serveur', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    const store = monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Planifie ma journée' }))
    await screen.findByTestId('carte-taches-plan_propose')
    // aujourdhui.json : essentiel_prevues 1 ; journee_proposition.json : objectif 5, 2 lignes.
    const attendu = 'Tu as gardé 1 essentielle. Pour atteindre 5, voici 2 tâches de plus, dans cet ordre. '
      + 'Rien ne change tant que tu ne gardes pas.'
    expect(store.getState().ia.messages[1].content).toBe(attendu)
    expect(screen.getByText(attendu)).toBeTruthy()
  })

  it('ERR 3 — sans clé d’IA, la ligne « Écris ou dicte… » devient la phrase de §5.2 ; hors /taches rien ne change', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    iaApi.queryAgent.mockResolvedValue({ data: {
      answer: "L'assistant n'est pas disponible pour le moment (réglage du serveur). Le problème est signalé à "
        + "l'administrateur ; réessaie plus tard.", evenement_id: null } })
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.type(screen.getByPlaceholderText('Écris ou dicte…'), 'bonjour')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    expect(await screen.findByText(
      "La conversation libre n'est pas branchée sur ce serveur. Les quatre demandes ci-dessus marchent sans elle.",
    )).toBeTruthy()
    expect(screen.queryByPlaceholderText('Écris ou dicte…')).toBeNull()
    for (const q of DEMANDES) expect(screen.getByRole('button', { name: q })).toBeTruthy()
  })

  afterEach(() => { window.history.pushState({}, '', '/') })

  it('sur /taches, les quatre demandes sont là même si le service d\'IA ne répond pas', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    monterAvecDroits(['taches_voir'])
    const liste = await screen.findByRole('group', { name: 'Demandes prêtes' })
    for (const q of DEMANDES) expect(within(liste).getByRole('button', { name: q })).toBeTruthy()
    expect(iaApi.getSuggestions).not.toHaveBeenCalled()
  })

  it('« Aide-moi à prioriser » appelle la route déterministe et rend la carte, sans modèle', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    const user = userEvent.setup()
    const store = monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Aide-moi à prioriser' }))
    await screen.findByTestId('carte-taches-priorites')
    expect(tachesApi.lirePriorites).toHaveBeenCalledTimes(1)
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
    const [question, reponse] = store.getState().ia.messages
    expect(question).toEqual({ role: 'user', content: 'Aide-moi à prioriser' })
    expect(reponse.cartes[0].donnees).toEqual(exempleContrat('taches', 'priorites'))
  })

  it('« Range ma liste » range les ids À trier lus à l\'API Tâches (jamais devinés)', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Range ma liste' }))
    await screen.findByTestId('carte-taches-capture_apercu')
    expect(tachesApi.listerToutesLesTaches).toHaveBeenCalledWith({ vue: 'boite' })
    expect(tachesApi.saisieRapide).toHaveBeenCalledWith({
      ids: [exempleContrat('taches', 'tache').id], apercu: true })
    expect(iaApi.queryAgent).not.toHaveBeenCalled()
  })

  it('« Range ma liste » sans tâche À trier : « Rien à trier », aucun aperçu', async () => {
    window.history.pushState({}, '', '/taches/a-trier')
    tachesApi.listerToutesLesTaches.mockResolvedValue([])
    const user = userEvent.setup()
    monterAvecDroits(['taches_voir'])
    await user.click(screen.getByRole('button', { name: 'Range ma liste' }))
    await screen.findByText('Rien à trier')
    expect(tachesApi.saisieRapide).not.toHaveBeenCalled()
  })

  it('hors /taches : comportement identique (pas de demandes prêtes, suggestions du manifeste)', async () => {
    window.history.pushState({}, '', '/crm/relances')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?', 'Q2 ?', 'Q3 ?'] })
    monterAvecDroits(['taches_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(iaApi.getSuggestions).toHaveBeenCalledWith('/crm/relances')
    expect(screen.queryByRole('group', { name: 'Demandes prêtes' })).toBeNull()
  })

  it('sur /taches sans le droit taches_voir : pas de demandes prêtes', async () => {
    window.history.pushState({}, '', '/taches/aujourdhui')
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 ?'] })
    monterAvecDroits(['crm_voir'])
    await screen.findByRole('button', { name: 'Q1 ?' })
    expect(screen.queryByRole('group', { name: 'Demandes prêtes' })).toBeNull()
  })
})
