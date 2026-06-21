import { useEffect, useState } from 'react'
import { Mic } from 'lucide-react'
import messagesApi from '../../api/messagesApi'

/* S17 — Rendu d'une note vocale dans une bulle. Lecteur audio + ligne de
   transcription qui se remplit quand le pipeline S11 a terminé :
   - transcript_status === 'pending'  → « Transcription… »
   - transcript_status === 'done'     → le texte transcrit
   - transcript_status === 'failed'   → message d'échec discret
   - transcript_status === 'disabled' → AUCUNE ligne (transcription coupée) ;
     la note vocale reste lisible.
   L'audio est récupéré via le proxy même-origine
   (`messagesApi.getAttachment`) qui renvoie le binaire ; on en fait une URL
   objet locale. */

function statusLabel(status, transcript) {
  if (status === 'pending') return { text: 'Transcription…', kind: 'pending' }
  if (status === 'failed') return { text: 'Transcription indisponible', kind: 'failed' }
  if (status === 'done' && transcript) return { text: transcript, kind: 'done' }
  return null // 'disabled' ou aucune donnée → rien
}

export default function VoiceMessage({ messageId, attachment }) {
  const att = attachment || {}
  // URL objet récupérée via le proxy (seulement quand aucune URL directe).
  const [fetchedSrc, setFetchedSrc] = useState('')
  const src = att.url || fetchedSrc

  // Si l'URL directe n'est pas fournie, on télécharge le binaire via le proxy
  // même-origine et on construit une URL objet (révoquée au démontage).
  useEffect(() => {
    if (att.url || messageId == null || att.id == null) return undefined
    let url = null
    let alive = true
    messagesApi
      .getAttachment(messageId, att.id)
      .then((res) => {
        if (!alive) return
        const blob = res.data instanceof Blob
          ? res.data
          : new Blob([res.data], { type: att.mime || 'audio/webm' })
        url = URL.createObjectURL(blob)
        setFetchedSrc(url)
      })
      .catch(() => { /* lecteur vide : la bulle reste affichée */ })
    return () => { alive = false; if (url) URL.revokeObjectURL(url) }
  }, [messageId, att.id, att.url, att.mime])

  const dur = att.duration_s
  const line = statusLabel(att.transcript_status, att.transcript)

  return (
    <div className="chat-voice" data-testid="voice-message" aria-label="Note vocale">
      <div className="chat-voice-head">
        <Mic size={14} aria-hidden="true" />
        {src ? (
          <audio controls src={src} className="chat-voice-audio" />
        ) : (
          <span className="chat-voice-loading">Chargement…</span>
        )}
        {dur != null && dur !== '' && (
          <span className="chat-voice-dur">{Math.round(Number(dur))}s</span>
        )}
      </div>
      {line && (
        <p className={`chat-voice-transcript ${line.kind}`} data-testid="voice-transcript">
          {line.text}
        </p>
      )}
    </div>
  )
}
