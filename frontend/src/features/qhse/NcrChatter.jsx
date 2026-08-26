import { useCallback, useEffect, useRef, useState } from 'react'
import { MessageSquare, Send } from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import { Card, Button, Textarea, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   UX30/WIR234 — Chatter Odoo-style (historique + notes) sur une entité QHSE.
   ----------------------------------------------------------------------------
   `NcrChatter` alimente le panneau `activity` de la DetailShell d'une
   non-conformité via `non-conformites/<id>/historique`/`noter`. `CapaChatter`
   en est le JUMEAU pour une CAPA (`capa/<id>/historique`/`noter`, exposées
   côté serveur par le même `_ChatterMixin` — jusqu'ici sans consommateur
   côté écran, WIR234). Les deux partagent `ChatterCard`, seule la source des
   appels change.
   Chaque entrée : kind (creation / modification / note), acteur, horodatage.
   ========================================================================== */

/* PACT158 — le serveur écrit kind='modification' (apps/qhse/chatter.py +
   QhseChatterEntry.Kind), jamais 'field_change' : la clé doit matcher la
   valeur RÉELLE du modèle, sinon la branche « Champ : ancienne → nouvelle »
   ne se déclenche jamais et chaque changement automatique s'affiche à tort
   « Enregistrement créé » avec une pastille montrant le mot brut. */
const KIND_LABEL = {
  creation: 'Création',
  modification: 'Modification',
  note: 'Note',
}

function entryText(e) {
  if (e.kind === 'note') return e.body
  if (e.kind === 'modification') {
    const label = e.field_label || e.field || 'Champ'
    return `${label} : ${e.old_value ?? '—'} → ${e.new_value ?? '—'}`
  }
  return e.body || 'Enregistrement créé'
}

function ChatterCard({ resourceId, fetchHistorique, postNote, title = 'Historique' }) {
  const [entries, setEntries] = useState([])
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const taRef = useRef(null)

  const load = useCallback(async () => {
    if (!resourceId) return
    setLoading(true)
    try {
      const res = await fetchHistorique(resourceId)
      const data = res.data
      setEntries(Array.isArray(data) ? data : (data?.results ?? []))
    } catch {
      // Panneau secondaire : on n'écrase pas l'écran en cas d'échec.
    } finally {
      setLoading(false)
    }
  }, [resourceId, fetchHistorique])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [load])

  async function submit(e) {
    e.preventDefault()
    const text = body.trim()
    if (!text || submitting) return
    setSubmitting(true)
    try {
      await postNote(resourceId, text)
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
          {title} {entries.length > 0 && `(${entries.length})`}
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

export default function NcrChatter({ ncrId }) {
  return (
    <ChatterCard
      resourceId={ncrId}
      fetchHistorique={qhseApi.nonConformites.historique}
      postNote={qhseApi.nonConformites.noter}
      title="Historique"
    />
  )
}

// WIR234 — jumeau de NcrChatter pour une CAPA (`ActionCorrectivePreventive`),
// jusqu'ici sans aucun panneau d'activité côté écran alors que le serveur
// expose déjà `capa/<id>/historique`/`noter` (même `_ChatterMixin`).
export function CapaChatter({ capaId }) {
  return (
    <ChatterCard
      resourceId={capaId}
      fetchHistorique={qhseApi.capa.historique}
      postNote={qhseApi.capa.noter}
      title="Historique CAPA"
    />
  )
}
