// Vue LISTE des leads CRM — table dense et triable, façon Odoo.
// Les étapes viennent EXCLUSIVEMENT de features/crm/stages (miroir de
// STAGES.py) : aucune liste d'étapes n'est déclarée ici.
import { useMemo, useState } from 'react'
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
  initials,
} from '../../../../features/crm/stages'
import './listview.css'

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

export default function ListView({ leads, onOpenLead, onAutoQuote }) {
  // Par défaut : plus récents d'abord (date_creation desc), aucune colonne active.
  const [sort, setSort] = useState({ key: null, dir: 'asc' })
  const today = todayISO()

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

  return (
    <div className="lv-wrap">
      <table className="data-table lv-table">
        <thead>
          <tr>
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
                className={perdu ? 'lv-row lv-row-perdu' : 'lv-row'}
                onClick={() => onOpenLead(lead)}
              >
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
                <td data-label="Stade">
                  <span
                    className="lv-stage-badge"
                    style={{
                      background: stageBg(STAGE_COLORS[lead.stage]),
                      color: STAGE_COLORS[lead.stage] ?? '#475569',
                    }}
                  >
                    {STAGE_LABELS[lead.stage] ?? lead.stage}
                  </span>
                </td>
                <td className="m-hide">{CANAL_LABELS[lead.canal] ?? '—'}</td>
                <td className="m-hide">
                  {lead.owner_nom ? (
                    <span className="lv-owner">
                      <span className="lv-avatar" aria-hidden="true">
                        {initials(lead.owner_nom)}
                      </span>
                      {lead.owner_nom}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="m-hide">
                  <span
                    className="lv-stars"
                    title={PRIORITE_LABELS[lead.priorite] ?? PRIORITE_LABELS.normale}
                  >
                    <span className={stars >= 1 ? 'lv-star lv-star-on' : 'lv-star'}>★</span>
                    <span className={stars >= 2 ? 'lv-star lv-star-on' : 'lv-star'}>★</span>
                  </span>
                </td>
                <td data-label="Relance">
                  {lead.relance_date ? (
                    <span className={enRetard ? 'lv-relance-late' : undefined}>
                      {formatDateFR(lead.relance_date)}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="m-hide">
                  {tags.length ? (
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
                  ) : (
                    '—'
                  )}
                </td>
                <td data-label="Actions">
                  <div className="actions-cell">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        onOpenLead(lead)
                      }}
                    >
                      Éditer
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm gen-btn-orange"
                      onClick={(e) => {
                        e.stopPropagation()
                        onAutoQuote(lead)
                      }}
                    >
                      ⚡ Devis auto
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
          {!sorted.length && (
            <tr>
              <td colSpan={8} className="lv-empty">
                Aucun lead à afficher.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
