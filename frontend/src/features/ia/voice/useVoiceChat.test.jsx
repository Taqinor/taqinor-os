// AG11/AG12 — Tests du hook voix (Vitest + jsdom). Toutes les API navigateur
// (MediaRecorder, getUserMedia, speechSynthesis, AudioContext) sont MOCKÉES via
// l'injection `deps.env`, donc le test tourne headless. On couvre :
//   • les helpers purs (support, choix de voix, MIME, RMS),
//   • le repli navigateur non supporté (recordingSupported=false),
//   • le happy path AG11 (capture → transcribe → zone de saisie, COP-F6 : la
//     dictée ne part plus toute seule),
//   • le garde-fou de sécurité AG12/COP-F6 (aucune confirmation à la voix).

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import React from 'react'

import iaReducer, { confirmAgentAction, ajouterMessageLocal } from '../store/iaSlice'
import { ETATS } from '../cartes/cartes'
import {
  useVoiceChat,
  propositionsConfirmees,
  accuseDeConfirmation,
  isRecordingSupported,
  isSpeechSynthesisSupported,
  isSilenceDetectionSupported,
  pickFrenchVoice,
  pickAudioMimeType,
  filenameForMime,
  computeRms,
} from './useVoiceChat'

// ── Helpers purs ──────────────────────────────────────────────────────────────
describe('useVoiceChat — helpers purs', () => {
  it('isRecordingSupported détecte getUserMedia + MediaRecorder', () => {
    expect(isRecordingSupported({})).toBe(false)
    expect(isRecordingSupported({
      navigator: { mediaDevices: { getUserMedia: () => {} } },
      MediaRecorder: function () {},
    })).toBe(true)
  })

  it('isSpeechSynthesisSupported / isSilenceDetectionSupported gardent les API absentes', () => {
    expect(isSpeechSynthesisSupported({})).toBe(false)
    expect(isSpeechSynthesisSupported({ speechSynthesis: {}, SpeechSynthesisUtterance: function () {} })).toBe(true)
    expect(isSilenceDetectionSupported({})).toBe(false)
    expect(isSilenceDetectionSupported({ AudioContext: function () {} })).toBe(true)
    expect(isSilenceDetectionSupported({ webkitAudioContext: function () {} })).toBe(true)
  })

  it('pickFrenchVoice choisit une voix FR, sinon la première, sinon null', () => {
    expect(pickFrenchVoice([{ lang: 'en-US' }, { lang: 'fr-FR', name: 'Amelie' }]).name).toBe('Amelie')
    expect(pickFrenchVoice([{ lang: 'en-US', name: 'A' }]).name).toBe('A')
    expect(pickFrenchVoice([])).toBe(null)
    expect(pickFrenchVoice(null)).toBe(null)
  })

  it('pickAudioMimeType retourne le 1er type supporté', () => {
    const MR = { isTypeSupported: (t) => t === 'audio/webm' }
    expect(pickAudioMimeType(MR)).toBe('audio/webm')
    expect(pickAudioMimeType({})).toBe('')
  })

  it('filenameForMime mappe le type sur une extension', () => {
    expect(filenameForMime('audio/webm;codecs=opus')).toBe('audio.webm')
    expect(filenameForMime('audio/ogg')).toBe('audio.ogg')
    expect(filenameForMime('audio/mp4')).toBe('audio.mp4')
    expect(filenameForMime('')).toBe('audio.webm')
  })

  it('computeRms calcule la moyenne quadratique', () => {
    expect(computeRms([])).toBe(0)
    expect(computeRms([0, 0, 0])).toBe(0)
    expect(computeRms([1, -1, 1, -1])).toBeCloseTo(1, 5)
  })
})

// ── Harnais hook ────────────────────────────────────────────────────────────
function makeStore(messages = null) {
  if (!messages) return configureStore({ reducer: { ia: iaReducer } })
  const initial = iaReducer(undefined, { type: '@@INIT' })
  return configureStore({ reducer: { ia: iaReducer }, preloadedState: { ia: { ...initial, messages } } })
}

function wrapper(store) {
  return ({ children }) => <Provider store={store}>{children}</Provider>
}

