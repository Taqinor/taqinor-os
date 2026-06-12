import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchDashboard } from '../features/reporting/store/reportingSlice'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

// ── Formatage monétaire DH ────────────────────────────────────────────────────
const dh = (v) =>
  new Intl.NumberFormat('fr-MA', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(v ?? 0) + ' DH'

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, icon, color, sub }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 14, padding: '1.25rem 1.5rem',
      boxShadow: '0 1px 4px rgba(0,0,0,0.07)', display: 'flex',
      alignItems: 'center', gap: '1rem',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: color + '18',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 22 }}>{icon}</span>
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, color: '#64748b', fontWeight: 500, marginBottom: 2 }}>
          {label}
        </div>
        <div style={{ fontSize: 22, fontWeight: 700, color: '#0f172a', lineHeight: 1.2 }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: 11.5, color: '#94a3b8', marginTop: 2 }}>{sub}</div>}
      </div>
    </div>
  )
}

// ── Section title ─────────────────────────────────────────────────────────────
function SectionTitle({ children }) {
  return (
    <h3 style={{
      fontWeight: 700, color: '#1e293b',
      margin: '0 0 0.75rem', textTransform: 'uppercase',
      letterSpacing: '0.06em', fontSize: 12,
    }}>
      {children}
    </h3>
  )
}

// ── Chart card ────────────────────────────────────────────────────────────────
function ChartCard({ title, children, minHeight = 260 }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 14, padding: '1.25rem 1.5rem',
      boxShadow: '0 1px 4px rgba(0,0,0,0.07)', minHeight,
    }}>
      <SectionTitle>{title}</SectionTitle>
      {children}
    </div>
  )
}

// ── Tooltip personnalisé DH ───────────────────────────────────────────────────
function TooltipDH({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#1e293b', color: '#f1f5f9', borderRadius: 8,
      padding: '8px 12px', fontSize: 13,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color ?? '#60a5fa' }}>
          {p.name ?? 'CA'} : {dh(p.value)}
        </div>
      ))}
    </div>
  )
}

// ── Barre de conversion ───────────────────────────────────────────────────────
function ConversionBar({ label, value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ marginBottom: '0.75rem' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 13, color: '#475569', marginBottom: 4,
      }}>
        <span>{label}</span>
        <span style={{ fontWeight: 600, color: '#0f172a' }}>{value} <span style={{ color: '#94a3b8', fontWeight: 400 }}>({pct}%)</span></span>
      </div>
      <div style={{ background: '#f1f5f9', borderRadius: 6, height: 8 }}>
        <div style={{
          width: pct + '%', height: '100%', borderRadius: 6,
          background: color, transition: 'width 0.6s ease',
        }} />
      </div>
    </div>
  )
}

