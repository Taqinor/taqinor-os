import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { Building2, LayoutGrid, ClipboardList, FolderKanban, MessagesSquare } from 'lucide-react'
import aoApi from '../../api/aoApi'
import recordsApi from '../../api/recordsApi'
import useResource from '../../hooks/useResource'
import { unwrapList } from '../../api/resource'
import { Button, Card, Textarea, EmptyState, Skeleton, toast } from '../../ui'
import { RecordShell } from '../../ui/module'
import ChatterTimeline from '../../components/ChatterTimeline'
import { formatDate, formatMAD } from '../../lib/format'
import { StatutAffaire } from './statusAo'

/* ============================================================================
   AOF171 — Fiche affaire (`RecordShell`) + chatter.
   ----------------------------------------------------------------------------
   Chatter via `ChatterTimeline` sur la cible `ao.appeloffre` (`records`,
   AUCUNE timeline maison) : notes = `recordsApi.getComments`/`createComment`,
   pièces jointes récentes = `recordsApi.getAttachments` — injectées dans le
   MÊME fil (ChatterTimeline les fusionne déjà). Rendu à la fois dans le
   panneau latéral (`activity`, grand écran) ET dans l'onglet « Historique »
   (accès en ligne sur tout viewport — DetailShell ne montre le panneau
   qu'à partir de `lg:`).

   **Onglet Rentabilité ABSENT — DÉLIBÉRÉMENT.** La route séparée
   `/ao/:id/rentabilite` (AOF161, lane `frontend/ao-directeur`) porte son
   propre écran ; ce composant ne la référence NULLE PART (aucun lien, aucun
   onglet) — masquer un onglet ne protège rien si les données voyagent dans
   le payload de la fiche (en-tête du groupe), donc la fiche n'a même pas le
   VOCABULAIRE « rentabilité » dans son arbre.

   Bandeau de verdict/échéance/complétude/issue : champs AGRÉGÉS lus tels
   quels depuis `affaire` (aucun calcul de KPI côté front) — noms de champs
   anticipés (`verdict_global*`, `prochaine_echeance_*`, `dossier_completude`,
   `resultat_issue_display`), pas encore posés par le serializer legacy ODX11
   (`apps/ao/serializers.py`) — livrés par la lane `backend/ao`. Rendu
   défensif (« — » si absent).
   ========================================================================== */

const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const VERDICT_TONE = { confirme: 'success', tendu: 'warning' }

function VerdictBandeau({ affaire }) {
  const verdictTone = VERDICT_TONE[affaire.verdict_global] ?? 'neutral'
  return (
    <Card className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2 sm:p-5 lg:grid-cols-4">
      <Info label="Verdict global du site" value={affaire.verdict_global_label} tone={verdictTone} />
      <Info
        label="Échéance la plus proche"
        value={affaire.prochaine_echeance_libelle}
        meta={affaire.prochaine_echeance_date ? formatDate(affaire.prochaine_echeance_date) : null}
      />
      <Info
        label="Complétude du dossier"
        value={affaire.dossier_completude != null ? `${Math.round(affaire.dossier_completude)} %` : null}
      />
      <Info label="Issue (ouverture des plis)" value={affaire.resultat_issue_display} />
    </Card>
  )
}

function Info({ label, value, meta, tone }) {
  const toneClass = tone === 'success' ? 'text-success' : tone === 'warning' ? 'text-warning' : 'text-foreground'
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`font-display text-base font-semibold ${toneClass}`}>{value || '—'}</dd>
      {meta && <p className="text-xs text-muted-foreground">{meta}</p>}
    </div>
  )
}

function TabPlaceholder({ icon: Icon, title }) {
  return (
    <EmptyState
      icon={Icon}
      title={title}
      description="Écran dédié en construction (lane distincte du Groupe AOF)."
    />
  )
}

