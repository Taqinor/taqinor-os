// AG11/AG12 — Tests du hook voix (Vitest + jsdom). Toutes les API navigateur
// (MediaRecorder, getUserMedia, speechSynthesis, AudioContext) sont MOCKÉES via
// l'injection `deps.env`, donc le test tourne headless. On couvre :
//   • les helpers purs (support, choix de voix, MIME, RMS),
//   • le repli navigateur non supporté (recordingSupported=false),
//   • le happy path AG11 (capture → transcribe → queryAgent),
//   • le garde-fou de sécurité AG12 (une proposition NE confirme JAMAIS seule).

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import React from 'react'

import iaReducer from '../store/iaSlice'
import {
  useVoiceChat,
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
function makeStore() {
  return configureStore({ reducer: { ia: iaReducer } })
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

describe('useVoiceChat — happy path AG11 (capture → transcribe → queryAgent)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('un tour micro transcrit puis dispatch queryAgent avec le texte', async () => {
    const store = makeStore()
    const env = makeMockEnv()
    const transcribe = vi.fn(() => Promise.resolve({ data: { text: 'combien de clients', language: 'fr' } }))
    const { result } = renderHook(
      () => useVoiceChat({ env, transcribe }),
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

    // queryAgent a poussé un message user dans le store.
    await waitFor(() => {
      const msgs = store.getState().ia.messages
      expect(msgs.some((m) => m.role === 'user' && m.content === 'combien de clients')).toBe(true)
    })
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

  it('confirmByVoiceTap NE confirme PAS hors d\'une proposition en attente', async () => {
    const store = makeStore()
    const env = makeMockEnv()
    const { result } = renderHook(() => useVoiceChat({ env, transcribe: vi.fn() }), { wrapper: wrapper(store) })
    act(() => { result.current.startConversation() })
    expect(result.current.conversationMode).toBe(true)
    // Aucune proposition en attente → un tap ne déclenche AUCUNE confirmation :
    // le store ne porte aucun index de confirmation en cours.
    act(() => { result.current.confirmByVoiceTap() })
    expect(store.getState().ia.confirmingIndex).toBe(null)
    act(() => { result.current.stopConversation() })
    expect(result.current.conversationMode).toBe(false)
  })
})
