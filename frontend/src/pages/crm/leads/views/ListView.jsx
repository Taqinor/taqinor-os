// Vue LISTE des leads CRM — table dense et triable, façon Odoo.
// Les étapes viennent EXCLUSIVEMENT de features/crm/stages (miroir de
// STAGES.py) : aucune liste d'étapes n'est déclarée ici.
import { Fragment, useEffect, useMemo, useState, memo } from 'react'
import { MoreHorizontal, PhoneCall, MessageCircle, List } from 'lucide-react'
import { useDispatch } from 'react-redux'
import { EmptyState } from '../../../../ui'
import { useIsAdmin } from '../../../../hooks/useHasPermission'
import { archiveLead, restoreLead, deleteLead, updateLead } from '../../../../features/crm/store/crmSlice'
import crmApi from '../../../../api/crmApi'
import { toastWithUndo, toastError } from '../../../../lib/toast'
import {
  PIPELINE_STAGES,
  STAGE_LABELS,
  CANAL_LABELS,
  PRIORITE_LABELS,
  PRIORITE_STARS,
  isPerdu,
  isStageMoveAllowed,
  tagList,
  tagColor,
} from '../../../../features/crm/stages'
import { formatDate } from '../../../../lib/format'
import AssigneePicker from '../../../../components/AssigneePicker'
import InlineEdit from '../../../../components/InlineEdit'
import ExternalLink from '../../../../ui/ExternalLink'
import LeadInsightsDialog from '../LeadInsightsDialog'
// VX24 — ScoreBadge extrait vers features/crm (réutilisé par LeadCard/LeadSummaryBar).
import ScoreBadge from '../../../../features/crm/ScoreBadge'
// VX87 — nudge post-appel « Appel terminé — noter le résultat ? ».
import CallLogPopover, { useCallEndedNudge } from '../../../../features/crm/CallLogPopover'
import { allVisibleSelected } from '../../../../features/crm/bulk'
import {
  Button, Checkbox, HelpTip, IconButton, StatusPill,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator,
  Popover, PopoverTrigger, PopoverContent,
} from '../../../../ui'
import { formatMAD } from '../../../../lib/format'

const MOBILE_QUERY = '(max-width: 768px)'

// Vrai sous 768px — les actions de ligne se replient alors dans un menu « ⋯ ».
function useIsMobile() {
  const [mobile, setMobile] = useState(
    () => window.matchMedia(MOBILE_QUERY).matches,
  )
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_QUERY)
    const onChange = (e) => setMobile(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return mobile
}

// Options des sélecteurs d'édition en place (libellés FR depuis stages.js).
// LB4 — options d'étape calculées PAR LIGNE (dépendent de l'étape courante du
// lead, pas une liste plate partagée) : `disabled` grise les transitions
// interdites, MÊME garde que le drag kanban (isStageMoveAllowed) — le chemin
// clavier/souris de la liste obtient désormais la même réponse (bug #8).
const stageOptionsFor = (currentStage) => PIPELINE_STAGES.map((s) => ({
  value: s,
  label: STAGE_LABELS[s] ?? s,
  disabled: s !== currentStage && !isStageMoveAllowed(currentStage, s),
}))
const PRIORITE_OPTIONS = [
  { value: 'basse', label: PRIORITE_LABELS.basse },
  { value: 'normale', label: PRIORITE_LABELS.normale },
  { value: 'haute', label: PRIORITE_LABELS.haute },
]

// Priorité : haute > normale > basse (ordre croissant = haute d'abord).
const PRIO_RANK = { haute: 0, normale: 1, basse: 2 }

const fullName = (l) => `${l.nom ?? ''} ${l.prenom ?? ''}`.trim()

