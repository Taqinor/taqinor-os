// AG11/AG12 — Tests d'intégration des contrôles VOIX dans AgentChat. On MOCKE le
// hook useVoiceChat pour piloter les états (support, recording, conversation…) de
// façon déterministe, et on vérifie que :
//   • le bouton micro + la bascule « Mode conversation » apparaissent quand le
//     navigateur les supporte, et DISPARAISSENT sinon (repli texte intact) ;
//   • les cartes AG3 (proposition / résultat) restent rendues à côté de la voix ;
//   • le bandeau d'état vocal s'affiche (écoute / transcription / lecture / attente).

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

// iaApi mocké (aucun réseau).
vi.mock('../../api/iaApi', () => ({
  default: {
    queryAgent: vi.fn(() => Promise.resolve({ data: { answer: '' } })),
    getChatHistory: vi.fn(() => Promise.resolve({ data: [] })),
    clearChatHistory: vi.fn(() => Promise.resolve({})),
    confirmAction: vi.fn(() => Promise.resolve({ data: { ok: true } })),
    transcribeVoice: vi.fn(() => Promise.resolve({ data: { text: '' } })),
  },
}))

// Hook voix mocké : on contrôle entièrement ce qu'il expose.
const voiceState = {
  recordingSupported: true,
  speechSupported: true,
  conversationSupported: true,
  recording: false,
  transcribing: false,
  speaking: false,
  voiceError: null,
  conversationMode: false,
  loopState: 'idle',
  toggleRecording: vi.fn(),
  startConversation: vi.fn(),
  stopConversation: vi.fn(),
  confirmByVoiceTap: vi.fn(),
}
vi.mock('../../features/ia/voice/useVoiceChat', () => ({
  __esModule: true,
  default: () => voiceState,
}))

import iaReducer from '../../features/ia/store/iaSlice'
import AgentChat from './AgentChat'

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  // Réinitialise l'état voix par défaut entre tests.
  Object.assign(voiceState, {
    recordingSupported: true, speechSupported: true, conversationSupported: true,
    recording: false, transcribing: false, speaking: false, voiceError: null,
    conversationMode: false, loopState: 'idle',
  })
  voiceState.toggleRecording.mockClear()
  voiceState.startConversation.mockClear()
  voiceState.stopConversation.mockClear()
})

function makeStore(messages = []) {
  return configureStore({
    reducer: { ia: iaReducer },
    preloadedState: { ia: { ...iaReducer(undefined, { type: '@@INIT' }), messages } },
  })
}

function renderChat(messages) {
  const store = makeStore(messages)
  render(<Provider store={store}><AgentChat /></Provider>)
  return store
}

describe('AgentChat — contrôles voix (AG11)', () => {
  it('affiche le bouton micro quand l\'enregistrement est supporté', () => {
    renderChat()
    expect(screen.getByTestId('mic-button')).toBeInTheDocument()
  })

  it('clic sur le micro appelle toggleRecording', async () => {
    renderChat()
    await userEvent.click(screen.getByTestId('mic-button'))
    expect(voiceState.toggleRecording).toHaveBeenCalledTimes(1)
  })

  it('repli : pas de bouton micro quand l\'enregistrement n\'est pas supporté', () => {
    voiceState.recordingSupported = false
    renderChat()
    expect(screen.queryByTestId('mic-button')).not.toBeInTheDocument()
    // La saisie texte reste disponible (repli).
    expect(screen.getByPlaceholderText(/Posez votre question/)).toBeInTheDocument()
  })

  it('bandeau d\'état : « Écoute en cours… » pendant l\'enregistrement', () => {
    voiceState.recording = true
    renderChat()
    expect(screen.getByTestId('voice-status')).toHaveTextContent(/Écoute en cours/)
  })

  it('bandeau d\'état : erreur vocale affichée', () => {
    voiceState.voiceError = 'Transcription vocale indisponible.'
    renderChat()
    expect(screen.getByTestId('voice-status')).toHaveTextContent(/indisponible/)
  })
})

describe('AgentChat — mode conversation (AG12)', () => {
  it('affiche la bascule « Mode conversation » quand supporté', () => {
    renderChat()
    expect(screen.getByTestId('conversation-toggle')).toBeInTheDocument()
  })

  it('clic démarre la conversation', async () => {
    renderChat()
    await userEvent.click(screen.getByTestId('conversation-toggle'))
    expect(voiceState.startConversation).toHaveBeenCalledTimes(1)
  })

  it('en mode conversation : bouton Arrêter visible + micro masqué', () => {
    voiceState.conversationMode = true
    renderChat()
    expect(screen.getByTestId('conversation-stop')).toBeInTheDocument()
    // En mode conversation, le micro manuel est masqué (la boucle pilote le micro).
    expect(screen.queryByTestId('mic-button')).not.toBeInTheDocument()
  })

  it('Arrêter appelle stopConversation', async () => {
    voiceState.conversationMode = true
    renderChat()
    await userEvent.click(screen.getByTestId('conversation-stop'))
    expect(voiceState.stopConversation).toHaveBeenCalledTimes(1)
  })

  it('bandeau « attente de confirmation » quand la boucle attend un « confirmer »', () => {
    voiceState.conversationMode = true
    voiceState.loopState = 'awaiting_confirm'
    renderChat()
    expect(screen.getByTestId('voice-status')).toHaveTextContent(/confirmer/i)
  })

  it('repli : pas de bascule conversation quand non supporté', () => {
    voiceState.conversationSupported = false
    renderChat()
    expect(screen.queryByTestId('conversation-toggle')).not.toBeInTheDocument()
  })
})

describe('AgentChat — les cartes AG3 restent intactes avec la voix', () => {
  it('la carte proposition reste rendue (la voix ne la casse pas)', () => {
    renderChat([
      { role: 'agent', kind: 'proposal', content: '', human_preview: 'Envoyer le devis ?', confirm_token: 'tok-1' },
    ])
    expect(screen.getByTestId('proposal-card')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Confirmer/ })).toBeInTheDocument()
  })

  it('la carte résultat reste rendue', () => {
    renderChat([
      { role: 'agent', kind: 'result', content: '', reference: 'DEV-1', proposal_url: '/api/django/ventes/devis/1/proposal/' },
    ])
    expect(screen.getByTestId('result-card')).toBeInTheDocument()
  })
})
