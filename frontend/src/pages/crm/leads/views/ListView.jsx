// Vue LISTE des leads CRM — table dense et triable, façon Odoo.
// Les étapes viennent EXCLUSIVEMENT de features/crm/stages (miroir de
// STAGES.py) : aucune liste d'étapes n'est déclarée ici.
import { Fragment, useCallback, useEffect, useMemo, useReducer, useRef, useState, memo } from 'react'
import { MoreHorizontal, PhoneCall, MessageCircle, List } from 'lucide-react'
import { useDispatch } from 'react-redux'
import { EmptyState } from '../../../../ui'
import { useIsAdmin } from '../../../../hooks/useHasPermission'
import { archiveLead, restoreLead, deleteLead } from '../../../../features/crm/store/crmSlice'
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
// LB19 — choix de colonnes persisté : import DIRECT de deux pièces du
// moteur ui/datatable (blueprint D4, zéro fork) — `useColumnPrefs`
// (persistance localStorage) + `ColumnManager`/`columnStateReducer`/
// `initColumnState` (UI + réducteur pur d'état des colonnes). Explicitement
// PAS `DataTable`/`FilterBuilder`/`urlState` : un seul état de filtres pour
// toute la page (D5), cette liste n'en emprunte rien d'autre.
import { useColumnPrefs } from '../../../../ui/datatable/useColumnPrefs'
import { ColumnManager, columnStateReducer, initColumnState } from '../../../../ui/datatable'

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

