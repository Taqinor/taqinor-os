import { useEffect, useRef, useState } from 'react'
import { Mic, Square, Trash2, Send } from 'lucide-react'
import { IconButton } from '../../ui'
import { toastError } from '../../lib/toast'
import api from '../../api/axios'
import { pickAudioMimeType } from '../ia/voice/useVoiceChat'

/* S17 — Enregistreur de note vocale. Capture un court clip via le
   `MediaRecorder` du navigateur (aucune nouvelle dépendance), puis l'envoie
   comme pièce jointe vocale via `messagesApi.uploadAttachment` (POST
   /chat/messages/upload/ avec `conversation` + `kind=voice`). Le bouton est
   simplement masqué quand le navigateur ne supporte pas l'enregistrement, donc
   le reste du composer continue de fonctionner. */

// Le support de l'enregistrement audio dépend de deux APIs distinctes.
function isRecordingSupported() {
  return (
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder !== 'undefined' &&
    !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
  )
}

const STATE = { IDLE: 'idle', RECORDING: 'recording', PREVIEW: 'preview' }

export default function VoiceRecorder({ conversationId, onSent, disabled = false }) {
  const supported = isRecordingSupported()
  const [phase, setPhase] = useState(STATE.IDLE)
  const [seconds, setSeconds] = useState(0)
  const [clip, setClip] = useState(null) // { blob, url }
  const [busy, setBusy] = useState(false)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)

  // Nettoyage : on coupe le micro, le timer et l'URL objet à la sortie.
  useEffect(() => () => {
    if (timerRef.current) clearInterval(timerRef.current)
    streamRef.current?.getTracks?.().forEach((t) => t.stop())
    if (clip?.url) URL.revokeObjectURL(clip.url)
  }, [clip])

  if (!supported) return null

  const stopTracks = () => {
    streamRef.current?.getTracks?.().forEach((t) => t.stop())
    streamRef.current = null
  }

  const startTimer = () => {
    setSeconds(0)
    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000)
  }
  const stopTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = null
  }

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      // VX173 — mimeType NÉGOCIÉ (source unique `pickAudioMimeType`, partagée
      // avec `useVoiceChat.js`) : WebKit ne supporte pas webm et produit en
      // silence de l'audio/mp4 — sans `mimeType` explicite, `rec.mimeType`
      // reste étiqueté « webm » par le repli ci-dessous alors que les octets
      // sont du mp4 (lecture/serveur KO sur iPhone).
      const negotiatedType = pickAudioMimeType(window.MediaRecorder)
      const rec = negotiatedType
        ? new window.MediaRecorder(stream, { mimeType: negotiatedType })
        : new window.MediaRecorder(stream)
      recorderRef.current = rec
      rec.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data)
      }
      rec.onstop = () => {
        const type = rec.mimeType || negotiatedType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type })
        const url = URL.createObjectURL(blob)
        setClip({ blob, url })
        setPhase(STATE.PREVIEW)
        stopTracks()
        stopTimer()
      }
      rec.start()
      setPhase(STATE.RECORDING)
      startTimer()
    } catch {
      toastError('Microphone indisponible')
      stopTracks()
    }
  }

  const stop = () => {
    try {
      recorderRef.current?.stop()
    } catch { /* déjà arrêté */ }
  }

  const discard = () => {
    if (clip?.url) URL.revokeObjectURL(clip.url)
    setClip(null)
    setSeconds(0)
    setPhase(STATE.IDLE)
  }

  const send = async () => {
    if (!clip) return
    setBusy(true)
    try {
      const ext = (clip.blob.type.includes('ogg') && 'ogg') ||
        (clip.blob.type.includes('mp4') && 'm4a') || 'webm'
      const file = new File([clip.blob], `memo-${Date.now()}.${ext}`, { type: clip.blob.type })
      // Le backend distingue un mémo vocal par `kind=voice` (→ pipeline de
      // transcription S11). On envoie le multipart directement pour porter ce
      // champ (le helper générique d'upload ne le transmet pas).
      const fd = new FormData()
      fd.append('conversation', conversationId)
      fd.append('file', file)
      fd.append('kind', 'voice')
      if (seconds) fd.append('duration_s', String(seconds))
      const res = await api.post('/chat/messages/upload/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      onSent?.(res?.data)
      discard()
    } catch (err) {
      toastError(err.response?.data?.detail || 'Échec de l’envoi de la note vocale')
    } finally {
      setBusy(false)
    }
  }

  const mmss = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`

  if (phase === STATE.RECORDING) {
    return (
      <div className="chat-voice-recorder recording" data-testid="voice-recorder">
        <span className="chat-voice-rec-dot" aria-hidden="true" />
        <span className="chat-voice-rec-time" aria-label="Durée d’enregistrement">{mmss}</span>
        <IconButton type="button" aria-label="Arrêter l’enregistrement" onClick={stop}>
          <Square size={16} aria-hidden="true" />
        </IconButton>
      </div>
    )
  }

  if (phase === STATE.PREVIEW && clip) {
    return (
      <div className="chat-voice-recorder preview" data-testid="voice-recorder">
        <audio controls src={clip.url} className="chat-voice-preview" aria-label="Aperçu de la note vocale" />
        <IconButton type="button" aria-label="Supprimer la note vocale" onClick={discard} disabled={busy}>
          <Trash2 size={16} aria-hidden="true" />
        </IconButton>
        <IconButton type="button" aria-label="Envoyer la note vocale" onClick={send} disabled={busy}>
          <Send size={16} aria-hidden="true" />
        </IconButton>
      </div>
    )
  }

  return (
    <IconButton
      type="button"
      aria-label="Enregistrer une note vocale"
      onClick={start}
      disabled={disabled || !conversationId}
      className="chat-voice-record-btn"
      data-testid="voice-recorder"
    >
      <Mic size={18} aria-hidden="true" />
    </IconButton>
  )
}