// ── Page principale ───────────────────────────────────────────────────────────
export function Component() {
  const dispatch = useDispatch()
  const { data, loading, error } = useSelector((s) => s.reporting)

  useEffect(() => {
    dispatch(fetchDashboard())
  }, [dispatch])

  if (loading) {
    return (
      <div className="page">
        <div className="page-header"><h2>Reporting & Analytics</h2></div>
        <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem 0' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            border: '4px solid #e2e8f0', borderTopColor: '#3b82f6',
            animation: 'spin 0.8s linear infinite',
          }} />
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header"><h2>Reporting & Analytics</h2></div>
        <div className="page-error">{error}</div>
      </div>
    )
  }

  if (!data) return null

  const { kpis, ca_mensuel, top_produits, statuts_factures, conversion, stock_alerte, creances } = data

  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h2>Reporting & Analytics</h2>
        <button
          className="btn btn-sm btn-outline"
          onClick={() => dispatch(fetchDashboard())}
        >
          Actualiser
        </button>
      </div>

      {/* ── KPIs ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '1rem', marginBottom: '1.75rem',
      }}>
        <KpiCard
          label="CA encaissé"
          value={dh(kpis.ca_paye)}
          icon="💰"
          color="#22c55e"
          sub="Factures payées"
        />
        <KpiCard
          label="En attente de paiement"
          value={dh(kpis.ca_attente)}
          icon="⏳"
          color="#f59e0b"
          sub="Émises + en retard"
        />
        <KpiCard
          label="Clients actifs"
          value={kpis.nb_clients}
          icon="👥"
          color="#3b82f6"
          sub="Total base clients"
        />
        <KpiCard
          label="Valeur du stock"
          value={dh(kpis.valeur_stock)}
          icon="📦"
          color="#8b5cf6"
          sub="Prix vente × quantité"
        />
      </div>

      {/* ── Graphiques ligne 1 ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
        gap: '1rem', marginBottom: '1rem',
      }}>

        {/* CA mensuel */}
        <ChartCard title="CA mensuel (12 derniers mois)" minHeight={280}>
          {ca_mensuel.every(m => m.ca === 0) ? (
            <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', paddingTop: '3rem' }}>
              Aucune facture payée sur les 12 derniers mois.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={ca_mensuel} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="caGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="mois" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={(v) => v >= 1000 ? Math.round(v / 1000) + 'k' : v} />
                <Tooltip content={<TooltipDH />} />
                <Area
                  type="monotone" dataKey="ca" name="CA HT"
                  stroke="#3b82f6" strokeWidth={2.5}
                  fill="url(#caGradient)" dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Top produits */}
        <ChartCard title="Top 5 produits vendus (quantité)" minHeight={280}>
          {top_produits.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', paddingTop: '3rem' }}>
              Aucune vente enregistrée.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart
                data={top_produits}
                layout="vertical"
                margin={{ top: 4, right: 20, bottom: 0, left: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} />
                <YAxis
                  dataKey="nom" type="category"
                  tick={{ fontSize: 11, fill: '#475569' }}
                  width={100}
                />
                <Tooltip
                  formatter={(v) => [v + ' unités', 'Qté vendue']}
                  contentStyle={{ borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="qte" fill="#6366f1" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </ChartCard>
      </div>

      {/* ── Graphiques ligne 2 ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '1rem', marginBottom: '1rem',
      }}>

        {/* Statuts factures */}
        <ChartCard title="Répartition des factures" minHeight={260}>
          {statuts_factures.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: 13, textAlign: 'center', paddingTop: '3rem' }}>
              Aucune facture.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={statuts_factures}
                  cx="50%" cy="50%"
                  innerRadius={55} outerRadius={80}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {statuts_factures.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v, n) => [v, n]} contentStyle={{ borderRadius: 8, fontSize: 13 }} />
                <Legend iconType="circle" iconSize={10} wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </ChartCard>

        {/* Conversion */}
        <ChartCard title="Tunnel de conversion" minHeight={260}>
          <div style={{ paddingTop: '0.5rem' }}>
            <ConversionBar
              label="Devis créés"
              value={conversion.nb_devis}
              max={conversion.nb_devis}
              color="#3b82f6"
            />
            <ConversionBar
              label="Devis acceptés"
              value={conversion.nb_acceptes}
              max={conversion.nb_devis}
              color="#22c55e"
            />
            <ConversionBar
              label="Factures émises"
              value={conversion.nb_factures}
              max={conversion.nb_devis}
              color="#8b5cf6"
            />
            {conversion.nb_devis > 0 && (
              <div style={{
                marginTop: '1rem', padding: '0.6rem 0.85rem',
                background: '#f8fafc', borderRadius: 8,
                fontSize: 13, color: '#475569',
              }}>
                Taux de conversion global :{' '}
                <strong style={{ color: '#0f172a' }}>
                  {Math.round((conversion.nb_factures / conversion.nb_devis) * 100)}%
                </strong>
              </div>
            )}
          </div>
        </ChartCard>

        {/* Stock critique */}
        <ChartCard title={`Stock sous seuil d'alerte (${stock_alerte.length})`} minHeight={260}>
          {stock_alerte.length === 0 ? (
            <div style={{ textAlign: 'center', paddingTop: '2rem' }}>
              <span style={{ fontSize: 28 }}>✅</span>
              <p style={{ color: '#22c55e', fontSize: 13, marginTop: 8, fontWeight: 600 }}>
                Tous les stocks sont au-dessus du seuil.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {stock_alerte.map((p, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '0.45rem 0.6rem', borderRadius: 8,
                  background: p.quantite_stock <= 0 ? '#fef2f2' : '#fffbeb',
                  border: `1px solid ${p.quantite_stock <= 0 ? '#fecaca' : '#fde68a'}`,
                }}>
                  <span style={{ fontSize: 13, color: '#1e293b', fontWeight: 500, flex: 1, minWidth: 0 }}>
                    {p.nom}
                  </span>
                  <span style={{
                    fontSize: 12, fontWeight: 700,
                    color: p.quantite_stock <= 0 ? '#dc2626' : '#d97706',
                    marginLeft: 8,
                  }}>
                    {p.quantite_stock <= 0 ? 'Rupture' : `${p.quantite_stock} / ${p.seuil_alerte}`}
                  </span>
                </div>
              ))}
            </div>
          )}
        </ChartCard>
      </div>

      {/* ── Créances clients ── */}
      {creances.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <ChartCard title="Créances clients (factures impayées)" minHeight={0}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #f1f5f9' }}>
                    {['Client', 'Nb factures', 'Montant total', 'Retard max'].map(h => (
                      <th key={h} style={{
                        padding: '0.5rem 0.75rem', textAlign: 'left',
                        fontSize: 11, fontWeight: 700, color: '#64748b',
                        textTransform: 'uppercase', letterSpacing: '0.05em',
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {creances.map((c, i) => (
                    <tr key={i} style={{
                      borderBottom: '1px solid #f8fafc',
                      background: i % 2 === 0 ? '#fff' : '#fafafa',
                    }}>
                      <td style={{ padding: '0.55rem 0.75rem', fontWeight: 500, color: '#1e293b' }}>
                        {c.client}
                      </td>
                      <td style={{ padding: '0.55rem 0.75rem', color: '#475569' }}>
                        {c.nb_factures}
                      </td>
                      <td style={{ padding: '0.55rem 0.75rem', fontWeight: 600, color: '#dc2626' }}>
                        {dh(c.montant_total)}
                      </td>
                      <td style={{ padding: '0.55rem 0.75rem' }}>
                        {c.jours_retard_max > 0 ? (
                          <span style={{
                            background: '#fef2f2', color: '#dc2626',
                            borderRadius: 6, padding: '2px 8px', fontSize: 12, fontWeight: 600,
                          }}>
                            {c.jours_retard_max}j
                          </span>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ChartCard>
        </div>
      )}
    </div>
  )
}
