import { describe, it, expect, vi, beforeEach } from 'vitest'
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

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
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
      { ecran: CONTRAT.exemple.ecran, lead_id: CONTRAT.exemple.lead_id })
  })

  it('sans événement, le contexte est la route courante (lead null)', async () => {
    const user = userEvent.setup()
    monter()
    await poserUneQuestion(user)
    expect(iaApi.queryAgent).toHaveBeenLastCalledWith(
      CONTRAT.exemple.question, { ecran: window.location.pathname, lead_id: null })
  })

  it('affiche les trois questions du manifeste pour l\'écran', async () => {
    iaApi.getSuggestions.mockResolvedValue({ data: ['Q1 du lead ?', 'Q2 du lead ?', 'Q3 du lead ?'] })
    monter()
    await screen.findByRole('button', { name: 'Q1 du lead ?' })
    expect(screen.getByRole('button', { name: 'Q3 du lead ?' })).toBeTruthy()
    expect(iaApi.getSuggestions).toHaveBeenCalledWith(window.location.pathname)
  })
})
