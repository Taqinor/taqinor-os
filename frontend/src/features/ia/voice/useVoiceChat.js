// AG11 + AG12 — Hook voix de l'assistant : micro (MediaRecorder), transcription
// (AG10 /transcribe via iaApi), réponse lue à voix haute (speechSynthesis), et
// (AG12) « Mode conversation » mains-libres avec détection de silence (Web Audio)
// et barge-in.
//
// AUCUNE nouvelle dépendance npm : MediaRecorder + Web Audio API + speechSynthesis
// du navigateur, toutes gardées pour les navigateurs non compatibles (repli
// texte). Toutes les API navigateur sont INJECTABLES (`deps`) pour des tests
// headless (node:test / vitest).
//
// SÉCURITÉ (rule founder #4 / AG3) : la voix NE confirme JAMAIS automatiquement
// une action sortante/irréversible. Quand l'agent renvoie une proposition (carte
// AG3), la machine attend un « confirmer » explicite — voir conversationLoop.js.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import iaApi from '../../../api/iaApi'
import { queryAgent, confirmAgentAction } from '../store/iaSlice'
import { createConversationLoop, LOOP_STATES } from './conversationLoop'

// ── Détection de support (PUR — testable) ─────────────────────────────────────

// Vrai si l'environnement fournit le minimum pour CAPTURER l'audio (micro +
// MediaRecorder). `env` permet l'injection en test ; par défaut `globalThis`.
export function isRecordingSupported(env = globalThis) {
  return !!(
    env
    && env.navigator
    && env.navigator.mediaDevices
    && typeof env.navigator.mediaDevices.getUserMedia === 'function'
    && typeof env.MediaRecorder === 'function'
  )
}

// Vrai si la synthèse vocale est disponible (lecture à voix haute).
export function isSpeechSynthesisSupported(env = globalThis) {
  return !!(env && env.speechSynthesis && typeof env.SpeechSynthesisUtterance === 'function')
}

// Vrai si la détection de silence (Web Audio) est disponible — requise pour le
// mode conversation mains-libres.
export function isSilenceDetectionSupported(env = globalThis) {
  return !!(env && (typeof env.AudioContext === 'function' || typeof env.webkitAudioContext === 'function'))
}

// Choisit une voix FRANÇAISE parmi celles disponibles, sinon la 1re voix, sinon
// null. PUR — testable avec une liste injectée.
export function pickFrenchVoice(voices) {
  if (!Array.isArray(voices) || voices.length === 0) return null
  const fr = voices.find((v) => (v.lang || '').toLowerCase().startsWith('fr'))
  return fr || voices[0] || null
}

// Choisit le meilleur type MIME audio supporté par MediaRecorder. PUR.
export function pickAudioMimeType(MediaRecorderCtor) {
  if (!MediaRecorderCtor || typeof MediaRecorderCtor.isTypeSupported !== 'function') {
    return '' // laisse le navigateur décider
  }
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/ogg',
    'audio/mp4',
  ]
  for (const c of candidates) {
    if (MediaRecorderCtor.isTypeSupported(c)) return c
  }
  return ''
}

// Construit un nom de fichier à partir du type MIME (aide le décodage côté Groq).
export function filenameForMime(mime) {
  if (!mime) return 'audio.webm'
  if (mime.includes('ogg')) return 'audio.ogg'
  if (mime.includes('mp4')) return 'audio.mp4'
  if (mime.includes('wav')) return 'audio.wav'
  return 'audio.webm'
}

// Paramètres de détection de silence (mode conversation).
const SILENCE_RMS_THRESHOLD = 0.012 // RMS en dessous duquel on considère « silence »
const SILENCE_HANG_MS = 1200        // durée de silence avant de clore le tour
const SPEECH_RMS_THRESHOLD = 0.03   // RMS au-dessus duquel on détecte de la parole (barge-in)
const MAX_TURN_MS = 15000           // sécurité : durée max d'un tour d'écoute

// Calcule le RMS (volume) d'un buffer d'échantillons temporels [-1,1]. PUR.
export function computeRms(samples) {
  if (!samples || samples.length === 0) return 0
  let sum = 0
  for (let i = 0; i < samples.length; i++) {
    const v = samples[i]
    sum += v * v
  }
  return Math.sqrt(sum / samples.length)
}

