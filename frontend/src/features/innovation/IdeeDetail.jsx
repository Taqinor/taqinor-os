import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  ThumbsUp, Search, CheckCircle2, Rocket, XCircle, Send,
} from 'lucide-react'
import { DetailShell } from '../../ui/module'
import { Button, Textarea, EmptyState, Spinner, DefinitionList, Badge, toast } from '../../ui'
import { formatDateTime } from '../../lib/format'
import innovationApi from '../../api/innovationApi'
import {
  STATUT_MAP, StatutIdeePill, transitionsPour, estTerminal, TRANSITION_LABELS,
} from './innovationStatus'

/* ============================================================================
   NTIDE5 — Détail idée + actions (examiner/retenir/réaliser/fermer, palier
   Directeur/Responsable côté serveur — 403 si le rôle est insuffisant), vote
   (l'auteur ne peut pas voter pour sa propre idée — 400 côté serveur, affiché
   en toast), historique (chatter générique ARC8) et lien opaque devis/ticket/
   chantier.
   ========================================================================== */

const TRANSITION_ICONS = {
  examiner: Search,
  retenir: CheckCircle2,
  realiser: Rocket,
  fermer: XCircle,
}

function labelLinkedType(v) {
  return { devis: 'Devis', ticket: 'Ticket SAV', chantier: 'Chantier' }[v] || v
}

export default function IdeeDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [idee, setIdee] = useState(null)
  const [activites, setActivites] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [showFermerNote, setShowFermerNote] = useState(false)

  const load = () => {
    setLoading(true)
    return innovationApi.get(id)
      .then((res) => {
        setIdee(res.data)
        setActivites(res.data.historique || [])
      })
      .catch(() => toast.error('Impossible de charger cette idée.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const runTransition = async (key, extra) => {
    setBusy(true)
    try {
      if (key === 'examiner') await innovationApi.examiner(id)
      else if (key === 'retenir') await innovationApi.retenir(id)
      else if (key === 'realiser') await innovationApi.realiser(id)
      else if (key === 'fermer') await innovationApi.fermer(id, extra || '')
      toast.success('Statut mis à jour.')
      setShowFermerNote(false)
      setNote('')
      await load()
    } catch (err) {
      toast.error(err?.response?.status === 403
        ? "Action réservée au palier Directeur/Responsable."
        : 'Transition impossible.')
    } finally {
      setBusy(false)
    }
  }

  const handleVote = async () => {
    setBusy(true)
    try {
      await innovationApi.vote(id)
      toast.success('Vote enregistré.')
      await load()
    } catch (err) {
      const detail = err?.response?.data?.idee?.[0] || err?.response?.data?.detail
      toast.error(detail || 'Vote impossible.')
    } finally {
      setBusy(false)
    }
  }

  if (loading || !idee) {
    return (
      <div className="page flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }

  const items = [
    { term: 'Auteur', description: idee.auteur_nom || '—' },
    { term: 'Contexte', description: idee.contexte || '—' },
    { term: 'Votes', description: String(idee.votes_count ?? 0) },
    { term: 'Proposée le', description: formatDateTime(idee.date_creation) },
  ]
  if (idee.linked_type) {
    items.push({
      term: 'Lié à',
      description: `${labelLinkedType(idee.linked_type)} #${idee.linked_id}`,
    })
  }

  const detailsTab = (
    <div className="flex flex-col gap-4">
      {idee.description && (
        <div className="whitespace-pre-wrap rounded-lg border border-border p-3 text-sm leading-relaxed">
          {idee.description}
        </div>
      )}
      <DefinitionList items={items} />
    </div>
  )

  const historiqueTab = (
    <div className="flex flex-col gap-4">
      {activites.length ? (
        <ul className="flex flex-col gap-2">
          {activites.map((a) => (
            <li key={a.id} className="rounded-lg border border-border px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={a.kind === 'note' ? 'neutral' : 'info'}>
                  {a.kind === 'note' ? 'Note' : a.kind === 'creation' ? 'Création' : 'Changement'}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {a.user_username || '—'} · {formatDateTime(a.created_at)}
                </span>
              </div>
              <div className="mt-1">
                {a.field === 'statut' && a.old_value
                  ? (
                    <span className="text-muted-foreground">
                      {STATUT_MAP[a.old_value]?.label || a.old_value} → {STATUT_MAP[a.new_value]?.label || a.new_value}
                    </span>
                  )
                  : a.body ? <span className="whitespace-pre-wrap">{a.body}</span> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Aucune activité" description="Aucun changement ni note pour le moment." />
      )}
    </div>
  )

  const transitions = transitionsPour(idee.statut)
  const actions = (
    <>
      <Button type="button" variant="outline" onClick={handleVote} disabled={busy}>
        <ThumbsUp /> Voter
      </Button>
      {!estTerminal(idee.statut) && transitions.map((key) => {
        const Icon = TRANSITION_ICONS[key]
        if (key === 'fermer') {
          return (
            <Button key={key} type="button" variant="outline" disabled={busy}
                    onClick={() => setShowFermerNote((v) => !v)}>
              <Icon /> {TRANSITION_LABELS[key]}
            </Button>
          )
        }
        return (
          <Button key={key} type="button" onClick={() => runTransition(key)} disabled={busy}>
            <Icon /> {TRANSITION_LABELS[key]}
          </Button>
        )
      })}
    </>
  )

  return (
    <div className="page flex flex-col gap-4">
      <button
        type="button"
        onClick={() => navigate('/innovation/idees')}
        className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Retour à la boîte à idées
      </button>

      {showFermerNote && (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <Textarea
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Note de fermeture (optionnelle)…"
          />
          <div>
            <Button type="button" onClick={() => runTransition('fermer', note)} disabled={busy}>
              <Send /> Confirmer la fermeture
            </Button>
          </div>
        </div>
      )}

      <DetailShell
        title={idee.titre}
        status={idee.statut}
        statusPill={StatutIdeePill}
        actions={actions}
        tabs={[
          { value: 'details', label: 'Détails', content: detailsTab },
          { value: 'historique', label: 'Historique', count: activites.length, content: historiqueTab },
        ]}
      />
    </div>
  )
}
