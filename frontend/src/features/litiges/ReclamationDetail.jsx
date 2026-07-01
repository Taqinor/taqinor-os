import { useEffect, useState } from 'react'
import { Pencil, PlayCircle, CheckCircle2, XCircle, Send } from 'lucide-react'
import { DetailShell } from '../../ui/module'
import { Button, Badge, Textarea, EmptyState, Spinner, DefinitionList, toast } from '../../ui'
import { formatMAD, formatDateTime } from '../../lib/format'
import litigesApi from '../../api/litigesApi'
import {
  STATUT_MAP, GRAVITE_MAP, TYPE_MAP,
  StatutReclamationPill, transitionsPour, estTerminal,
} from './litigesStatus'

/* ============================================================================
   UX44 — Détail d'une réclamation : fiche, transitions de statut, chatter.
   ----------------------------------------------------------------------------
   Les transitions (prendre en charge / résoudre / rejeter) appliquent la machine
   à états côté serveur et journalisent le chatter. Les notes libres (``noter``)
   et l'historique (``historique``) alimentent la timeline.
   ========================================================================== */

const TRANSITION_LABELS = {
  prendre_en_charge: { label: 'Prendre en charge', icon: PlayCircle },
  resoudre: { label: 'Résoudre', icon: CheckCircle2 },
  rejeter: { label: 'Rejeter', icon: XCircle },
}

function labelStatut(v) { return STATUT_MAP[v]?.label ?? v ?? '—' }

export default function ReclamationDetail({ reclamationId, onBack, onEdit, onChanged }) {
  const [rec, setRec] = useState(null)
  const [activites, setActivites] = useState([])
  const [loading, setLoading] = useState(true)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    return Promise.all([
      litigesApi.get(reclamationId),
      litigesApi.historique(reclamationId),
    ])
      .then(([r, h]) => {
        setRec(r.data)
        setActivites(Array.isArray(h.data) ? h.data : (h.data?.results ?? []))
      })
      .catch(() => toast.error('Impossible de charger la réclamation.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const runTransition = async (key) => {
    setBusy(true)
    try {
      if (key === 'prendre_en_charge') await litigesApi.prendreEnCharge(reclamationId)
      else if (key === 'resoudre') await litigesApi.resoudre(reclamationId)
      else if (key === 'rejeter') await litigesApi.rejeter(reclamationId)
      toast.success('Statut mis à jour.')
      await load()
      onChanged?.()
    } catch {
      toast.error('Transition impossible.')
    } finally {
      setBusy(false)
    }
  }

  const ajouterNote = async () => {
    const msg = note.trim()
    if (!msg) return
    setBusy(true)
    try {
      await litigesApi.noter(reclamationId, msg)
      setNote('')
      await load()
      toast.success('Note ajoutée.')
    } catch {
      toast.error('Note impossible.')
    } finally {
      setBusy(false)
    }
  }

  if (loading || !rec) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  // ── Onglet Détails ──
  const items = [
    { term: 'Référence', description: rec.reference || '—' },
    { term: 'Type', description: TYPE_MAP[rec.type_reclamation] || rec.type_reclamation || '—' },
    { term: 'Gravité', description: GRAVITE_MAP[rec.gravite]?.label || rec.gravite || '—' },
    { term: 'Montant contesté', description: formatMAD(rec.montant_conteste) },
    { term: 'Relances', description: rec.bloque_relances ? 'Bloquées' : 'Actives' },
    { term: 'Créée le', description: formatDateTime(rec.date_creation) },
  ]
  if (rec.concurrent_nom) {
    items.push({ term: 'Concurrent gagnant', description: rec.concurrent_nom })
    if (rec.concurrent_prix != null) {
      items.push({
        term: 'Prix concurrent',
        description: `${formatMAD(rec.concurrent_prix, { withSymbol: false })} ${rec.concurrent_devise || 'MAD'}`,
      })
    }
  }
  if (rec.motif_perte) items.push({ term: 'Motif de la perte', description: rec.motif_perte })

  const detailsTab = (
    <div className="flex flex-col gap-4">
      {rec.description && (
        <div className="whitespace-pre-wrap rounded-lg border border-border p-3 text-sm leading-relaxed">
          {rec.description}
        </div>
      )}
      <DefinitionList items={items} />
    </div>
  )

  // ── Onglet Historique (chatter) ──
  const historiqueTab = (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Textarea
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
        />
        <div>
          <Button type="button" variant="outline" onClick={ajouterNote} disabled={busy || !note.trim()}>
            <Send /> Ajouter la note
          </Button>
        </div>
      </div>
      {activites.length ? (
        <ul className="flex flex-col gap-2">
          {activites.map((a) => (
            <li key={a.id} className="rounded-lg border border-border px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={a.type === 'note' ? 'neutral' : 'info'}>
                  {a.type_display || a.type}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {a.auteur_nom || '—'} · {formatDateTime(a.date_creation)}
                </span>
              </div>
              <div className="mt-1">
                {a.type === 'note'
                  ? <span className="whitespace-pre-wrap">{a.message}</span>
                  : (
                    <span className="text-muted-foreground">
                      {labelStatut(a.old_value)} → {labelStatut(a.new_value)}
                    </span>
                  )}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Aucune activité" description="Aucun changement ni note pour le moment." />
      )}
    </div>
  )

  const transitions = transitionsPour(rec.statut)
  const actions = (
    <>
      <Button type="button" variant="outline" onClick={onEdit}>
        <Pencil /> Éditer
      </Button>
      {!estTerminal(rec.statut) && transitions.map((key) => {
        const T = TRANSITION_LABELS[key]
        const Icon = T.icon
        return (
          <Button key={key} type="button" onClick={() => runTransition(key)} disabled={busy}>
            <Icon /> {T.label}
          </Button>
        )
      })}
    </>
  )

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Retour au registre
      </button>
      <DetailShell
        title={rec.objet}
        subtitle={rec.reference || undefined}
        status={rec.statut}
        statusPill={StatutReclamationPill}
        actions={actions}
        tabs={[
          { value: 'details', label: 'Détails', content: detailsTab },
          { value: 'historique', label: 'Historique', count: activites.length, content: historiqueTab },
        ]}
      />
    </div>
  )
}
