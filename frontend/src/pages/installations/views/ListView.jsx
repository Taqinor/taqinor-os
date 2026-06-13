// Vue LISTE des chantiers — table dense et triable, façon Odoo.
// Le tri PAR DÉFAUT suit l'ordre d'entonnoir des statuts (jamais alphabétique),
// via sortInstallations() de features/installations/statuses.
import { useMemo, useState } from 'react'
import {
  statusLabel,
  statusColor,
  sortInstallations,
} from '../../../features/installations/statuses'

// Fond de pastille de statut : couleur du statut à ~14 % d'opacité.
const statusBg = (hex) => {
  const h = String(hex ?? '').replace('#', '')
  if (h.length !== 6) return 'rgba(100,116,139,0.14)'
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, 0.14)`
}

const formatDateFR = (iso) => {
  if (!iso) return '—'
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

export default function ListView({ items, onOpen }) {
  // Par défaut : tri par statut dans l'ordre de l'entonnoir.
  const [sort, setSort] = useState({ key: 'statut', dir: 'asc' })

  const onSort = (key) =>
    setSort((s) =>
      s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' },
    )

  const sorted = useMemo(
    () => sortInstallations(items, sort.key, sort.dir),
    [items, sort],
  )

  return (
    <div className="lv-wrap">
      <table className="data-table lv-table">
        <thead>
          <tr>
            <SortableTh col="reference" label="Référence" sort={sort} onSort={onSort} />
            <SortableTh col="client_nom" label="Client" sort={sort} onSort={onSort} />
            <SortableTh col="site_ville" label="Ville" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="statut" label="Statut" sort={sort} onSort={onSort} />
            <SortableTh col="type_installation" label="Type" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="technicien_nom" label="Technicien" sort={sort} onSort={onSort} className="m-hide" />
            <SortableTh col="date_pose_prevue" label="Pose prévue" sort={sort} onSort={onSort} />
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((it) => (
            <tr
              key={it.id}
              className={`lv-row${it.annule ? ' lv-row-perdu' : ''}`}
              onClick={() => onOpen(it)}
            >
              <td data-label="Référence">
                <strong>{it.reference ?? '—'}</strong>
              </td>
              <td data-label="Client">{it.client_nom ?? '—'}</td>
              <td className="m-hide">{it.site_ville ?? '—'}</td>
              <td data-label="Statut">
                <span
                  className="lv-stage-badge"
                  style={{
                    background: statusBg(statusColor(it.statut)),
                    color: statusColor(it.statut),
                  }}
                >
                  {statusLabel(it.statut)}
                </span>
                {it.annule && (
                  <span
                    className="lv-stage-badge"
                    style={{ background: 'rgba(100,116,139,0.14)', color: '#64748b', marginLeft: 6 }}
                  >
                    Annulé
                  </span>
                )}
              </td>
              <td className="m-hide">{it.type_installation_display ?? '—'}</td>
              <td className="m-hide">{it.technicien_nom ?? '—'}</td>
              <td data-label="Pose prévue">{formatDateFR(it.date_pose_prevue)}</td>
              <td data-label="Actions">
                <div className="actions-cell">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline"
                    onClick={(e) => {
                      e.stopPropagation()
                      onOpen(it)
                    }}
                  >
                    Voir
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {!sorted.length && (
            <tr>
              <td colSpan={8} className="lv-empty">
                Aucun chantier à afficher.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