// Construit un `env` mock complet (toutes les API présentes).
function makeMockEnv({ recorder } = {}) {
  const rec = recorder || makeMockRecorder()
  // MediaRecorder doit être CONSTRUCTIBLE (`new`). On expose une fonction
  // constructeur qui renvoie toujours le recorder mock partagé.
  function MockMediaRecorder() { return rec }
  MockMediaRecorder.isTypeSupported = () => true
  return {
    navigator: { mediaDevices: { getUserMedia: vi.fn(() => Promise.resolve(makeMockStream())) } },
    MediaRecorder: MockMediaRecorder,
    _recorder: rec,
    speechSynthesis: { speak: vi.fn(), cancel: vi.fn(), getVoices: () => [{ lang: 'fr-FR', name: 'FR' }] },
    SpeechSynthesisUtterance: function (t) { this.text = t },
    AudioContext: function () {
      return {
        createMediaStreamSource: () => ({ connect: () => {} }),
        createAnalyser: () => ({ fftSize: 0, connect: () => {}, getFloatTimeDomainData: () => {}, disconnect: () => {} }),
        close: () => {},
      }
    },
    requestAnimationFrame: vi.fn(),
    cancelAnimationFrame: vi.fn(),
    Blob: function (chunks, opts) { this.chunks = chunks; this.type = opts?.type; this.size = 1 },
  }
}

function makeMockStream() {
  return { getTracks: () => [{ stop: vi.fn() }] }
}

function makeMockRecorder() {
  const r = {
    state: 'inactive',
    mimeType: 'audio/webm',
    ondataavailable: null,
    onstop: null,
    start: vi.fn(function () { r.state = 'recording' }),
    stop: vi.fn(function () { r.state = 'inactive'; r.onstop?.() }),
  }
  return r
}

describe('useVoiceChat — repli navigateur non supporté', () => {
  it('expose recordingSupported=false quand les API manquent (repli texte)', () => {
    const store = makeStore()
    const { result } = renderHook(() => useVoiceChat({ env: {} }), { wrapper: wrapper(store) })
    expect(result.current.recordingSupported).toBe(false)
    expect(result.current.speechSupported).toBe(false)
    expect(result.current.conversationSupported).toBe(false)
  })
})

describe('useVoiceChat — happy path AG11 (capture → transcribe → zone de saisie)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('un tour micro transcrit puis REMPLIT la saisie (aucune question envoyée seule)', async () => {
    const store = makeStore()
    const env = makeMockEnv()
    const transcribe = vi.fn(() => Promise.resolve({ data: { text: 'combien de clients', language: 'fr' } }))
    const onTexte = vi.fn()
    const { result } = renderHook(
      () => useVoiceChat({ env, transcribe, onTexte }),
      { wrapper: wrapper(store) },
    )
    expect(result.current.recordingSupported).toBe(true)

    // Démarre la capture (startCapture est async — on attend qu'elle se règle).
    await act(async () => { result.current.toggleRecording() })
    await waitFor(() => expect(result.current.recording).toBe(true))
    expect(env.navigator.mediaDevices.getUserMedia).toHaveBeenCalled()

    // Stoppe → déclenche onstop → transcribe → queryAgent.
    await act(async () => { result.current.toggleRecording() })
    await waitFor(() => expect(transcribe).toHaveBeenCalled())

    // COP-F6 : le texte est remis à l'écran pour relecture ; rien n'est envoyé.
    await waitFor(() => expect(onTexte).toHaveBeenCalledWith('combien de clients'))
    expect(store.getState().ia.messages).toEqual([])
  })

  it('transcription indisponible (available:false) → erreur visible, pas de question', async () => {
    const store = makeStore()
    const env = makeMockEnv()
    const transcribe = vi.fn(() => Promise.resolve({ data: { available: false, detail: 'Clé manquante.' } }))
    const { result } = renderHook(() => useVoiceChat({ env, transcribe }), { wrapper: wrapper(store) })
    await act(async () => { result.current.toggleRecording() })
    await waitFor(() => expect(result.current.recording).toBe(true))
    await act(async () => { result.current.toggleRecording() })
    await waitFor(() => expect(result.current.voiceError).toBe('Clé manquante.'))
    expect(store.getState().ia.messages.length).toBe(0)
  })
})

