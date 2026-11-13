import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
      { ...CONTEXTE_VIDE, ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id })
  })

  it('sans événement, le contexte est la route courante (lead null)', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question, { ...CONTEXTE_VIDE, ecran: window.location.pathname })
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
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/12', lead_id: 12 })
    await user.type(screen.getByPlaceholderText(/Posez votre question/), 'Et le stock ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    await waitFor(() => expect(iaApi.queryAgent).toHaveBeenCalledTimes(2))
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      'Et le stock ?', { ...CONTEXTE_VIDE, ecran: window.location.pathname })
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
      'Résume ce lead', { ...CONTEXTE_VIDE, ecran: '/crm/leads/7', lead_id: 7 })
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