// QX25 — la colonne Téléphone est masquée sur mobile (`m-hide`, ≤768px) sans
// aucun repli tap-to-call : on pose des icônes compactes tel:/wa.me dans la
// cellule « Lead » (jamais masquée) pour que le mobile reste appelable.
const telHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}
const waHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const digits = s.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}` : null
}

// Comparateurs ascendants par colonne triable.
const SORTERS = {
  lead: (a, b) => fullName(a).localeCompare(fullName(b), 'fr'),
  stage: (a, b) =>
    PIPELINE_STAGES.indexOf(a.stage) - PIPELINE_STAGES.indexOf(b.stage),
  canal: (a, b) =>
    (CANAL_LABELS[a.canal] ?? '').localeCompare(CANAL_LABELS[b.canal] ?? '', 'fr'),
  owner: (a, b) =>
    (a.owner_nom ?? '').localeCompare(b.owner_nom ?? '', 'fr'),
  priorite: (a, b) =>
    (PRIO_RANK[a.priorite] ?? 1) - (PRIO_RANK[b.priorite] ?? 1),
  relance: (a, b) =>
    String(a.relance_date).localeCompare(String(b.relance_date)),
  ville: (a, b) => (a.ville ?? '').localeCompare(b.ville ?? '', 'fr'),
  telephone: (a, b) =>
    (a.telephone ?? '').localeCompare(b.telephone ?? '', 'fr'),
  score: (a, b) => (a.score ?? 0) - (b.score ?? 0),
}

// VX24 — ScoreBadge (+ SCORE_COLORS) déménagé vers features/crm/ScoreBadge.jsx.
// VX221 — le tooltip « pourquoi ce score » (score_reasons) y est intégré.

const todayISO = () => {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const j = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${j}`
}

