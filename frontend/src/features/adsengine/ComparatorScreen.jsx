import { useEffect, useState, useCallback, useMemo } from 'react'
import { Scale, Search } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { unwrapList } from '../../api/resource'
import { formatMAD, formatNumber, formatRatio } from './adsengine'

/* ============================================================================
   PUB52 — Comparateur côte-à-côte (« je coupe A ou B ? » sur un seul écran).
   ----------------------------------------------------------------------------
   Sélectionne 2-4 ADS (données du Cockpit, `metrics.adsCockpit()`) OU 2-4
   CAMPAGNES (données de l'écran Campagnes, `campaigns.list()`) et aligne
   leurs métriques en colonnes, avec l'écart mis en surbrillance (vert = la
   meilleure valeur de la ligne, rouge = la pire — jamais recalculé/inventé,
   uniquement les chiffres déjà renvoyés par l'API). Reachable depuis
   Reporting (bouton) et depuis le Cockpit (lien posé au point d'enregistrement
   de route, PrintPageWrapper) — jamais en éditant le corps de ces écrans.
   ========================================================================== */

const MAX_SELECTION = 4
const MIN_SELECTION = 2

// higherIsBetter : true = plus haut est mieux (vert en haut) ; false =
// plus bas est mieux (coûts) ; null = pas de comparaison numérique (texte).
const AD_METRICS = [
  { key: 'depense_mad', label: 'Dépense', fmt: 'mad', higherIsBetter: null },
  { key: 'nb_leads', label: 'Leads réels', fmt: 'num', higherIsBetter: true },
  { key: 'cpl_mad', label: 'Coût par lead', fmt: 'mad', higherIsBetter: false },
  { key: 'conversations', label: 'Conversations WhatsApp', fmt: 'num', higherIsBetter: true },
  { key: 'signatures', label: 'Signatures', fmt: 'num', higherIsBetter: true },
  { key: 'cost_per_signature_mad', label: 'Coût par signature', fmt: 'mad', higherIsBetter: false },
  { key: 'frequency', label: 'Fréquence', fmt: 'ratio', higherIsBetter: false },
  { key: 'statut_display', label: 'Statut', fmt: 'text', higherIsBetter: null },
]

const CAMPAIGN_METRICS = [
  { key: 'budget', label: 'Budget (unités mineures Meta)', fmt: 'num', higherIsBetter: null },
  { key: 'objective', label: 'Objectif', fmt: 'text', higherIsBetter: null },
  { key: 'status', label: 'Statut', fmt: 'text', higherIsBetter: null },
]

const SOURCES = [
  { key: 'ads', label: 'Ads (Cockpit)', metrics: AD_METRICS, nameField: 'nom' },
  { key: 'campaigns', label: 'Campagnes', metrics: CAMPAIGN_METRICS, nameField: 'name' },
]

function fmtValue(fmt, value) {
  if (value === null || value === undefined || value === '') return '—'
  if (fmt === 'mad') return formatMAD(value)
  if (fmt === 'num') return formatNumber(value)
  if (fmt === 'ratio') return formatRatio(value)
  return String(value)
}

// Meilleure/pire valeur NUMÉRIQUE d'une ligne parmi les entités sélectionnées
// (ignore null/undefined) — jamais recalculé, juste comparé.
function rowExtremes(metric, entities) {
  if (metric.higherIsBetter === null) return { best: null, worst: null }
  const nums = entities
    .map(e => Number(e[metric.key]))
    .filter(n => Number.isFinite(n))
  if (nums.length < 2) return { best: null, worst: null }
  const max = Math.max(...nums)
  const min = Math.min(...nums)
  if (max === min) return { best: null, worst: null }
  return metric.higherIsBetter
    ? { best: max, worst: min }
    : { best: min, worst: max }
}