// ── Hook ──────────────────────────────────────────────────────────────────────

// `deps` permet d'injecter les API navigateur en test (toutes optionnelles).
export function useVoiceChat(deps = {}) {
  const dispatch = useDispatch()
  const { messages, agentLoading } = useSelector((s) => s.ia)

  const env = useMemo(
    () => deps.env || (typeof globalThis !== 'undefined' ? globalThis : {}),
    [deps.env],
  )

  // Capacités (figées au montage — déterministes pour les tests).
  const recordingSupported = useMemo(() => isRecordingSupported(env), [env])
  const speechSupported = useMemo(() => isSpeechSynthesisSupported(env), [env])
  const conversationSupported = useMemo(
    () => recordingSupported && isSilenceDetectionSupported(env),
    [recordingSupported, env],
  )

  // États visibles dans l'UI.
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [voiceError, setVoiceError] = useState(null)
  const [conversationMode, setConversationMode] = useState(false)
  const [loopState, setLoopState] = useState(LOOP_STATES.IDLE)

  // Refs des ressources audio en cours (jamais dans le state pour éviter les
  // re-renders pendant la capture).
  const mediaRecorderRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const chunksRef = useRef([])
  const audioCtxRef = useRef(null)
  const analyserRef = useRef(null)
  const rafRef = useRef(null)
  const silenceTimerRef = useRef(null)
  const turnTimeoutRef = useRef(null)
  const loopRef = useRef(null)
  // Suit le dernier message agent déjà traité par la boucle (par index).
  const lastHandledIndexRef = useRef(-1)
  // Indirection par ref pour briser la dépendance d'ordre entre `startCapture`,
  // `stopCapture` et `setupSilenceDetection` (mutuellement référencés) sans
  // changer leur identité — chaque ref pointe toujours sur la dernière version.
  const stopCaptureRef = useRef(() => {})
  const setupSilenceDetectionRef = useRef(() => {})

  const transcribeFn = deps.transcribe || iaApi.transcribeVoice

  // ── Synthèse vocale ────────────────────────────────────────────────────────
  const speak = useCallback((text, onDone) => {
    if (!text || !speechSupported) { onDone?.(); return }
    const synth = env.speechSynthesis
    try {
      synth.cancel() // coupe toute lecture en cours
      const utter = new env.SpeechSynthesisUtterance(text)
      const voices = (synth.getVoices && synth.getVoices()) || []
      const voice = pickFrenchVoice(voices)
      if (voice) utter.voice = voice
      utter.lang = (voice && voice.lang) || 'fr-FR'
      utter.onend = () => { setSpeaking(false); onDone?.() }
      utter.onerror = () => { setSpeaking(false); onDone?.() }
      setSpeaking(true)
      synth.speak(utter)
    } catch {
      setSpeaking(false)
      onDone?.()
    }
  }, [env, speechSupported])

  const stopSpeaking = useCallback(() => {
    if (speechSupported) {
      try { env.speechSynthesis.cancel() } catch { /* ignore */ }
    }
    setSpeaking(false)
  }, [env, speechSupported])

  // ── Nettoyage des ressources audio ─────────────────────────────────────────
  const teardownAudio = useCallback(() => {
    if (rafRef.current != null && env.cancelAnimationFrame) {
      env.cancelAnimationFrame(rafRef.current)
    }
    rafRef.current = null
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
    if (turnTimeoutRef.current) { clearTimeout(turnTimeoutRef.current); turnTimeoutRef.current = null }
    try { analyserRef.current?.disconnect?.() } catch { /* ignore */ }
    analyserRef.current = null
    try { audioCtxRef.current?.close?.() } catch { /* ignore */ }
    audioCtxRef.current = null
    const rec = mediaRecorderRef.current
    if (rec && rec.state && rec.state !== 'inactive') {
      try { rec.stop() } catch { /* ignore */ }
    }
    mediaRecorderRef.current = null
    const stream = mediaStreamRef.current
    if (stream && stream.getTracks) {
      stream.getTracks().forEach((t) => { try { t.stop() } catch { /* ignore */ } })
    }
    mediaStreamRef.current = null
  }, [env])

  // ── Envoi du clip transcrit puis injection dans le flux question ────────────
  const sendClip = useCallback(async (blob, { viaLoop } = {}) => {
    setTranscribing(true)
    setVoiceError(null)
    try {
      const res = await transcribeFn(blob)
      const data = res?.data ?? res ?? {}
      if (data.available === false) {
        setVoiceError(data.detail || 'Transcription vocale indisponible.')
        setTranscribing(false)
        if (viaLoop) loopRef.current?.onTranscript('')
        return
      }
      const text = (data.text || '').trim()
      setTranscribing(false)
      if (viaLoop) {
        loopRef.current?.onTranscript(text)
      } else if (text) {
        dispatch(queryAgent(text))
      }
    } catch {
      setTranscribing(false)
      setVoiceError('La transcription a échoué. Réessayez.')
      if (viaLoop) loopRef.current?.onTranscript('')
    }
  }, [dispatch, transcribeFn])

  // ── Capture micro (un tour) ────────────────────────────────────────────────
  // `opts.detectSilence` active la détection de fin de parole (mode conversation).
  const startCapture = useCallback(async (opts = {}) => {
    if (!recordingSupported) {
      setVoiceError('Votre navigateur ne permet pas l\'enregistrement audio.')
      return false
    }
    setVoiceError(null)
    chunksRef.current = []
    try {
      const stream = await env.navigator.mediaDevices.getUserMedia({ audio: true })
      mediaStreamRef.current = stream
      const mime = pickAudioMimeType(env.MediaRecorder)
      const rec = mime
        ? new env.MediaRecorder(stream, { mimeType: mime })
        : new env.MediaRecorder(stream)
      mediaRecorderRef.current = rec
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data)
      }
      rec.onstop = () => {
        const type = rec.mimeType || mime || 'audio/webm'
        const BlobCtor = env.Blob || (typeof Blob !== 'undefined' ? Blob : null)
        const blob = BlobCtor
          ? new BlobCtor(chunksRef.current, { type })
          : { _chunks: chunksRef.current, type }
        if (blob.name === undefined) {
          try { blob.name = filenameForMime(type) } catch { /* certains Blob sont figés */ }
        }
        setRecording(false)
        const viaLoop = !!opts.detectSilence
        if (viaLoop) loopRef.current?.onSpeechEnd()
        sendClip(blob, { viaLoop })
      }
      rec.start()
      setRecording(true)

      // Détection de silence / barge-in pour le mode conversation.
      if (opts.detectSilence && isSilenceDetectionSupported(env)) {
        setupSilenceDetectionRef.current(stream)
      }
      // Sécurité : un tour d'écoute ne dure jamais indéfiniment.
      if (opts.detectSilence) {
        turnTimeoutRef.current = setTimeout(() => stopCaptureRef.current(), MAX_TURN_MS)
      }
      return true
    } catch {
      setRecording(false)
      teardownAudio()
      setVoiceError('Accès au micro refusé ou indisponible.')
      return false
    }
  }, [recordingSupported, env, sendClip, teardownAudio])

  // Détection de silence : analyse le RMS et clôt le tour après SILENCE_HANG_MS
  // de silence continu (une fois que l'utilisateur a commencé à parler).
  const setupSilenceDetection = useCallback((stream) => {
    const AC = env.AudioContext || env.webkitAudioContext
    if (!AC) return
    const ctx = new AC()
    audioCtxRef.current = ctx
    const source = ctx.createMediaStreamSource(stream)
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 2048
    source.connect(analyser)
    analyserRef.current = analyser
    const buf = new Float32Array(analyser.fftSize)
    let hasSpoken = false

    const tick = () => {
      if (!analyserRef.current) return
      analyser.getFloatTimeDomainData(buf)
      const rms = computeRms(buf)
      if (rms > SPEECH_RMS_THRESHOLD) hasSpoken = true
      if (hasSpoken && rms < SILENCE_RMS_THRESHOLD) {
        if (!silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(() => stopCaptureRef.current(), SILENCE_HANG_MS)
        }
      } else if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current)
        silenceTimerRef.current = null
      }
      rafRef.current = env.requestAnimationFrame
        ? env.requestAnimationFrame(tick)
        : null
    }
    rafRef.current = env.requestAnimationFrame ? env.requestAnimationFrame(tick) : null
  }, [env])

  // Stoppe l'enregistrement en cours (déclenche rec.onstop → sendClip).
  const stopCapture = useCallback(() => {
    if (turnTimeoutRef.current) { clearTimeout(turnTimeoutRef.current); turnTimeoutRef.current = null }
    if (silenceTimerRef.current) { clearTimeout(silenceTimerRef.current); silenceTimerRef.current = null }
    if (rafRef.current != null && env.cancelAnimationFrame) {
      env.cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    const rec = mediaRecorderRef.current
    if (rec && rec.state !== 'inactive') {
      try { rec.stop() } catch { /* ignore */ }
    } else {
      setRecording(false)
    }
  }, [env])

  // Garde les refs d'indirection à jour (voir déclaration des refs plus haut).
  useEffect(() => { stopCaptureRef.current = stopCapture }, [stopCapture])
  useEffect(() => { setupSilenceDetectionRef.current = setupSilenceDetection }, [setupSilenceDetection])

  // ── AG11 : bascule micro simple (push-to-talk) ─────────────────────────────
  const toggleRecording = useCallback(() => {
    if (recording) {
      stopCapture()
    } else {
      startCapture({ detectSilence: false })
    }
  }, [recording, startCapture, stopCapture])

  // ── AG12 : mode conversation (boucle) ──────────────────────────────────────
  const buildLoop = useCallback(() => {
    return createConversationLoop({
      onState: (s) => setLoopState(s),
      startListening: () => startCapture({ detectSilence: true }),
      stopListening: () => stopCapture(),
      ask: (text) => dispatch(queryAgent(text)),
      speak: (text) => speak(text),
      stopSpeaking: () => stopSpeaking(),
      confirm: (token) => dispatch(confirmAgentAction({ token, index: messages.length - 1 })),
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dispatch, startCapture, stopCapture, speak, stopSpeaking])

  const startConversation = useCallback(() => {
    if (!conversationSupported) {
      setVoiceError('Le mode conversation n\'est pas pris en charge par ce navigateur.')
      return
    }
    setConversationMode(true)
    lastHandledIndexRef.current = messages.length - 1
    const loop = buildLoop()
    loopRef.current = loop
    loop.start()
  }, [conversationSupported, buildLoop, messages.length])

  const stopConversation = useCallback(() => {
    loopRef.current?.stop()
    loopRef.current = null
    setConversationMode(false)
    teardownAudio()
    stopSpeaking()
  }, [teardownAudio, stopSpeaking])

  // Tap explicite « Confirmer » pendant le mode conversation (jamais auto).
  const confirmByVoiceTap = useCallback(() => {
    loopRef.current?.confirmByTap()
  }, [])

  // Quand une nouvelle réponse agent arrive (et qu'on est en mode conversation),
  // on la passe à la boucle pour qu'elle la lise / déclenche AWAITING_CONFIRM.
  useEffect(() => {
    if (!conversationMode || !loopRef.current) return
    if (agentLoading) return
    const idx = messages.length - 1
    if (idx <= lastHandledIndexRef.current) return
    const last = messages[idx]
    if (!last || last.role !== 'agent') return
    lastHandledIndexRef.current = idx
    if (last.kind === 'result') {
      loopRef.current.onActionDone(last)
    } else {
      loopRef.current.onAnswer(last)
    }
  }, [messages, agentLoading, conversationMode])

  // Quand la synthèse vocale d'un tour normal se termine, on prévient la boucle
  // (elle ré-ouvre le micro). On observe `speaking` repassant à false.
  const prevSpeakingRef = useRef(false)
  useEffect(() => {
    if (prevSpeakingRef.current && !speaking && conversationMode && loopRef.current) {
      loopRef.current.onSpeechSpoken()
    }
    prevSpeakingRef.current = speaking
  }, [speaking, conversationMode])

  // Nettoyage au démontage.
  useEffect(() => () => {
    teardownAudio()
    if (speechSupported) { try { env.speechSynthesis.cancel() } catch { /* ignore */ } }
  }, [teardownAudio, speechSupported, env])

  return {
    // Capacités.
    recordingSupported,
    speechSupported,
    conversationSupported,
    // États.
    recording,
    transcribing,
    speaking,
    voiceError,
    conversationMode,
    loopState,
    // Actions AG11.
    toggleRecording,
    stopCapture,
    speak,
    stopSpeaking,
    // Actions AG12.
    startConversation,
    stopConversation,
    confirmByVoiceTap,
  }
}

export default useVoiceChat