const formatDateFR = (iso) => {
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function SortableTh({ col, label, sort, onSort, className, help }) {
  const active = sort.key === col
  return (
    <th className={className} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      {/* `help` reste HORS du bouton de tri : deux éléments interactifs ne
          s'imbriquent jamais (<button> dans <button> serait invalide). */}
      <span className="inline-flex items-center gap-1">
        <button type="button" className="lv-th-btn" onClick={() => onSort(col)}>
          {label}
          <span className="lv-sort-ind" aria-hidden="true">
            {active ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
          </span>
        </button>
        {help}
      </span>
    </th>
  )
}

// VX187 — ligne extraite + memo() : `ListView` porte de l'état LOCAL sans
// rapport avec le contenu des lignes (busyId, insightsLead, nudgeLead, sort…)
// — chaque changement (ex. après un clic Archiver) re-rendait TOUTES les
// lignes de la table, pas seulement celle concernée. `checked` est un
// booléen dédié (pas le `Set` `selected` entier) pour que memo() compare une
// primitive, pas une référence qui change de forme à chaque sélection.
const ListRow = memo(function ListRow({
  lead, checked, onToggleSelect, onOpenLead, armCallNudgeFor, onInlineSave,
  users, onReassign, onAutoQuote, canDelete, busy, onRestore, onArchive,
  onDelete, isMobile, onOpenInsights, today,
  perduTarget, setPerduTarget, closePerdu, perduMotif, setPerduMotif,
  perduBusy, confirmPerdu, motifsPerte,
}) {
  const perdu = isPerdu(lead)
  const stars = PRIORITE_STARS[lead.priorite] ?? 1
  const tags = tagList(lead)
  const enRetard = lead.relance_date && lead.relance_date < today
  return (
    <tr
      className={`lv-row${perdu ? ' lv-row-perdu' : ''}${lead.is_archived ? ' lv-row-archived' : ''}${checked ? ' lv-row-selected' : ''}`}
      onClick={() => onOpenLead(lead)}
    >
      {onToggleSelect && (
        <td
          className="lv-check-col"
          onClick={(e) => e.stopPropagation()}
        >
          <Checkbox
            aria-label={`Sélectionner ${fullName(lead) || 'ce lead'}`}
            checked={checked}
            onCheckedChange={() => onToggleSelect(lead.id)}
          />
        </td>
      )}
      <td data-label="Lead">
        <div className="lv-lead-cell">
          <span className="lv-lead-name">
            {fullName(lead) || '—'}
            {perdu && <span className="lv-badge-perdu">Perdu</span>}
          </span>
          {lead.societe ? (
            <span className="lv-lead-societe">{lead.societe}</span>
          ) : null}
          {/* QX25 — repli tap-to-call mobile : la colonne Téléphone
              (m-hide) disparaît sous 768px, ces icônes compactes
              restent visibles dans la cellule Lead (jamais masquée). */}
          {(telHref(lead.telephone) || waHref(lead.whatsapp)) && (
            <span className="lv-lead-contact" style={{ display: 'inline-flex', gap: '8px', marginTop: '2px' }}
                  onClick={(e) => e.stopPropagation()}>
              {telHref(lead.telephone) && (
                <a href={telHref(lead.telephone)} title="Appeler"
                   aria-label={`Appeler ${fullName(lead) || 'ce lead'}`}
                   className="text-muted-foreground hover:text-foreground"
                   onClick={() => armCallNudgeFor(lead)}>
                  <PhoneCall className="size-3.5" aria-hidden="true" />
                </a>
              )}
              {waHref(lead.whatsapp) && (
                <ExternalLink href={waHref(lead.whatsapp)}
                   title="Ouvrir WhatsApp" aria-label={`WhatsApp ${fullName(lead) || 'ce lead'}`}
                   className="text-muted-foreground hover:text-foreground">
                  <MessageCircle className="size-3.5" aria-hidden="true" />
                </ExternalLink>
              )}
            </span>
          )}
          {/* VX243(a) — confiance au niveau du DOSSIER : une ligne archivée
              montre QUI l'a archivée et QUAND (archived_by/at étaient capturés
              serveur mais jamais rendus). Silencieux sur un lead vivant. */}
          {lead.is_archived && (lead.archived_by_nom || lead.archived_at) && (
            <span className="lv-lead-archived-by text-xs text-muted-foreground">
              Archivé{lead.archived_by_nom ? ` par ${lead.archived_by_nom}` : ''}
              {lead.archived_at ? ` le ${formatDate(lead.archived_at)}` : ''}
            </span>
          )}
        </div>
      </td>
      <td data-label="Stade" onClick={(e) => e.stopPropagation()}>
        <InlineEdit
          value={lead.stage}
          options={stageOptionsFor(lead.stage)}
          disabled={!onInlineSave}
          display={(
            // Pastille d'étape via StatusPill (tons tokenisés depuis
            // statusTone) — plus aucune palette #hex en dur ici. Le
            // libellé FR vient de stages.js (miroir STAGES.py).
            <StatusPill
              status={lead.stage}
              label={STAGE_LABELS[lead.stage] ?? lead.stage}
              className="lv-stage-badge"
            />
          )}
          onSave={(v) => onInlineSave(lead, 'stage', v)}
        />
      </td>
      <td className="m-hide" data-label="Score">
        <ScoreBadge lead={lead} />
      </td>
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        {lead.telephone ? (
          <a className="link-blue" href={`tel:${lead.telephone}`}
             onClick={() => armCallNudgeFor(lead)}>
            {lead.telephone}
          </a>
        ) : '—'}
      </td>
      <td className="m-hide">{lead.ville || '—'}</td>
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        <InlineEdit
          value={lead.facture_hiver ?? ''}
          type="number"
          disabled={!onInlineSave}
          placeholder="+ facture"
          display={lead.facture_hiver != null && lead.facture_hiver !== '' ? (
            <span>
              {formatMAD(lead.facture_hiver, { decimals: 0 })}
            </span>
          ) : null}
          onSave={(v) => onInlineSave(lead, 'facture_hiver', v === '' ? null : v)}
        />
      </td>
      <td className="m-hide">{CANAL_LABELS[lead.canal] ?? '—'}</td>
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        <AssigneePicker
          users={users}
          value={lead.owner ?? ''}
          onChange={(id) => onReassign?.(lead, id)}
          size={22}
          disabled={!onReassign}
        />
      </td>
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        <InlineEdit
          value={lead.priorite ?? 'normale'}
          options={PRIORITE_OPTIONS}
          disabled={!onInlineSave}
          display={(
            <span
              className="lv-stars"
              title={PRIORITE_LABELS[lead.priorite] ?? PRIORITE_LABELS.normale}
            >
              <span className={stars >= 1 ? 'lv-star lv-star-on' : 'lv-star'}>★</span>
              <span className={stars >= 2 ? 'lv-star lv-star-on' : 'lv-star'}>★</span>
            </span>
          )}
          onSave={(v) => onInlineSave(lead, 'priorite', v)}
        />
      </td>
      <td data-label="Relance" onClick={(e) => e.stopPropagation()}>
        <InlineEdit
          value={lead.relance_date ?? ''}
          type="date"
          disabled={!onInlineSave}
          display={lead.relance_date ? (
            <span className={enRetard ? 'lv-relance-late' : undefined}>
              {formatDateFR(lead.relance_date)}
            </span>
          ) : null}
          onSave={(v) => onInlineSave(lead, 'relance_date', v)}
        />
      </td>
      <td className="m-hide">
        {lead.next_activity ? (
          <span
            className={lead.next_activity.state === 'overdue'
              ? 'lv-relance-late' : undefined}
            title={lead.next_activity.summary || undefined}
          >
            {formatDateFR(lead.next_activity.due_date)}
            {lead.next_activity.summary
              ? ` · ${lead.next_activity.summary}` : ''}
          </span>
        ) : <span className="lv-muted">—</span>}
      </td>
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        <InlineEdit
          value={lead.tags ?? ''}
          type="text"
          disabled={!onInlineSave}
          placeholder="+ tags"
          display={tags.length ? (
            <span className="lv-tags">
              {tags.map((t) => {
                const c = tagColor(t)
                return (
                  <span
                    key={t}
                    className="lv-tag"
                    style={{ background: c.bg, color: c.color }}
                  >
                    {t}
                  </span>
                )
              })}
            </span>
          ) : null}
          onSave={(v) => onInlineSave(lead, 'tags', v)}
        />
      </td>
      <td data-label="Actions" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {/* VX223 — « ✗ Perdu » : action à 2 clics toujours visible sur
            la ligne (pas enfouie dans le menu « ⋯ » mobile — le
            geste le plus fréquent du quotidien commercial). Absente
            si déjà perdu. */}
        {!perdu && (
          <Popover
            open={perduTarget?.id === lead.id}
            onOpenChange={(v) => (v ? setPerduTarget(lead) : closePerdu())}
          >
            <PopoverTrigger asChild>
              <IconButton
                label="Marquer perdu"
                variant="ghost"
                size="icon"
                className="size-8"
              >
                ✗
              </IconButton>
            </PopoverTrigger>
            <PopoverContent align="start">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '220px' }}>
                <p style={{ fontSize: '13px', fontWeight: 500, margin: 0 }}>Marquer perdu</p>
                <input
                  className="form-control"
                  list={`lv-motifs-${lead.id}`}
                  placeholder="Motif de perte"
                  value={perduMotif}
                  onChange={(e) => setPerduMotif(e.target.value)}
                  autoFocus
                />
                <datalist id={`lv-motifs-${lead.id}`}>
                  {(motifsPerte ?? []).map((m) => <option key={m.id} value={m.nom} />)}
                </datalist>
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px' }}>
                  <Button type="button" variant="outline" size="sm" onClick={closePerdu}>
                    Annuler
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={!perduMotif.trim() || perduBusy}
                    loading={perduBusy}
                    onClick={confirmPerdu}
                  >
                    Confirmer
                  </Button>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        )}
        {(() => {
          // Actions de ligne dans l'ordre — partagées entre l'affichage
          // boutons (desktop) et le menu « ⋯ » (mobile).
          const actions = [
            {
              id: 'edit', label: 'Éditer',
              onClick: () => onOpenLead(lead),
            },
            {
              id: 'parcours', label: 'Parcours',
              title: 'Points de contact & correspondance client',
              onClick: () => onOpenInsights(lead),
            },
            {
              id: 'devis', label: '⚡ Devis auto',
              disabled: !lead.devis_auto?.pret,
              title: lead.devis_auto?.pret
                ? 'Devis auto'
                : (lead.devis_auto?.message ?? 'Devis auto indisponible'),
              onClick: () => onAutoQuote(lead),
            },
            lead.is_archived
              ? {
                id: 'restore', label: 'Restaurer',
                disabled: busy,
                onClick: () => onRestore(lead),
              }
              : {
                id: 'archive', label: 'Archiver',
                disabled: busy,
                onClick: () => onArchive(lead),
              },
          ]
          if (canDelete) {
            actions.push({
              id: 'delete', label: 'Supprimer', destructive: true,
              disabled: busy,
              onClick: () => onDelete(lead),
            })
          }
          if (isMobile) {
            // Mobile : un seul bouton « ⋯ » ouvre le menu d'actions.
            return (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <IconButton
                    label="Actions du lead"
                    variant="ghost"
                    size="icon"
                    className="size-8"
                  >
                    <MoreHorizontal />
                  </IconButton>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Actions</DropdownMenuLabel>
                  {actions.map((a) => (
                    <Fragment key={a.id}>
                      {a.destructive && <DropdownMenuSeparator />}
                      <DropdownMenuItem
                        destructive={a.destructive}
                        disabled={a.disabled}
                        onSelect={() => a.onClick()}
                      >
                        {a.label}
                      </DropdownMenuItem>
                    </Fragment>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )
          }
          return (
            <div className="actions-cell">
              {actions.map((a) => (
                <Button
                  key={a.id}
                  type="button"
                  size="sm"
                  variant={a.destructive
                    ? 'destructive'
                    : (a.id === 'devis' ? undefined : 'outline')}
                  className={a.id === 'devis' ? 'gen-btn-orange' : undefined}
                  disabled={a.disabled}
                  title={a.title}
                  onClick={() => a.onClick()}
                >
                  {a.label}
                </Button>
              ))}
            </div>
          )
        })()}
        </div>
      </td>
    </tr>
  )
})

export default function ListView({
  leads, onOpenLead, onAutoQuote, onRefetch, users = [], onReassign,
  selected = new Set(), onToggleSelect, onToggleAll, onInlineSave,
}) {
  const dispatch = useDispatch()
  const canDelete = useIsAdmin() // règle existante : destroy = admin
  const isMobile = useIsMobile()
  // Par défaut : plus récents d'abord (date_creation desc), aucune colonne active.
  const [sort, setSort] = useState({ key: null, dir: 'asc' })
  const [busyId, setBusyId] = useState(null)
  // WR9 — fiche « Parcours » (timeline multi-touch + correspondance client).
  const [insightsLead, setInsightsLead] = useState(null)
  const today = todayISO()

  // VX223 — « ✗ Perdu » en 2 clics depuis une ligne : (1) ouvrir la
  // mini-popover, (2) choisir un motif → confirmer, UNE seule requête PATCH
  // `perdu`+`motif_perte`. Une seule popover à la fois dans la table (comme le
  // nudge post-appel ci-dessous) — `perduTarget` porte le lead ciblé.
  const [perduTarget, setPerduTarget] = useState(null)
  const [perduMotif, setPerduMotif] = useState('')
  const [perduBusy, setPerduBusy] = useState(false)
  const [motifsPerte, setMotifsPerte] = useState(null) // null = pas encore chargés
  useEffect(() => {
    if (!perduTarget || motifsPerte !== null) return
    crmApi.getMotifsPerte()
      .then((r) => setMotifsPerte(((r.data?.results ?? r.data) || []).filter((m) => !m.archived)))
      .catch(() => setMotifsPerte([]))
  }, [perduTarget, motifsPerte])
  const closePerdu = () => { setPerduTarget(null); setPerduMotif('') }
  const confirmPerdu = async () => {
    const motif = perduMotif.trim()
    if (!motif || !perduTarget) return
    setPerduBusy(true)
    try {
      await dispatch(updateLead({
        id: perduTarget.id, data: { perdu: true, motif_perte: motif },
      })).unwrap()
      onRefetch?.()
      closePerdu()
    } catch {
      toastError('Le lead n’a pas pu être marqué perdu — réessayez.')
    } finally {
      setPerduBusy(false)
    }
  }

  // VX87 — nudge post-appel : armé au tap tel: (mémorise QUEL lead a été
  // appelé, une table n'a qu'un seul nudge visible à la fois — comme un
  // vendeur ne passe qu'un appel à la fois), proposé au retour dans l'onglet.
  const { nudgeVisible, armCallNudge, dismissNudge } = useCallEndedNudge()
  const [nudgeLead, setNudgeLead] = useState(null)
  const armCallNudgeFor = (lead) => { setNudgeLead(lead); armCallNudge() }

  const onArchive = async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(archiveLead(lead.id)).unwrap()
      onRefetch?.()
      // VX95 — l'archivage est déjà commis côté serveur : « Annuler » relance
      // l'action inverse (restaurerLead), pas un commit différé.
      toastWithUndo({
        message: 'Lead archivé.',
        onUndo: async () => {
          try {
            await dispatch(restoreLead(lead.id)).unwrap()
            onRefetch?.()
          } catch { toastError('Restauration impossible.') }
        },
      })
    } catch { /* erreur silencieuse */ } finally { setBusyId(null) }
  }

  const onRestore = async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(restoreLead(lead.id)).unwrap()
      onRefetch?.()
      toastWithUndo({
        message: 'Lead restauré.',
        onUndo: async () => {
          try {
            await dispatch(archiveLead(lead.id)).unwrap()
            onRefetch?.()
          } catch { toastError('Archivage impossible.') }
        },
      })
    } catch { /* erreur silencieuse */ } finally { setBusyId(null) }
  }

  const onDelete = async (lead) => {
    // VX96 — la suppression est RÉVERSIBLE (soft-delete + corbeille 30 min) :
    // plus de copie « irréversible », et un toast « Annuler » restaure le lead.
    if (!window.confirm('Supprimer ce lead ? Il ira à la corbeille (restaurable 30 min).')) return
    setBusyId(lead.id)
    try {
      const { corbeille_id: corbeilleId } = await dispatch(deleteLead(lead.id)).unwrap()
      toastWithUndo({
        message: 'Lead supprimé.',
        description: 'Restaurable pendant 30 minutes depuis la corbeille.',
        onUndo: async () => {
          if (!corbeilleId) return
          try {
            await crmApi.restaurerCorbeille(corbeilleId)
            onRefetch?.()
          } catch { toastError('Restauration impossible.') }
        },
      })
      onRefetch?.()
    } catch (err) {
      // 409 : lead lié à un devis → on archive plutôt que de supprimer.
      window.alert(err?.detail ?? 'Suppression impossible.')
    } finally { setBusyId(null) }
  }

  const onSort = (key) =>
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' },
    )

  const sorted = useMemo(() => {
    const arr = [...(leads ?? [])]
    if (!sort.key) {
      return arr.sort(
        (a, b) => new Date(b.date_creation ?? 0) - new Date(a.date_creation ?? 0),
      )
    }
    const dir = sort.dir === 'desc' ? -1 : 1
    const cmp = SORTERS[sort.key]
    return arr.sort((a, b) => {
      // Relance : les dates vides restent TOUJOURS en fin de liste.
      if (sort.key === 'relance') {
        if (!a.relance_date && !b.relance_date) return 0
        if (!a.relance_date) return 1
        if (!b.relance_date) return -1
      }
      return dir * cmp(a, b)
    })
  }, [leads, sort])

  const visibleIds = sorted.map((l) => l.id)
  const allChecked = allVisibleSelected(selected, visibleIds)

  return (
    <div className="lv-wrap">
      {/* VX7 — calm color : séparateurs adoucis + actions révélées au survol. */}
      <table className="data-table lv-table calm-list">
        <thead>
          <tr>
            {onToggleSelect && (
              <th className="lv-check-col">
                <Checkbox
                  aria-label="Tout sélectionner"
                  checked={allChecked}
                  onCheckedChange={() => onToggleAll?.(visibleIds)}
                />
              </th>
            )}
            <SortableTh col="lead" label="Lead" sort={sort} onSort={onSort} />
            <SortableTh col="stage" label="Stade" sort={sort} onSort={onSort} />
            <SortableTh
              col="score" label="Score" sort={sort} onSort={onSort} className="m-hide"
              // VX47 — aide contextuelle : « d'où vient ce chiffre » n'est
              // expliqué nulle part côté écran (scoring.py reste opaque).
              help={(
                <HelpTip label="Aide — score de lead">
                  Le score (0-100) combine des signaux automatiques : complétude
                  du profil, montant de facture (budget), canal d'acquisition,
                  type d'installation, ancienneté du lead et maturité d'achat
                  déclarée (propriétaire, délai, financement…).
                  <strong> Chaud</strong> (≥70), <strong>Tiède</strong> (45-69),
                  <strong> Froid</strong> (&lt;45) — recalculé à chaque mise à
                  jour du lead.
                </HelpTip>
              )}
            />
            <SortableTh col="telephone" label="Téléphone" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="ville" label="Ville" sort={sort} onSort={onSort} className="m-hide" />
            <th className="m-hide">Facture</th>
            <SortableTh col="canal" label="Canal" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="owner" label="Responsable" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="priorite" label="Priorité" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="relance" label="Relance" sort={sort} onSort={onSort} />
            <th className="m-hide">Prochaine activité</th>
            <th className="m-hide">Tags</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((lead) => (
            <ListRow
              key={lead.id}
              lead={lead}
              checked={selected.has(lead.id)}
              onToggleSelect={onToggleSelect}
              onOpenLead={onOpenLead}
              armCallNudgeFor={armCallNudgeFor}
              onInlineSave={onInlineSave}
              users={users}
              onReassign={onReassign}
              onAutoQuote={onAutoQuote}
              canDelete={canDelete}
              busy={busyId === lead.id}
              onRestore={onRestore}
              onArchive={onArchive}
              onDelete={onDelete}
              isMobile={isMobile}
              onOpenInsights={setInsightsLead}
              today={today}
              perduTarget={perduTarget}
              setPerduTarget={setPerduTarget}
              closePerdu={closePerdu}
              perduMotif={perduMotif}
              setPerduMotif={setPerduMotif}
              perduBusy={perduBusy}
              confirmPerdu={confirmPerdu}
              motifsPerte={motifsPerte}
            />
          ))}
          {!sorted.length && (
            <tr>
              <td colSpan={onToggleSelect ? 13 : 12} className="lv-empty">
                {/* VX147 — « 0 lead » unifié sur `EmptyState` (calqué sur
                    ChartsView) au lieu du texte brut précédent. */}
                <EmptyState
                  icon={List}
                  title="Aucun lead"
                  description="Aucun lead ne correspond à ces filtres."
                />
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {insightsLead && (
        <LeadInsightsDialog
          lead={insightsLead}
          onClose={() => setInsightsLead(null)}
        />
      )}
      {/* VX87 — nudge post-appel : proposé au retour dans l'onglet après un
          tap tel: sur une ligne, jamais intrusif — dismissable. */}
      {nudgeVisible && nudgeLead && (
        <div className="lv-call-nudge" role="status">
          <span className="lv-call-nudge-text">
            Appel terminé avec {fullName(nudgeLead) || 'ce lead'} — noter le résultat ?
          </span>
          <CallLogPopover
            leadId={nudgeLead.id}
            trigger={<button type="button" className="lv-call-nudge-log">Noter</button>}
            onLogged={dismissNudge}
          />
          <button
            type="button"
            className="lv-call-nudge-dismiss"
            aria-label="Ignorer"
            onClick={dismissNudge}
          >
            ✕
          </button>
        </div>
      )}
    </div>
  )
}
