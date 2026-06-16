import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchEquipements } from '../../features/sav/store/equipementsSlice'
import savApi from '../../api/savApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import {
  EMPTY_EQUIP_FILTERS,
  EQUIP_STATUTS,
  EQUIP_STATUT_LABELS,
  GARANTIE_FILTRES,
  GARANTIE_ETATS,
  filterEquipements,
  sortEquipements,
  garantieLabel,
  garantieColor,
} from '../../features/sav/equipement'

const formatDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

function GarantieBadge({ eq }) {
  return (
    <span className="badge" style={{
      background: `${garantieColor(eq)}22`, color: garantieColor(eq),
      padding: '2px 8px', borderRadius: 6, fontSize: 12, whiteSpace: 'nowrap',
    }}>
      {garantieLabel(eq)}
    </span>
  )
}

function EquipementDetail({ equipement, onClose, onSaved }) {
  const [fields, setFields] = useState({
    numero_serie: equipement.numero_serie ?? '',
    date_pose: equipement.date_pose ?? '',
    statut: equipement.statut ?? 'en_service',
    note: equipement.note ?? '',
  })
  const set = (k, v) => setFields((f) => ({ ...f, [k]: v }))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const nullable = (v) => (v === '' || v === undefined ? null : v)
      await savApi.updateEquipement(equipement.id, {
        numero_serie: nullable(fields.numero_serie),
        date_pose: nullable(fields.date_pose),
        statut: fields.statut,
        note: nullable(fields.note),
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(JSON.stringify(err.response?.data ?? err.message))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Équipement — {equipement.produit_nom ?? ''}</h3>
          <button type="button" className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Produit</label>
              <input className="form-control" value={equipement.produit_nom ?? '—'} readOnly />
            </div>
            <div className="form-group">
              <label className="form-label">Marque</label>
              <input className="form-control" value={equipement.produit_marque ?? '—'} readOnly />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Chantier</label>
              <input className="form-control" value={equipement.installation_reference ?? '—'} readOnly />
            </div>
            <div className="form-group">
              <label className="form-label">Client</label>
              <input className="form-control" value={equipement.client_nom ?? '—'} readOnly />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group fg-grow">
              <label className="form-label">Numéro de série</label>
              <input className="form-control" value={fields.numero_serie}
                     onChange={(e) => set('numero_serie', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Date de pose</label>
              <input type="date" className="form-control" value={fields.date_pose ?? ''}
                     onChange={(e) => set('date_pose', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="form-label">Statut</label>
              <select className="form-select" value={fields.statut}
                      onChange={(e) => set('statut', e.target.value)}>
                {EQUIP_STATUTS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Garantie</label>
            <div><GarantieBadge eq={equipement} /></div>
            {equipement.date_fin_garantie_production && (
              <div className="form-hint">
                Garantie production jusqu'au {formatDateFR(equipement.date_fin_garantie_production)}
              </div>
            )}
            <div className="form-hint">
              La date de fin de garantie est recalculée automatiquement à partir
              de la durée du produit et de la date de pose.
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Note</label>
            <textarea className="form-control" rows={2} value={fields.note ?? ''}
                      onChange={(e) => set('note', e.target.value)} />
          </div>
          {error && <div className="form-error-box" role="alert">{error}</div>}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Fermer</button>
          <button type="button" className="btn btn-primary" disabled={saving} onClick={save}>
            {saving ? 'Enregistrement...' : 'Mettre à jour'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function EquipementsPage() {
  const dispatch = useDispatch()
  const { items, loading } = useSelector((s) => s.equipements)
  const [filters, setFilters] = useState(EMPTY_EQUIP_FILTERS)
  const [sort, setSort] = useState({ key: 'date_fin_garantie', dir: 'asc' })
  const [selected, setSelected] = useState(null)

  const reload = () => dispatch(fetchEquipements())
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const produitOptions = useMemo(() => {
    const seen = new Map()
    for (const it of items) if (it.produit && !seen.has(it.produit)) seen.set(it.produit, it.produit_nom)
    return [...seen.entries()].map(([id, nom]) => ({ id, nom: nom ?? `#${id}` }))
  }, [items])

  const marqueOptions = useMemo(
    () => [...new Set(items.map((it) => it.produit_marque).filter(Boolean))].sort(),
    [items])

  const rows = useMemo(
    () => sortEquipements(filterEquipements(items, filters), sort.key, sort.dir),
    [items, filters, sort])

  const onSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'asc' }))

  const arrow = (key) => (sort.key === key ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '')

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Parc d'équipements</h1>
        <div className="page-subtitle">{rows.length} équipement(s)</div>
        <button type="button" className="btn btn-sm btn-outline"
                onClick={() => importApi.exportList('equipements', rows.map(r => r.id))
                  .then(r => downloadXlsx(r.data, 'equipements.xlsx')).catch(() => {})}>
          ⬇ Exporter Excel
        </button>
      </div>

      {/* ── Filtres ── */}
      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (série, produit, chantier, client)…"
               value={filters.q} onChange={(e) => setF('q', e.target.value)}
               style={{ flex: '1 1 220px' }} />
        <select className="form-select" value={filters.produit} onChange={(e) => setF('produit', e.target.value)}>
          <option value="">Tous les produits</option>
          {produitOptions.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
        </select>
        <select className="form-select" value={filters.marque} onChange={(e) => setF('marque', e.target.value)}>
          <option value="">Toutes les marques</option>
          {marqueOptions.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select className="form-select" value={filters.garantie} onChange={(e) => setF('garantie', e.target.value)}>
          {GARANTIE_FILTRES.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
        </select>
        <button type="button"
                className={`btn btn-sm ${filters.garantie === 'expire_bientot' ? 'btn-warning' : 'btn-outline'}`}
                onClick={() => setF('garantie', filters.garantie === 'expire_bientot' ? '' : 'expire_bientot')}>
          ⏰ Expirant bientôt
        </button>
        {(filters.q || filters.produit || filters.marque || filters.garantie || filters.statut) && (
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => setFilters(EMPTY_EQUIP_FILTERS)}>Réinitialiser</button>
        )}
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">Aucun équipement. Ajoutez-en depuis la fiche d'un chantier.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th onClick={() => onSort('numero_serie')} style={{ cursor: 'pointer' }}>Série{arrow('numero_serie')}</th>
                <th onClick={() => onSort('produit_nom')} style={{ cursor: 'pointer' }}>Produit{arrow('produit_nom')}</th>
                <th className="m-hide">Marque</th>
                <th>Chantier</th>
                <th className="m-hide">Client</th>
                <th className="m-hide">Statut</th>
                <th onClick={() => onSort('date_fin_garantie')} style={{ cursor: 'pointer' }}>Garantie{arrow('date_fin_garantie')}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((eq) => (
                <tr key={eq.id} onClick={() => setSelected(eq)} style={{ cursor: 'pointer' }}>
                  <td>{eq.numero_serie ?? '—'}</td>
                  <td>{eq.produit_nom ?? '—'}</td>
                  <td className="m-hide">{eq.produit_marque ?? '—'}</td>
                  <td>{eq.installation_reference ?? '—'}</td>
                  <td className="m-hide">{eq.client_nom ?? '—'}</td>
                  <td className="m-hide">{EQUIP_STATUT_LABELS[eq.statut] ?? eq.statut}</td>
                  <td><GarantieBadge eq={eq} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Légende garantie */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 10 }}>
        {Object.entries(GARANTIE_ETATS).map(([k, v]) => (
          <span key={k} style={{ fontSize: 12, color: '#64748b' }}>
            <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 3,
                           background: v.color, marginRight: 4 }} />
            {v.label}
          </span>
        ))}
      </div>

      {selected && (
        <EquipementDetail equipement={selected} onClose={() => setSelected(null)}
                          onSaved={reload} />
      )}
    </div>
  )
}