export default function AffaireDetail() {
  const { id } = useParams()
  const [note, setNote] = useState('')
  const [sending, setSending] = useState(false)

  // `select` OBLIGATOIRE : `useResource` passe la valeur résolue TELLE QUELLE
  // (cf. son contrat — « pour un axios brut, passez `select: (res) => res.data` »).
  // Sans lui, `affaire` valait la réponse axios entière et TOUS les champs de
  // la fiche étaient lus un cran trop haut : titre « #undefined », objet,
  // statut et bandeau vides. Même convention que `DashboardPage.jsx`.
  const { data: affaire, loading, error } = useResource(
    () => aoApi.affaires.get(id), id,
    { select: (res) => res.data, errorMessage: 'Affaire introuvable.' },
  )
  const { data: comments, refetch: refetchComments } = useResource(
    () => recordsApi.getComments('ao.appeloffre', id), id,
    { initialData: [], select: unwrapList, errorMessage: () => '' },
  )
  const { data: attachments } = useResource(
    () => recordsApi.getAttachments('ao.appeloffre', id), id,
    { initialData: [], select: unwrapList, errorMessage: () => '' },
  )

  const chatterEntries = (comments || []).map((c) => ({
    id: c.id,
    kind: 'note',
    body: c.body,
    user_nom: c.author_display || c.author_username,
    created_at: c.created_at,
  }))

  const ajouterNote = async () => {
    const body = note.trim()
    if (!body) return
    setSending(true)
    try {
      await recordsApi.createComment('ao.appeloffre', id, body)
      setNote('')
      refetchComments()
    } catch (e) {
      toast.error(errMsg(e, 'Note non enregistrée.'))
    } finally {
      setSending(false)
    }
  }

  const chatterPanel = (
    <Card className="p-4">
      <h3 className="mb-3 font-display text-base font-semibold">Chatter</h3>
      <div className="mb-4 flex flex-col gap-2">
        <Textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ajouter une note…"
          rows={2}
          aria-label="Nouvelle note"
        />
        <Button size="sm" className="self-end" disabled={sending || !note.trim()} onClick={ajouterNote}>
          {sending ? 'Envoi…' : 'Noter'}
        </Button>
      </div>
      <ChatterTimeline entries={chatterEntries} attachments={attachments} />
    </Card>
  )

  if (loading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (error || !affaire) {
    return (
      <EmptyState
        title="Affaire introuvable"
        description={error || "Cette affaire n'existe pas ou n'est pas accessible."}
      />
    )
  }

  return (
    <RecordShell
      title={affaire.reference || `#${affaire.id}`}
      subtitle={affaire.objet}
      status={affaire.statut}
      statusPill={StatutAffaire}
      backTo="/ao/affaires"
      backLabel="Retour aux affaires"
      activity={chatterPanel}
      tabs={[
        {
          value: 'synthese',
          label: 'Synthèse',
          content: (
            <div className="flex flex-col gap-4">
              <VerdictBandeau affaire={affaire} />
              <Card className="p-4">
                <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
                  <Info label="Acheteur" value={affaire.acheteur} />
                  <Info label="Type de marché" value={affaire.type_marche_display || affaire.type_marche} />
                  <Info label="Lot" value={affaire.lot} />
                  <Info
                    label="Date limite de remise des plis"
                    value={affaire.date_limite ? formatDate(affaire.date_limite) : null}
                  />
                  <Info
                    label="Montant estimé"
                    value={affaire.montant_estime != null ? formatMAD(affaire.montant_estime) : null}
                  />
                  <Info
                    label="Caution provisoire"
                    value={affaire.caution_provisoire != null ? formatMAD(affaire.caution_provisoire) : null}
                  />
                </dl>
              </Card>
            </div>
          ),
        },
        {
          value: 'toitures',
          label: 'Toitures & relevés',
          content: <TabPlaceholder icon={Building2} title="Toitures & relevés" />,
        },
        {
          value: 'calepinages',
          label: 'Calepinages',
          content: <TabPlaceholder icon={LayoutGrid} title="Calepinages" />,
        },
        {
          value: 'bordereau',
          label: 'Bordereau',
          content: <TabPlaceholder icon={ClipboardList} title="Bordereau" />,
        },
        {
          value: 'dossier',
          label: 'Dossier',
          content: <TabPlaceholder icon={FolderKanban} title="Dossier" />,
        },
        {
          value: 'questions_terrain',
          label: 'Questions terrain',
          content: <TabPlaceholder icon={MessagesSquare} title="Questions terrain" />,
        },
        {
          value: 'historique',
          label: 'Historique',
          content: <ChatterTimeline entries={chatterEntries} attachments={attachments} />,
        },
      ]}
    />
  )
}
