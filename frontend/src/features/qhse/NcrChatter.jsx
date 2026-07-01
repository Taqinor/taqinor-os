import { useCallback, useEffect, useRef, useState } from 'react'
import { MessageSquare, Send } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { Card, Button, Textarea, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   UX30 — Chatter d'une non-conformité (historique Odoo-style + notes).
   ----------------------------------------------------------------------------
   Alimente le panneau `activity` de la DetailShell : liste l'historique QHSE
   (créations, changements de champ auto, notes manuelles) via
   `non-conformites/<id>/historique`, et permet d'ajouter une note via `noter`.
   Chaque entrée : kind (creation / field_change / note), acteur, horodatage.
   ========================================================================== */

const KIND_LABEL = {
  creation: 'Création',
  field_change: 'Modification',
  note: 'Note',
}

function entryText(e) {
  if (e.kind === 'note') return e.body
  if (e.kind === 'field_change') {
    const label = e.field_label || e.field || 'Champ'
    return `${label} : ${e.old_value ?? '—'} → ${e.new_value ?? '—'}`
  }
  return e.body || 'Enregistrement créé'
}

export default function NcrChatter({ ncrId }) {
  const [entries, setEntries] = useState([])
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const taRef = useRef(null)

  const load = useCallback(async () => {
    if (!ncrId) return
    setLoading(true)
    try {
      const res = await qhseApi.nonConformites.historique(ncrId)
      const data = res.data
      setEntries(Array.isArray(data) ? data : (data?.results ?? []))
    } catch {
      // Panneau secondaire : on n'écrase pas l'écran en cas d'échec.
    } finally {
      setLoading(false)
    }
  }, [ncrId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [load])

  async function submit(e) {
    e.preventDefault()
    const text = body.trim()
    if (!text || submitting) return
    setSubmitting(true)
    try {
      await qhseApi.nonConformites.noter(ncrId, text)
      setBody('')
      await load()
      toast.success('Note ajoutée.')
    } catch {
      toast.error('Impossible d’ajouter la note.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <MessageSquare size={16} aria-hidden="true" />
        <h3 className="font-display text-sm font-semibold">
          Historique {entries.length > 0 && `(${entries.length})`}
        </h3>
      </div>

      <div className="flex max-h-96 flex-col gap-3 overflow-y-auto">
        {loading && (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        )}
        {!loading && entries.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune entrée.</p>
        )}
        {entries.map((e) => (
          <div key={e.id} className="border-l-2 border-border pl-3">
            <div className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">
                {e.user_nom || 'Système'}
              </span>
              <span>{KIND_LABEL[e.kind] ?? e.kind}</span>
              <span>{formatDateTime(e.created_at)}</span>
            </div>
            <p className="mt-0.5 whitespace-pre-wrap text-sm">{entryText(e)}</p>
          </div>
        ))}
      </div>

      <form className="mt-3 flex flex-col gap-2" onSubmit={submit}>
        <Textarea
          ref={taRef}
          rows={2}
          placeholder="Ajouter une note…"
          value={body}
          onChange={(ev) => setBody(ev.target.value)}
        />
        <Button
          type="submit"
          size="sm"
          disabled={!body.trim() || submitting}
          className="self-end"
        >
          <Send size={14} /> Noter
        </Button>
      </form>
    </Card>
  )
}
