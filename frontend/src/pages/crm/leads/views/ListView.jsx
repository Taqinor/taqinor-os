// Vue LISTE des leads CRM — table dense et triable, façon Odoo.
// Les étapes viennent EXCLUSIVEMENT de features/crm/stages (miroir de
// STAGES.py) : aucune liste d'étapes n'est déclarée ici.
import { useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { archiveLead, restoreLead, deleteLead } from '../../../../features/crm/store/crmSlice'
import {
  PIPELINE_STAGES,
  STAGE_LABELS,
  STAGE_COLORS,
  CANAL_LABELS,
  PRIORITE_LABELS,
  PRIORITE_STARS,
  isPerdu,
  tagList,
  tagColor,
} from '../../../../features/crm/stages'
import AssigneePicker from '../../../../components/AssigneePicker'
import InlineEdit from '../../../../components/InlineEdit'
import { allVisibleSelected } from '../../../../features/crm/bulk'
import { Button, Checkbox } from '../../../../ui'
import './listview.css'

// Options des sélecteurs d'édition en place (libellés FR depuis stages.js).
const STAGE_OPTIONS = PIPELINE_STAGES.map((s) => ({ value: s, label: STAGE_LABELS[s] ?? s }))
const PRIORITE_OPTIONS = [
  { value: 'basse', label: PRIORITE_LABELS.basse },
  { value: 'normale', label: PRIORITE_LABELS.normale },
  { value: 'haute', label: PRIORITE_LABELS.haute },
]

// Fond de pastille d'étape : couleur de l'étape à ~14 % d'opacité.
const stageBg = (hex) => {
  const h = String(hex ?? '').replace('#', '')
  if (h.length !== 6) return 'rgba(100,116,139,0.14)'
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, 0.14)`
}

// Priorité : haute > normale > basse (ordre croissant = haute d'abord).
const PRIO_RANK = { haute: 0, normale: 1, basse: 2 }

const fullName = (l) => `${l.nom ?? ''} ${l.prenom ?? ''}`.trim()

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
}

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

function SortableTh({ col, label, sort, onSort, className }) {
  const active = sort.key === col
  return (
    <th className={className} aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="lv-th-btn" onClick={() => onSort(col)}>
        {label}
        <span className="lv-sort-ind" aria-hidden="true">
          {active ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
        </span>
      </button>
    </th>
  )
}

export default function ListView({
  leads, onOpenLead, onAutoQuote, onRefetch, users = [], onReassign,
  selected = new Set(), onToggleSelect, onToggleAll, onInlineSave,
}) {
  const dispatch = useDispatch()
  const role = useSelector((s) => s.auth.role)
  const canDelete = role === 'admin' // règle existante : destroy = admin
  // Par défaut : plus récents d'abord (date_creation desc), aucune colonne active.
  const [sort, setSort] = useState({ key: null, dir: 'asc' })
  const [busyId, setBusyId] = useState(null)
  const today = todayISO()

  const onArchive = async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(archiveLead(lead.id)).unwrap()
      onRefetch?.()
    } catch { /* erreur silencieuse */ } finally { setBusyId(null) }
  }

  const onRestore = async (lead) => {
    setBusyId(lead.id)
    try {
      await dispatch(restoreLead(lead.id)).unwrap()
      onRefetch?.()
    } catch { /* erreur silencieuse */ } finally { setBusyId(null) }
  }

  const onDelete = async (lead) => {
    if (!window.confirm('Supprimer définitivement ce lead ? Cette action est irréversible.')) return
    setBusyId(lead.id)
    try {
      await dispatch(deleteLead(lead.id)).unwrap()
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
      <table className="data-table lv-table">
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
            <SortableTh col="canal" label="Canal" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="owner" label="Responsable" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="priorite" label="Priorité" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="relance" label="Relance" sort={sort} onSort={onSort} />
            <th className="m-hide">Tags</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((lead) => {
            const perdu = isPerdu(lead)
            const stars = PRIORITE_STARS[lead.priorite] ?? 1
            const tags = tagList(lead)
            const enRetard = lead.relance_date && lead.relance_date < today
            return (
              <tr
                key={lead.id}
                className={`lv-row${perdu ? ' lv-row-perdu' : ''}${lead.is_archived ? ' lv-row-archived' : ''}${selected.has(lead.id) ? ' lv-row-selected' : ''}`}
                onClick={() => onOpenLead(lead)}
              >
                {onToggleSelect && (
                  <td
                    className="lv-check-col"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      aria-label={`Sélectionner ${fullName(lead) || 'ce lead'}`}
                      checked={selected.has(lead.id)}
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
                  </div>
                </td>
                <td data-label="Stade" onClick={(e) => e.stopPropagation()}>
                  <InlineEdit
                    value={lead.stage}
                    options={STAGE_OPTIONS}
                    disabled={!onInlineSave}
                    display={(
                      <span
                        className="lv-stage-badge"
                        style={{
                          background: stageBg(STAGE_COLORS[lead.stage]),
                          color: STAGE_COLORS[lead.stage] ?? '#475569',
                        }}
                      >
                        {STAGE_LABELS[lead.stage] ?? lead.stage}
                      </span>
                    )}
                    onSave={(v) => onInlineSave(lead, 'stage', v)}
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
                <td data-label="Actions">
                  <div className="actions-cell">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        onOpenLead(lead)
                      }}
                    >
                      Éditer
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      className="gen-btn-orange"
                      disabled={!lead.devis_auto?.pret}
                      title={lead.devis_auto?.pret
                        ? 'Devis auto'
                        : (lead.devis_auto?.message ?? 'Devis auto indisponible')}
                      onClick={(e) => {
                        e.stopPropagation()
                        onAutoQuote(lead)
                      }}
                    >
                      ⚡ Devis auto
                    </Button>
                    {lead.is_archived ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyId === lead.id}
                        onClick={(e) => {
                          e.stopPropagation()
                          onRestore(lead)
                        }}
                      >
                        Restaurer
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busyId === lead.id}
                        onClick={(e) => {
                          e.stopPropagation()
                          onArchive(lead)
                        }}
                      >
                        Archiver
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        type="button"
                        size="sm"
                        variant="destructive"
                        disabled={busyId === lead.id}
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(lead)
                        }}
                      >
                        Supprimer
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            )
          })}
          {!sorted.length && (
            <tr>
              <td colSpan={onToggleSelect ? 9 : 8} className="lv-empty">
                Aucun lead à afficher avec ces filtres.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
