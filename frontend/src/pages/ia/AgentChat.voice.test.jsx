// AG11/AG12 — Tests d'intégration des contrôles VOIX dans AgentChat. On MOCKE le
// hook useVoiceChat pour piloter les états (support, recording, conversation…) de
// façon déterministe, et on vérifie que :
//   • le bouton micro + la bascule « Mode conversation » apparaissent quand le
//     navigateur les supporte, et DISPARAISSENT sinon (repli texte intact) ;
//   • les cartes AG3 (proposition / résultat) restent rendues à côté de la voix ;
//   • le bandeau d'état vocal s'affiche (écoute / transcription / lecture / attente).

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
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
  // COP-F6 : on garde les `deps` reçus (rappel `onTexte` de la dictée).
  default: (deps) => { voiceState.deps = deps; return voiceState },
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
    // AIC12 — AgentChat lit `auth.role` (useIsAdmin) : la tranche auth est requise.
    reducer: { ia: iaReducer, auth: (state = { role: 'normal' }) => state },
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

  it('COP-F6 : aucun bandeau « dites confirmer » (la confirmation est un geste du doigt)', () => {
    voiceState.conversationMode = true
    voiceState.loopState = 'awaiting_confirm'
    renderChat()
    expect(screen.queryByTestId('voice-status')).not.toBeInTheDocument()
  })

  it('repli : pas de bascule conversation quand non supporté', () => {
    voiceState.conversationSupported = false
    renderChat()
    expect(screen.queryByTestId('conversation-toggle')).not.toBeInTheDocument()
  })
})

describe('AgentChat — dictée (COP-F6)', () => {
  it('le texte dicté REMPLIT la zone de saisie sans partir tout seul', () => {
    renderChat()
    act(() => { voiceState.deps.onTexte('bonjour la dictée') })
    expect(screen.getByPlaceholderText(/Posez votre question/)).toHaveValue('bonjour la dictée')
    act(() => { voiceState.deps.onTexte('suite') })
    expect(screen.getByPlaceholderText(/Posez votre question/)).toHaveValue('bonjour la dictée suite')
  })
})

describe('AgentChat — les cartes restent intactes avec la voix', () => {
  it('la carte proposition reste rendue (la voix ne la casse pas)', () => {
    renderChat([{
      role: 'agent', content: '',
      cartes: [{
        type: 'proposition', action_key: 'x', libelle: 'X', apercu: 'Envoyer le devis ?',
        confirm_token: 'tok-1', expire_dans_s: 300, expire_le: Date.now() + 300000, etat: 'a_confirmer',
      }],
    }])
    expect(screen.getByTestId('proposal-card')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Confirmer/ })).toBeInTheDocument()
  })

  it('la carte résultat reste rendue', () => {
    renderChat([{
      role: 'agent', content: '',
      cartes: [{ type: 'resultat', action_key: 'x', libelle: 'X', carte: null, donnees: { reference: 'DEV-1' } }],
    }])
    expect(screen.getByTestId('result-card')).toBeInTheDocument()
  })
})
