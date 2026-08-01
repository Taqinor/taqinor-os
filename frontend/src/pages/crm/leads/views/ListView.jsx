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
// EZ14 — undo universel : « appliquer tout de suite + inverse à l'annulation »,
// jamais le commit différé qui perd l'écriture au démontage d'un board.
import { mutateWithUndo } from '../../../../lib/mutateWithUndo'
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
  // LB20 — option « Par étape » : MÊME agrégation que le kanban (count +
  // totalDevis par étape) pour que les deux vues affichent toujours les
  // mêmes nombres.
  groupLeadsByStage,
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
import PerduPopover from '../PerduPopover'
import { isSigneIntercept } from '../signeIntercept'
import { allVisibleSelected } from '../../../../features/crm/bulk'
import {
  Button, Checkbox, HelpTip, IconButton, StatusPill, Segmented,
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
import { useIsMobile } from '../../../../ui/ResponsiveDialog'

// LB32 — dédup : hook CANONIQUE `useIsMobile` (ui/ResponsiveDialog, déjà
// adopté par LeadsPage.jsx/LeadWorkspace) au lieu d'une copie locale
// verbatim (identique à celles de FilterBar.jsx/ChartsView.jsx). Même
// breakpoint qu'avant (768px, passé en paramètre) — comportement inchangé.
const MOBILE_QUERY = '(max-width: 768px)'

/* APX9 — palier de RENDU de la liste (le pendant de RENDER_CAP=40 du kanban).
   Une ligne de tableau coûte bien moins qu'une carte, et la Liste EST la vue
   dense (APX5) : la faire cliquer tous les 40 leads irait contre sa raison
   d'être. 200 monte tout jusqu'à 200 leads — la très grande majorité des
   pipelines — et borne le pire cas. */
const LIST_RENDER_CAP = 200

/* EZ14 — champs éditables en place qui gagnent l'undo, et leur genre au
   REGISTRE FERMÉ (lib/mutateWithUndo.js). Un champ absent d'ici s'enregistre
   exactement comme avant : c'est le cas voulu pour `facture_hiver` (un montant)
   et pour tout champ d'argent — jamais d'« Annuler » sur l'argent. */
const CHAMPS_UNDO = {
  stage: { kind: 'lead_stage', message: 'Étape modifiée.' },
  priorite: { kind: 'lead_priorite', message: 'Priorité modifiée.' },
  tags: { kind: 'lead_tags', message: 'Étiquettes modifiées.' },
  relance_date: { kind: 'lead_relance', message: 'Relance modifiée.' },
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

// LB20 — option d'affichage « Plat / Par étape » + repli des groupes :
// persistés en localStorage, MÊME patron try/catch que VX240(e)
// (LeadExpressModal.jsx lireLastCanal/ecrireLastCanal) — jamais bloquant si
// localStorage est indisponible (navigation privée, quota).
const LIST_GROUP_KEY = 'taqinor.leads.listGroup'
const lireListGroup = () => {
  try { return localStorage.getItem(LIST_GROUP_KEY) === 'stage' ? 'stage' : 'plat' }
  catch { return 'plat' }
}
const ecrireListGroup = (v) => {
  try { localStorage.setItem(LIST_GROUP_KEY, v) }
  catch { /* localStorage indisponible : no-op */ }
}
const LIST_GROUP_COLLAPSED_KEY = 'taqinor.leads.listGroupCollapsed'
const lireGroupesReplies = () => {
  try {
    const parsed = JSON.parse(localStorage.getItem(LIST_GROUP_COLLAPSED_KEY) || '[]')
    return new Set(Array.isArray(parsed) ? parsed : [])
  } catch { return new Set() }
}
const ecrireGroupesReplies = (setValue) => {
  try { localStorage.setItem(LIST_GROUP_COLLAPSED_KEY, JSON.stringify([...setValue])) }
  catch { /* localStorage indisponible : no-op */ }
}

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
// LB6/LB21 — la ligne ne porte plus AUCUNE plomberie « ✗ Perdu » : tout l'état
// (lead ciblé, motif saisi, envoi en cours) vit dans le `PerduPopover` partagé,
// et la ligne ne reçoit que le callback stable `onMarkPerdu`. Taper un motif ne
// re-rend donc plus une seule ligne de la table (blueprint I4, bug #4).
const ListRow = memo(function ListRow({
  lead, checked, onToggleSelect, onOpenLead, armCallNudgeFor, onInlineSave,
  users, onReassign, onAutoQuote, canDelete, busy, onRestore, onArchive,
  onDelete, isMobile, onOpenInsights, today, hiddenCols = {},
  onMarkPerdu,
}) {
  const perdu = isPerdu(lead)
  const stars = PRIORITE_STARS[lead.priorite] ?? 1
  const tags = tagList(lead)
  const enRetard = lead.relance_date && lead.relance_date < today
  // LB21 — ligne ouvrable au clavier (recon-05 a11y #5 : onClick sur <tr>,
  // aucun tabIndex/role/onKeyDown). Enter/Espace ouvrent la fiche SEULEMENT
  // quand la touche vient de la ligne elle-même — JAMAIS d'un contrôle
  // interne (checkbox, select d'édition en place, lien tel:/wa, bouton
  // d'action…) : ces contrôles gèrent DÉJÀ leur propre activation clavier
  // native, un second déclenchement ouvrirait la fiche par-dessus.
  const onRowKeyDown = (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return
    if (e.target.closest('button, a, input, select, textarea, [role="button"]')) return
    e.preventDefault()
    onOpenLead(lead)
  }
  return (
    <tr
      className={`lv-row${perdu ? ' lv-row-perdu' : ''}${lead.is_archived ? ' lv-row-archived' : ''}${checked ? ' lv-row-selected' : ''}`}
      onClick={() => onOpenLead(lead)}
      tabIndex={0}
      onKeyDown={onRowKeyDown}
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
      {/* APX5 — LA VUE LA PLUS DENSE : UNE ligne par lead. La cellule Lead
          empilait jusqu'à 3 lignes (nom / société / icônes de contact, +1 si
          archivé) → 33-65 px par ligne. Elle devient une rangée : nom · société
          en clair, icônes tel/WhatsApp poussées à droite, « Archivé » condensé
          en pastille (le détail « par X le Y » vit dans son infobulle, il n'est
          pas perdu). La hauteur de ligne, elle, est pilotée par le MÊME système
          de densité que le reste de l'ERP (`--row-py`, index.css). */}
      <td data-label="Lead" className="lv-sticky-name">
        <div className="lv-lead-cell">
          {/* LB21 — le nom devient un vrai élément interactif sémantique
              (blueprint D4) : un <button> dédié, découvrable au clavier/AT
              indépendamment du reste de la ligne (stopPropagation évite le
              double déclenchement via le onClick de <tr>). */}
          <button
            type="button"
            className="lv-lead-name"
            onClick={(e) => { e.stopPropagation(); onOpenLead(lead) }}
          >
            {fullName(lead) || '—'}
            {perdu && <span className="lv-badge-perdu">Perdu</span>}
          </button>
          {lead.societe ? (
            <span className="lv-lead-societe" title={lead.societe}>{lead.societe}</span>
          ) : null}
          {/* VX243(a) — confiance au niveau du DOSSIER : QUI a archivé et QUAND
              (archived_by/at étaient capturés serveur mais jamais rendus).
              APX5 : condensé en pastille, le détail passe dans l'infobulle —
              l'information reste, elle ne prend plus une ligne entière. */}
          {lead.is_archived && (lead.archived_by_nom || lead.archived_at) && (
            <span
              className="lv-lead-archived-by"
              title={`Archivé${lead.archived_by_nom ? ` par ${lead.archived_by_nom}` : ''}${lead.archived_at ? ` le ${formatDate(lead.archived_at)}` : ''}`}
            >
              Archivé
            </span>
          )}
          {/* QX25 — repli tap-to-call mobile : la colonne Téléphone
              (m-hide) disparaît sous 768px, ces icônes compactes
              restent visibles dans la cellule Lead (jamais masquée).
              APX5 : poussées à DROITE de la cellule (marge auto par la
              feuille de style), plus empilées sous le nom. */}
          {(telHref(lead.telephone) || waHref(lead.whatsapp)) && (
            <span className="lv-lead-contact" onClick={(e) => e.stopPropagation()}>
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
          // Critique Fable LB #2 : « Signé » ouvre SigneDialog via la
          // sentinelle rejetée (LB3) — l'avaler ICI, sinon InlineEdit peint
          // un faux « Échec de l'enregistrement » rouge PERSISTANT sur un
          // chemin de succès (l'affichage suit déjà la prop, rien à annuler).
          onSave={(v) => onInlineSave(lead, 'stage', v).catch((e) => {
            if (!isSigneIntercept(e)) throw e
          })}
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
        {/* LB21(fold) — le mini-flux « Marquer perdu » vit dans le composant
            PARTAGÉ PerduPopover (LB15) : une seule implémentation carte+liste,
            état interne (motifs lazy, busy, rejet garde la popover ouverte). */}
        {!perdu && (
          <PerduPopover
            lead={lead}
            onMarkPerdu={onMarkPerdu}
            idPrefix="lv"
            align="start"
            trigger={(
              <IconButton label="Marquer perdu" variant="ghost" size="icon" className="size-8">
                ✗
              </IconButton>
            )}
          />
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
  const isMobile = useIsMobile(MOBILE_QUERY)
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
  // LB20 — hauteur RÉELLE du thead (mesurée, jamais devinée) : les rangées
  // de groupe (« Par étape ») restent collées SOUS le thead sticky, pas
  // dessus — `--lv-thead-h` posée sur .lv-wrap, consommée par .lv-group
  // (index.css). ResizeObserver (pas juste un effet au montage) : le thead
  // change de hauteur si le contenu de l'aide Score se déplie, etc.
  const theadRef = useRef(null)
  useEffect(() => {
    const theadEl = theadRef.current
    const wrapEl = wrapRef.current
    if (!theadEl || !wrapEl || typeof ResizeObserver === 'undefined') return
    const setH = () => wrapEl.style.setProperty('--lv-thead-h', `${theadEl.offsetHeight}px`)
    setH()
    const ro = new ResizeObserver(setH)
    ro.observe(theadEl)
    return () => ro.disconnect()
  }, [])
  // LB20 — « Plat / Par étape » : lu UNE FOIS au montage (localStorage),
  // toute bascule est aussitôt persistée.
  const [listGroup, setListGroup] = useState(lireListGroup)
  useEffect(() => { ecrireListGroup(listGroup) }, [listGroup])
  const [collapsedGroups, setCollapsedGroups] = useState(lireGroupesReplies)
  const toggleGroupCollapsed = useCallback((stageKey) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(stageKey)) next.delete(stageKey)
      else next.add(stageKey)
      ecrireGroupesReplies(next)
      return next
    })
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
  // LB21(fold) — l'état « Marquer perdu » (cible/motif/busy/motifs lazy) vit
  // désormais DANS le composant partagé PerduPopover (LB15) : plus aucune
  // plomberie parent, chaque ligne reste memo-stable (props primitives).

  // VX87 — nudge post-appel : armé au tap tel: (mémorise QUEL lead a été
  // appelé, une table n'a qu'un seul nudge visible à la fois — comme un
  // vendeur ne passe qu'un appel à la fois), proposé au retour dans l'onglet.
  // EZ2 — au BUREAU, un tap `tel:` ne masque jamais l'onglet : le hook arme
  // désormais AUSSI un retour de focus fenêtre et une temporisation, le premier
  // déclencheur gagnant. Rien à câbler ici — le comportement mobile est
  // strictement inchangé.
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
  /* EZ14 — adoptions n°3 à 6 : l'édition en place des champs RÉVERSIBLES gagne
     l'undo, d'un seul endroit. `onInlineSave(lead, champ, valeur)` est déjà le
     point de passage unique ; on l'enveloppe ici, donc AUCUNE cellule n'a à
     connaître l'undo, et une nouvelle colonne éditable ne peut pas l'oublier.

     Le registre est FERMÉ (lib/mutateWithUndo.js) : un champ absent de
     `CHAMPS_UNDO` (module, plus haut) s'enregistre EXACTEMENT comme avant, sans
     toast d'annulation. C'est volontaire — `facture_hiver` (un montant) et tout
     champ d'argent n'ont JAMAIS d'undo. */
  const inlineSaveAvecUndo = useCallback(async (lead, champ, valeur) => {
    if (!onInlineSave) return undefined
    const conf = CHAMPS_UNDO[champ]
    if (!conf) return onInlineSave(lead, champ, valeur)
    const precedent = lead?.[champ] ?? null
    // Enregistrer la MÊME valeur n'est pas une modification : pas de toast.
    if (precedent === valeur) return onInlineSave(lead, champ, valeur)
    await mutateWithUndo({
      kind: conf.kind,
      message: conf.message,
      apply: () => onInlineSave(lead, champ, valeur),
      revert: () => onInlineSave(lead, champ, precedent),
    })
    return undefined
  }, [onInlineSave])

  // EZ14 — adoption n°1/2 : archivage et restauration passent par l'util
  // unique. Le comportement VX95 est conservé À L'IDENTIQUE (appliqué tout de
  // suite, « Annuler » = l'action inverse) ; ce qui change, c'est qu'il n'y a
  // plus une variante locale du motif par site d'appel.
  const onArchive = useCallback(async (lead) => {
    setBusyId(lead.id)
    try {
      await mutateWithUndo({
        kind: 'lead_archive',
        message: 'Lead archivé.',
        apply: () => dispatch(archiveLead(lead.id)).unwrap(),
        revert: () => dispatch(restoreLead(lead.id)).unwrap(),
        errorMessage: "L'archivage a échoué — réessayez.",
      })
    } finally { setBusyId(null) }
  }, [dispatch])

  const onRestore = useCallback(async (lead) => {
    setBusyId(lead.id)
    try {
      await mutateWithUndo({
        kind: 'lead_archive',
        message: 'Lead restauré.',
        apply: () => dispatch(restoreLead(lead.id)).unwrap(),
        revert: () => dispatch(archiveLead(lead.id)).unwrap(),
        errorMessage: 'La restauration a échoué — réessayez.',
      })
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

  /* APX9 — PLAFOND DE RENDU (même principe que le kanban, taille adaptée).
     -------------------------------------------------------------------------
     `fetchLeads` charge toutes les pages en mémoire et cette vue montait
     CHAQUE ligne. Le plafond ne touche que le RENDU : « Charger plus » découpe
     plus loin dans le tableau DÉJÀ chargé — zéro appel réseau, zéro dépendance.
     Palier de 200 (contre 40 pour le kanban) : une ligne de tableau coûte bien
     moins qu'une carte, et la Liste EST la vue dense — la faire cliquer tous
     les 40 leads irait contre sa raison d'être. */
  const [limiteRendu, setLimiteRendu] = useState(LIST_RENDER_CAP)
  const chargerPlus = () => setLimiteRendu((n) => n + LIST_RENDER_CAP)
  // Un changement de tri/filtre/groupe repart du premier palier (sinon on
  // garderait « 400 lignes montées » sur une liste qui n'en a plus que 12).
  useEffect(() => { setLimiteRendu(LIST_RENDER_CAP) }, [sort, listGroup, leads])
  const rendus = useMemo(() => sorted.slice(0, limiteRendu), [sorted, limiteRendu])
  const restants = Math.max(0, sorted.length - limiteRendu)

  // La sélection « tout » porte sur les lignes RENDUES (on ne coche jamais ce
  // qui n'est pas à l'écran — même règle qu'avant, la liste rendue faisait
  // simplement la totalité).
  const visibleIds = rendus.map((l) => l.id)
  const allChecked = allVisibleSelected(selected, visibleIds)
  // LB19 — colonnes réellement rendues (modèle moins celles masquées par
  // l'utilisateur) : réutilisé par le <colgroup> ET le colSpan de l'état
  // vide, pour qu'ils restent TOUJOURS en phase.
  const visibleColumns = useMemo(
    () => LIST_COLUMNS.filter((c) => !hiddenCols[c.id]),
    [hiddenCols],
  )
  const emptyColSpan = (onToggleSelect ? 1 : 0) + visibleColumns.length

  // LB20 — mode « Par étape » : compteur + total MAD via groupLeadsByStage
  // (MÊME fonction que le kanban — les nombres ne divergent jamais entre
  // les deux vues), mais les LIGNES viennent d'un filtre sur `sorted` : le
  // tri actif de la liste s'applique DANS chaque groupe (groupLeadsByStage
  // re-trie par priorité/date en interne — bon pour ses propres `.leads`,
  // pas pour les nôtres).
  const groupedRows = useMemo(() => {
    if (listGroup !== 'stage') return null
    // APX9 — les COMPTEURS/TOTAUX de groupe restent ceux de `sorted` (totaux
    // RÉELS de l'étape) ; seules les LIGNES sont bornées par le plafond.
    return groupLeadsByStage(sorted).map((g) => ({
      ...g,
      leads: sorted.filter((l) => l.stage === g.key).slice(0, limiteRendu),
      restants: Math.max(0, sorted.filter((l) => l.stage === g.key).length - limiteRendu),
    }))
  }, [sorted, listGroup, limiteRendu])

  // LB20 — extrait pour être partagé entre le mode Plat (sorted.map) et le
  // mode Par étape (groupedRows[i].leads.map) : AUCUNE duplication du JSX
  // de ligne, `tr.lv-row` reste le même sélecteur dans les deux modes.
  const renderRow = (lead) => {
    // LB6/LB21 — toutes les props de la ligne sont des primitives ou des
    // callbacks stables : memo(ListRow) bail out pour les lignes que rien ne
    // concerne (aucun état « ✗ Perdu » ne transite plus par ici, bug #4).
    return (
      <ListRow
        key={lead.id}
        lead={lead}
        checked={selected.has(lead.id)}
        onToggleSelect={onToggleSelect}
        onOpenLead={onOpenLead}
        armCallNudgeFor={armCallNudgeFor}
        onInlineSave={inlineSaveAvecUndo}
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
        onMarkPerdu={onMarkPerdu}
        hiddenCols={hiddenCols}
      />
    )
  }

  return (
    <div className="lv-view">
      {/* LB19/LB20 — barre d'outils locale (Plat/Par étape + choix de
          colonnes) : HORS du scrolleur .lv-wrap pour rester visible
          pendant le défilement vertical de la table. */}
      <div className="lv-toolbar">
        <Segmented
          size="sm"
          options={[
            { value: 'plat', label: 'Plat' },
            { value: 'stage', label: 'Par étape' },
          ]}
          value={listGroup}
          onChange={setListGroup}
        />
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
        <thead ref={theadRef}>
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
          {!sorted.length && (
            <tr>
              <td colSpan={emptyColSpan} className="lv-empty">
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
          {/* Mode Plat (défaut) : les 100 % des tests/e2e existants passent
              par ce chemin — tr.lv-row/.ie-cell/select.ie-input inchangés. */}
          {!!sorted.length && listGroup !== 'stage' && rendus.map(renderRow)}
          {/* LB20 — mode « Par étape » : rangées de groupe collantes
              (tr.lv-group, sous le thead) au-dessus des lignes de CE
              groupe — repliables, ordre = l'ordre du funnel
              (groupLeadsByStage itère déjà PIPELINE_STAGES dans l'ordre). */}
          {!!sorted.length && listGroup === 'stage' && groupedRows.map((g) => (
            <Fragment key={g.key}>
              <tr className="lv-group">
                <td colSpan={emptyColSpan}>
                  <button
                    type="button"
                    className="lv-group-toggle"
                    aria-expanded={!collapsedGroups.has(g.key)}
                    onClick={() => toggleGroupCollapsed(g.key)}
                  >
                    <span className="lv-group-chevron" aria-hidden="true">
                      {collapsedGroups.has(g.key) ? '▸' : '▾'}
                    </span>
                    <StatusPill status={g.key} label={g.label} />
                    <span className="lv-group-count">{g.count}</span>
                    <span className="lv-group-total">{formatMAD(g.totalDevis)}</span>
                  </button>
                </td>
              </tr>
              {!collapsedGroups.has(g.key) && g.leads.map(renderRow)}
              {!collapsedGroups.has(g.key) && g.restants > 0 && (
                <tr className="lv-charger-plus-row">
                  <td colSpan={emptyColSpan}>
                    <button type="button" className="lv-charger-plus" onClick={chargerPlus}>
                      Charger plus ({g.restants} restant{g.restants > 1 ? 's' : ''})
                    </button>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
          {/* APX9 — mode Plat : le même palier, en pied de tableau. Le tableau
              est DÉJÀ chargé en mémoire — ce bouton ne déclenche aucun appel. */}
          {!!sorted.length && listGroup !== 'stage' && restants > 0 && (
            <tr className="lv-charger-plus-row">
              <td colSpan={emptyColSpan}>
                <button type="button" className="lv-charger-plus" onClick={chargerPlus}>
                  Charger plus ({restants} restant{restants > 1 ? 's' : ''})
                </button>
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
              // EZ1 — relance déjà posée transmise : affichée, jamais écrasée
              // en silence.
              relanceActuelle={nudgeLead.relance_date ?? null}
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