// LB18 — modèle de colonnes déclaré UNE fois : alimente le `<colgroup>`
// (largeurs fixes — l'édition inline ne fait plus danser les colonnes
// voisines, P3 #14) puis, LB19, `useColumnPrefs`/`ColumnManager` (moteur
// ui/datatable, import direct — blueprint D4, zéro fork). `hideable: false`
// = colonnes cœur jamais proposées au choix (Lead/Stade/Relance/Actions) ;
// les autres reprennent EXACTEMENT l'ensemble qui portait `.m-hide` (repli
// responsive existant) — la visibilité PAR DÉFAUT du modèle est donc
// identique au rendu desktop actuel (toutes visibles).
const LIST_COLUMNS = [
  { id: 'lead', header: 'Lead', width: 220, hideable: false },
  { id: 'stage', header: 'Stade', width: 150, hideable: false },
  { id: 'score', header: 'Score', width: 90 },
  { id: 'telephone', header: 'Téléphone', width: 150 },
  { id: 'ville', header: 'Ville', width: 110 },
  { id: 'facture', header: 'Facture', width: 110 },
  { id: 'canal', header: 'Canal', width: 140 },
  { id: 'owner', header: 'Responsable', width: 150 },
  { id: 'priorite', header: 'Priorité', width: 90 },
  { id: 'relance', header: 'Relance', width: 120, hideable: false },
  { id: 'next_activity', header: 'Prochaine activité', width: 190 },
  { id: 'tags', header: 'Tags', width: 160 },
  { id: 'actions', header: 'Actions', width: 190, hideable: false },
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
// LB6 — la popover « ✗ Perdu » reçoit désormais des PRIMITIVES + callbacks
// stables uniquement (blueprint I4, bug #4) : `perduOpen` (booléen, calculé
// par le parent) au lieu de `perduTarget` (l'objet lead entier — changeait de
// référence à chaque frappe pour TOUTES les lignes) ; `perduMotif`/`perduBusy`
// sont désormais CONDITIONNÉS par la ligne appelante (le parent passe une
// valeur constante '' / false aux lignes non ciblées, la valeur live SEULEMENT
// à la ligne ouverte) — taper un motif ne re-rend plus que la ligne ciblée.
// `confirmPerdu(lead, motif)` prend ses arguments en paramètres (au lieu de
// lire `perduTarget`/`perduMotif` en closure) : sa référence reste STABLE
// quel que soit ce que l'utilisateur tape.
const ListRow = memo(function ListRow({
  lead, checked, onToggleSelect, onOpenLead, armCallNudgeFor, onInlineSave,
  users, onReassign, onAutoQuote, canDelete, busy, onRestore, onArchive,
  onDelete, isMobile, onOpenInsights, today, hiddenCols = {},
  perduOpen, onRequestPerduOpen, closePerdu, perduMotif, setPerduMotif,
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
      <td data-label="Lead" className="lv-sticky-name">
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
      {!hiddenCols.score && (
      <td className="m-hide" data-label="Score">
        <ScoreBadge lead={lead} />
      </td>
      )}
      {!hiddenCols.telephone && (
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        {lead.telephone ? (
          <a className="link-blue" href={`tel:${lead.telephone}`}
             onClick={() => armCallNudgeFor(lead)}>
            {lead.telephone}
          </a>
        ) : '—'}
      </td>
      )}
      {!hiddenCols.ville && <td className="m-hide">{lead.ville || '—'}</td>}
      {!hiddenCols.facture && (
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
      )}
      {!hiddenCols.canal && (
        <td className="m-hide">{CANAL_LABELS[lead.canal] ?? '—'}</td>
      )}
      {!hiddenCols.owner && (
      <td className="m-hide" onClick={(e) => e.stopPropagation()}>
        <AssigneePicker
          users={users}
          value={lead.owner ?? ''}
          onChange={(id) => onReassign?.(lead, id)}
          size={22}
          disabled={!onReassign}
        />
      </td>
      )}
      {!hiddenCols.priorite && (
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
      )}
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
      {!hiddenCols.next_activity && (
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
      )}
      {!hiddenCols.tags && (
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
      )}
      <td data-label="Actions" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {/* VX223 — « ✗ Perdu » : action à 2 clics toujours visible sur
            la ligne (pas enfouie dans le menu « ⋯ » mobile — le
            geste le plus fréquent du quotidien commercial). Absente
            si déjà perdu. */}
        {!perdu && (
          <Popover
            open={perduOpen}
            onOpenChange={(v) => (v ? onRequestPerduOpen(lead) : closePerdu())}
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
                    onClick={() => confirmPerdu(lead, perduMotif)}
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
  selected = new Set(), onToggleSelect, onToggleAll, onInlineSave, onMarkPerdu,
}) {
  const dispatch = useDispatch()
  const canDelete = useIsAdmin() // règle existante : destroy = admin
  const isMobile = useIsMobile()
  // LB18 — `.lv-wrap` est LE scrolleur deux axes (D1) : un listener de
  // scroll PASSIF (jamais de re-rendu React — classList directe sur le DOM)
  // bascule `.lv-scrolled-x` dès que le scroll horizontal démarre, pour
  // l'ombre de bord de la colonne nom épinglée (.lv-sticky-name, index.css).
  const wrapRef = useRef(null)
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const onScroll = () => {
      el.classList.toggle('lv-scrolled-x', el.scrollLeft > 0)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [])
  // LB19 — état des colonnes : préférences localStorage lues UNE FOIS au
  // montage (`useColumnPrefs`, clé `taqinor.leads.columns…`) puis pilotées
  // par le réducteur PUR du moteur (`columnStateReducer` — show/hide,
  // inchangé, zéro fork) ; toute mutation est notifiée en retour pour la
  // persistance (même contrat que `useDataTable`, NTUX16). Colonnes
  // core (hideable:false) ne peuvent jamais entrer dans `.hidden`
  // (ColumnManager les exclut déjà du menu de choix).
  const { initialColumnState, onColumnStateChange } = useColumnPrefs('leads.columns')
  const [columnState, dispatchColumns] = useReducer(
    columnStateReducer,
    LIST_COLUMNS,
    (cols) => initialColumnState || initColumnState(cols),
  )
  useEffect(() => {
    onColumnStateChange(columnState)
  }, [columnState, onColumnStateChange])
  const hiddenCols = columnState.hidden
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
  // LB6 — callbacks stables (bug #4) : `setPerduTarget` (useState) est déjà
  // stable, passé directement comme `onRequestPerduOpen` à chaque ligne.
  const closePerdu = useCallback(() => { setPerduTarget(null); setPerduMotif('') }, [])
  // LB5 — passe par le callback stable de LeadsPage (onMarkPerdu, blueprint
  // I2) : store seul source de vérité, AUCUN refetch (updateLead.fulfilled
  // patche déjà le lead complet). Le toast d'échec est déjà émis par
  // onMarkPerdu. LB6 — signature `(lead, motif)` en PARAMÈTRES (au lieu de
  // lire `perduTarget`/`perduMotif` en closure) : la référence reste stable
  // quel que soit ce que l'utilisateur tape, `[onMarkPerdu, closePerdu]`
  // suffit (bug #4 — taper un motif ne re-rendait auparavant PAS que la ligne
  // ciblée, faute de quoi TOUTE la table re-rendait à chaque frappe).
  const confirmPerdu = useCallback(async (lead, motif) => {
    const trimmed = (motif ?? '').trim()
    if (!trimmed || !lead || !onMarkPerdu) return
    setPerduBusy(true)
    try {
      await onMarkPerdu(lead, trimmed)
      closePerdu()
    } catch {
      // Échec : toast déjà affiché par onMarkPerdu, popover reste ouverte
      // (le motif saisi n'est pas perdu, l'utilisateur peut retenter).
    } finally {
      setPerduBusy(false)
    }
  }, [onMarkPerdu, closePerdu])

  // VX87 — nudge post-appel : armé au tap tel: (mémorise QUEL lead a été
  // appelé, une table n'a qu'un seul nudge visible à la fois — comme un
  // vendeur ne passe qu'un appel à la fois), proposé au retour dans l'onglet.
  const { nudgeVisible, armCallNudge, dismissNudge } = useCallEndedNudge()
  const [nudgeLead, setNudgeLead] = useState(null)
  // LB6 — `armCallNudge` (renvoyé par useCallEndedNudge, features/crm/
  // CallLogPopover.jsx) est une closure FRAÎCHE à chaque rendu — un ref
  // toujours à jour (synchronisé en effet, JAMAIS écrit pendant le rendu)
  // laisse `armCallNudgeFor` rester stable (`[]`) sans modifier ce hook
  // partagé (hors périmètre de cette lane). L'effet s'exécute après le
  // commit, donc AVANT que l'utilisateur ne clique réellement sur tel:.
  const armCallNudgeRef = useRef(armCallNudge)
  useEffect(() => { armCallNudgeRef.current = armCallNudge })
  const armCallNudgeFor = useCallback((lead) => {
    setNudgeLead(lead)
    armCallNudgeRef.current()
  }, [])

  // LB6 — useCallback : passées à CHAQUE ligne, une référence fraîche à
  // chaque rendu de ListView (ex. après un simple changement de `busyId`)
  // cassait memo(ListRow) pour TOUTES les lignes (bug #4).
  // LB7 — bugs recon2-03 #5/#11 : archiveLead.fulfilled/restoreLead.fulfilled
  // (crmSlice.js) remplacent déjà le lead au complet dans le store (is_archived
  // inclus — la ligne se re-rend grisée/« Restaurer » SEULE, sans refetch) ;
  // plus de refetch intégral après ce PATCH mono-lead (I1). Catch externe
  // silencieux → toastError (I8) ; les catches internes (undo) toastaient déjà.
  const onArchive = useCallback(async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(archiveLead(lead.id)).unwrap()
      // VX95 — l'archivage est déjà commis côté serveur : « Annuler » relance
      // l'action inverse (restaurerLead), pas un commit différé.
      toastWithUndo({
        message: 'Lead archivé.',
        onUndo: async () => {
          try {
            await dispatch(restoreLead(lead.id)).unwrap()
          } catch { toastError('Restauration impossible.') }
        },
      })
    } catch {
      toastError("L'archivage a échoué — réessayez.")
    } finally { setBusyId(null) }
  }, [dispatch])

  const onRestore = useCallback(async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(restoreLead(lead.id)).unwrap()
      toastWithUndo({
        message: 'Lead restauré.',
        onUndo: async () => {
          try {
            await dispatch(archiveLead(lead.id)).unwrap()
          } catch { toastError('Archivage impossible.') }
        },
      })
    } catch {
      toastError('La restauration a échoué — réessayez.')
    } finally { setBusyId(null) }
  }, [dispatch])

  const onDelete = useCallback(async (lead) => {
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
  }, [dispatch, onRefetch])

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
  // LB19 — colonnes réellement rendues (modèle moins celles masquées par
  // l'utilisateur) : réutilisé par le <colgroup> ET le colSpan de l'état
  // vide, pour qu'ils restent TOUJOURS en phase.
  const visibleColumns = useMemo(
    () => LIST_COLUMNS.filter((c) => !hiddenCols[c.id]),
    [hiddenCols],
  )

  return (
    <div className="lv-view">
      {/* LB19 — barre d'outils locale (choix de colonnes) : HORS du
          scrolleur .lv-wrap pour rester visible pendant le défilement
          vertical de la table. */}
      <div className="lv-toolbar">
        <ColumnManager columns={LIST_COLUMNS} columnState={columnState} dispatch={dispatchColumns} />
      </div>
      <div className="lv-wrap" ref={wrapRef}>
        {/* VX7 — calm color : séparateurs adoucis + actions révélées au survol. */}
        <table className="data-table lv-table calm-list">
        {/* LB18 — largeurs fixes (table-layout:fixed, index.css) : ouvrir un
            <select> d'édition en place ne fait plus danser les colonnes
            voisines (P3 #14). LB19 — filtré par colonne CACHÉE : le nombre
            de <col> doit toujours correspondre au nombre de <td>/<th> réels
            rendus (le navigateur aligne colgroup positionnellement). */}
        <colgroup>
          {onToggleSelect && <col style={{ width: 36 }} />}
          {visibleColumns.map((c) => <col key={c.id} style={{ width: c.width }} />)}
        </colgroup>
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
            <SortableTh col="lead" label="Lead" sort={sort} onSort={onSort} className="lv-sticky-name" />
            <SortableTh col="stage" label="Stade" sort={sort} onSort={onSort} />
            {!hiddenCols.score && (
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
            )}
            {!hiddenCols.telephone && (
              <SortableTh col="telephone" label="Téléphone" sort={sort} onSort={onSort} className="m-hide" />
            )}
            {!hiddenCols.ville && (
              <SortableTh col="ville" label="Ville" sort={sort} onSort={onSort} className="m-hide" />
            )}
            {!hiddenCols.facture && <th className="m-hide">Facture</th>}
            {!hiddenCols.canal && (
              <SortableTh col="canal" label="Canal" sort={sort} onSort={onSort} className="m-hide" />
            )}
            {!hiddenCols.owner && (
              <SortableTh col="owner" label="Responsable" sort={sort} onSort={onSort} className="m-hide" />
            )}
            {!hiddenCols.priorite && (
              <SortableTh col="priorite" label="Priorité" sort={sort} onSort={onSort} className="m-hide" />
            )}
            <SortableTh col="relance" label="Relance" sort={sort} onSort={onSort} />
            {!hiddenCols.next_activity && <th className="m-hide">Prochaine activité</th>}
            {!hiddenCols.tags && <th className="m-hide">Tags</th>}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((lead) => {
            // LB6 — SEULE la ligne ciblée reçoit la valeur LIVE de
            // perduMotif/perduBusy ; toutes les autres reçoivent une
            // constante ('' / false) qui ne change JAMAIS entre deux rendus
            // — memo(ListRow) bail out pour elles, seule la ligne ouverte
            // re-rend à chaque frappe (bug #4).
            const isPerduTarget = perduTarget?.id === lead.id
            return (
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
                perduOpen={isPerduTarget}
                onRequestPerduOpen={setPerduTarget}
                closePerdu={closePerdu}
                perduMotif={isPerduTarget ? perduMotif : ''}
                setPerduMotif={setPerduMotif}
                perduBusy={isPerduTarget ? perduBusy : false}
                confirmPerdu={confirmPerdu}
                motifsPerte={motifsPerte}
                hiddenCols={hiddenCols}
              />
            )
          })}
          {!sorted.length && (
            <tr>
              <td colSpan={(onToggleSelect ? 1 : 0) + visibleColumns.length} className="lv-empty">
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
    </div>
  )
}