describe('useVoiceChat — sécurité AG12 (pas d\'auto-confirmation)', () => {
  it('startConversation est inopérant si le mode n\'est pas supporté', () => {
    const store = makeStore()
    const env = { ...makeMockEnv(), AudioContext: undefined, webkitAudioContext: undefined }
    const { result } = renderHook(() => useVoiceChat({ env }), { wrapper: wrapper(store) })
    expect(result.current.conversationSupported).toBe(false)
    act(() => { result.current.startConversation() })
    expect(result.current.conversationMode).toBe(false)
    expect(result.current.voiceError).toMatch(/mode conversation/i)
  })

  it('COP-F6 : propositionsConfirmees compte les cartes confirmées et rend le dernier libellé', () => {
    expect(propositionsConfirmees(null)).toEqual({ nombre: 0, libelle: '' })
    const messages = [
      { role: 'agent', cartes: [{ type: 'proposition', etat: ETATS.A_CONFIRMER, libelle: 'A' }] },
      { role: 'agent', cartes: [
        { type: 'proposition', etat: ETATS.CONFIRMEE, libelle: 'Appliquer une remise au devis' },
        { type: 'resultat', etat: ETATS.CONFIRMEE, libelle: 'jamais compté' },
      ] },
    ]
    expect(propositionsConfirmees(messages)).toEqual({ nombre: 1, libelle: 'Appliquer une remise au devis' })
    expect(accuseDeConfirmation('Appliquer une remise au devis')).toBe('C’est fait : Appliquer une remise au devis.')
    expect(accuseDeConfirmation('')).toBe('Action effectuée.')
  })

  it('COP-F6 : confirmée au doigt en mode conversation, sans nouveau message → l\'accusé est lu', async () => {
    // Moteur sans reprise (LangChain) : /confirm ne pousse aucun message, la
    // carte change seulement d'état — c'est ce changement qui déclenche la lecture.
    const store = makeStore([
      { role: 'user', content: 'fais une remise de 2 %' },
      { role: 'agent', content: '', cartes: [
        { type: 'proposition', etat: ETATS.A_CONFIRMER, libelle: 'Appliquer une remise au devis', confirm_token: 'j' },
      ] },
    ])
    const env = makeMockEnv()
    const { result } = renderHook(() => useVoiceChat({ env, transcribe: vi.fn() }), { wrapper: wrapper(store) })
    await act(async () => { result.current.startConversation() })
    expect(result.current.conversationMode).toBe(true)
    expect(env.speechSynthesis.speak).not.toHaveBeenCalled()
    await act(async () => {
      store.dispatch({
        type: confirmAgentAction.fulfilled.type,
        payload: { ok: true, action_key: 'ventes.devis.remise', data: {} },
        meta: { arg: { token: 'j', index: 1, carte: 0 } },
      })
    })
    expect(store.getState().ia.messages).toHaveLength(2)
    await waitFor(() => expect(env.speechSynthesis.speak).toHaveBeenCalledTimes(1))
    expect(env.speechSynthesis.speak.mock.calls[0][0].text).toBe('C’est fait : Appliquer une remise au devis.')
    // Une proposition DÉJÀ confirmée avant l'ouverture du mode n'est jamais relue.
    act(() => { result.current.stopConversation() })
    await act(async () => { result.current.startConversation() })
    expect(env.speechSynthesis.speak).toHaveBeenCalledTimes(1)
    act(() => { result.current.stopConversation() })
  })

  it('COP-F6 : une carte posée par un bouton (message local) ne lit rien et n\'ouvre pas une seconde capture', async () => {
    const store = makeStore([{ role: 'user', content: 'ma file' }, { role: 'agent', content: 'Voici.', cartes: [] }])
    const env = makeMockEnv()
    const { result } = renderHook(() => useVoiceChat({ env, transcribe: vi.fn() }), { wrapper: wrapper(store) })
    await act(async () => { result.current.startConversation() })
    await waitFor(() => expect(env.navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1))
    await act(async () => {
      store.dispatch(ajouterMessageLocal({ role: 'agent', content: '', local: true, cartes: [] }))
    })
    expect(store.getState().ia.messages).toHaveLength(3)
    expect(env.speechSynthesis.speak).not.toHaveBeenCalled()
    expect(env.navigator.mediaDevices.getUserMedia).toHaveBeenCalledTimes(1)
    expect(result.current.loopState).toBe('listening')
    act(() => { result.current.stopConversation() })
  })

  it('COP-F6 : le hook n\'expose aucun chemin de confirmation vocale', () => {
    const store = makeStore()
    const env = makeMockEnv()
    const { result } = renderHook(() => useVoiceChat({ env, transcribe: vi.fn() }), { wrapper: wrapper(store) })
    expect(result.current.confirmByVoiceTap).toBeUndefined()
    act(() => { result.current.startConversation() })
    expect(result.current.conversationMode).toBe(true)
    act(() => { result.current.stopConversation() })
    expect(result.current.conversationMode).toBe(false)
  })
})
