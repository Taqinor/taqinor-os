// NTMOB30 — Dictée d'une note de TERRAIN, réutilisable hors intervention.
//
// `MemosPanel` (F13/F14) sait enregistrer un mémo vocal, mais seulement sur une
// `Intervention`. Ce composant extrait le même geste — bouton micro, enregistre,
// transcrit — pour l'offrir à la chatter d'un LEAD ou d'un TICKET SAV : le
// technicien dicte au lieu de taper sur un petit écran, et le TEXTE obtenu part
// par l'endpoint `noter` déjà existant de chaque app (aucun nouveau modèle,
// aucune pièce jointe créée).
//
// FRONTIÈRE EZ15/PLAN2 : la dictée INLINE navigateur (Web Speech, zéro backend,
// surfaces BUREAU) reste à EZ15. Ici c'est l'enregistrement + transcription
// SERVEUR (Whisper self-hosted, `chat/transcrire/`) pour le terrain/mobile —
// jamais deux boutons micro sur le même champ.
//
// Transcription désactivée côté serveur (`CHAT_TRANSCRIPTION_ENABLED`) ou micro
// indisponible → le bouton ne s'affiche pas / dit pourquoi : la saisie clavier
// reste le chemin normal, jamais bloqué.
import { useEffect, useRef, useState } from 'react'
import { Mic, Square } from 'lucide-react'
import messagesApi from '../../api/messagesApi'

function microDisponible() {
  return typeof navigator !== 'undefined'
    && !!navigator.mediaDevices?.getUserMedia
    && typeof MediaRecorder !== 'undefined'
}

export default function VoiceNoteRecorder({ onTranscrit, disabled = false }) {
  const [enregistre, setEnregistre] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const recorderRef = useRef(null)
  const chunksRef = useRef([])

  // Libère le micro si l'écran se ferme en cours d'enregistrement (`onstop`
  // ne se déclenche pas au démontage) — même précaution que `MemosPanel`.
  useEffect(() => () => {
    const rec = recorderRef.current
    if (rec) {
      try { if (rec.state !== 'inactive') rec.stop() } catch { /* déjà arrêté */ }
      rec.stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  if (!microDisponible()) return null

  const demarrer = async () => {
    setMessage('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      chunksRef.current = []
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setBusy(true)
        try {
          const r = await messagesApi.transcrire(
            new File([blob], 'note.webm', { type: 'audio/webm' }))
          if (r.data?.enabled === false) {
            setMessage('Transcription indisponible — saisissez la note au clavier.')
          } else if (r.data?.texte) {
            onTranscrit?.(r.data.texte)
          } else {
            setMessage('Rien n\'a été compris — réessayez ou tapez la note.')
          }
        } catch {
          setMessage('Transcription impossible — saisissez la note au clavier.')
        } finally {
          setBusy(false)
        }
      }
      recorderRef.current = rec
      rec.start()
      setEnregistre(true)
    } catch {
      setMessage('Micro indisponible sur cet appareil.')
    }
  }

  const arreter = () => {
    try { recorderRef.current?.stop() } catch { /* déjà arrêté */ }
    setEnregistre(false)
  }

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={enregistre ? arreter : demarrer}
        aria-label={enregistre ? 'Arrêter la dictée' : 'Dicter une note'}
        className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-2.5 text-sm"
      >
        {enregistre
          ? <Square className="size-4 text-destructive" aria-hidden="true" />
          : <Mic className="size-4" aria-hidden="true" />}
        {busy ? 'Transcription…' : enregistre ? 'Arrêter' : 'Dicter'}
      </button>
      {message && <p className="text-xs text-muted-foreground">{message}</p>}
    </div>
  )
}