export default function ComparatorScreen() {
  const [sourceKey, setSourceKey] = useState('ads')
  const [pool, setPool] = useState([])
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIds, setSelectedIds] = useState(() => new Set())

  const source = SOURCES.find(s => s.key === sourceKey)

  const load = useCallback((key) => {
    setLoading(true)
    setSelectedIds(new Set())
    const fetcher = key === 'campaigns'
      ? adsengineApi.campaigns.list()
      : adsengineApi.metrics.adsCockpit()
    fetcher
      .then(r => setPool(key === 'campaigns' ? unwrapList(r) : (Array.isArray(r.data) ? r.data : [])))
      .catch(() => setPool([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de source
  useEffect(() => { load(sourceKey) }, [sourceKey, load])

  const toggleSelect = (id) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else if (next.size < MAX_SELECTION) {
        next.add(id)
      }
      return next
    })
  }

  const q = query.trim().toLowerCase()
  const filteredPool = q
    ? pool.filter(e => (e[source.nameField] || '').toLowerCase().includes(q))
    : pool

  const selected = useMemo(
    () => pool.filter(e => selectedIds.has(e.id)),
    [pool, selectedIds])

  return (
    <div className="page ae-comparator">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Scale size={20} aria-hidden="true" /> Comparateur
        </h2>
      </div>

      <div role="group" aria-label="Type d'entité" style={{ display: 'flex', gap: '0.4rem', marginBottom: '1rem' }}>
        {SOURCES.map(s => (
          <button key={s.key} type="button" data-testid={`ae-comparator-source-${s.key}`}
            aria-pressed={sourceKey === s.key}
            className={`btn ${sourceKey === s.key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setSourceKey(s.key)}>
            {s.label}
          </button>
        ))}
      </div>

      <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
        Sélectionnez {MIN_SELECTION} à {MAX_SELECTION} {source.label.toLowerCase()} à comparer
        ({selected.length}/{MAX_SELECTION} sélectionnée{selected.length > 1 ? 's' : ''}).
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem' }}>
        <Search size={15} aria-hidden="true" />
        <input type="text" className="form-input" data-testid="ae-comparator-search"
          placeholder="Rechercher…" value={query}
          onChange={e => setQuery(e.target.value)}
          style={{ flex: 1, maxWidth: 360 }} />
      </div>

      {loading ? <p className="page-loading">Chargement…</p> : (
        <>
          {filteredPool.length === 0
            ? <p data-testid="ae-comparator-pool-empty" style={{ color: '#64748b' }}>Aucun élément.</p>
            : (
              <div data-testid="ae-comparator-pool" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '1.25rem' }}>
                {filteredPool.map(e => {
                  const isSelected = selectedIds.has(e.id)
                  const disabled = !isSelected && selected.length >= MAX_SELECTION
                  return (
                    <button key={e.id} type="button" data-testid={`ae-comparator-pick-${e.id}`}
                      disabled={disabled} onClick={() => toggleSelect(e.id)}
                      aria-pressed={isSelected}
                      className="btn"
                      style={{
                        background: isSelected ? '#2563eb' : '#f1f5f9',
                        color: isSelected ? '#fff' : '#334155',
                        opacity: disabled ? 0.5 : 1,
                        border: 'none', borderRadius: 999, padding: '0.35rem 0.8rem', fontSize: '0.85rem',
                      }}>
                      {e[source.nameField] || `#${e.id}`}
                    </button>
                  )
                })}
              </div>
            )}

          {selected.length < MIN_SELECTION
            ? <p data-testid="ae-comparator-need-more" style={{ color: '#64748b' }}>
                Sélectionnez au moins {MIN_SELECTION} {source.label.toLowerCase()} pour comparer.</p>
            : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" data-testid="ae-comparator-table">
                  <thead>
                    <tr>
                      <th>Métrique</th>
                      {selected.map(e => (
                        <th key={e.id} data-testid={`ae-comparator-col-${e.id}`}>
                          {e[source.nameField] || `#${e.id}`}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {source.metrics.map(metric => {
                      const { best, worst } = rowExtremes(metric, selected)
                      return (
                        <tr key={metric.key} data-testid={`ae-comparator-row-${metric.key}`}>
                          <td>{metric.label}</td>
                          {selected.map(e => {
                            const raw = e[metric.key]
                            const num = Number(raw)
                            const isBest = best !== null && Number.isFinite(num) && num === best
                            const isWorst = worst !== null && Number.isFinite(num) && num === worst
                            return (
                              <td key={e.id}
                                data-testid={isBest ? `ae-comparator-best-${metric.key}-${e.id}`
                                  : isWorst ? `ae-comparator-worst-${metric.key}-${e.id}` : undefined}
                                style={{
                                  background: isBest ? '#dcfce7' : isWorst ? '#fee2e2' : 'transparent',
                                  color: isBest ? '#166534' : isWorst ? '#991b1b' : 'inherit',
                                  fontWeight: (isBest || isWorst) ? 600 : 400,
                                }}>
                                {fmtValue(metric.fmt, raw)}
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
        </>
      )}
    </div>
  )
}
