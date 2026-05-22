import { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchProduits } from '../features/stock/store/stockSlice'
import { fetchClients } from '../features/crm/store/crmSlice'
import { fetchDevis, fetchFactures } from '../features/ventes/store/ventesSlice'

function KpiIcon({ color, children }) {
  return (
    <div style={{
      width: 46, height: 46, borderRadius: 12,
      background: color + '18',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none"
        stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </div>
  )
}

const STATUT_DEVIS = {
  brouillon: { label: 'Brouillon',  color: '#94a3b8' },
  envoye:    { label: 'Envoyé',     color: '#3b82f6' },
  accepte:   { label: 'Accepté',    color: '#10b981' },
  refuse:    { label: 'Refusé',     color: '#ef4444' },
  expire:    { label: 'Expiré',     color: '#f59e0b' },
}

export function Component() {
  const dispatch = useDispatch()
  const { produits } = useSelector((s) => s.stock)
  const { clients }  = useSelector((s) => s.crm)
  const { devis, factures } = useSelector((s) => s.ventes)

  useEffect(() => {
    dispatch(fetchProduits())
    dispatch(fetchClients())
    dispatch(fetchDevis())
    dispatch(fetchFactures())
  }, [dispatch])

  const devisAcceptes    = devis.filter(d => d.statut === 'accepte')
  const facturesEnRetard = factures.filter(f => f.statut === 'en_retard')
  const facturesEmises   = factures.filter(f => f.statut === 'emise')

  const kpis = [
    {
      label: 'Produits en stock', value: produits.length, color: '#3b82f6',
      icon: <>
        <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/>
        <polyline points="3.27 6.96 12 12.01 20.73 6.96"/>
        <line x1="12" y1="22.08" x2="12" y2="12"/>
      </>,
    },
    {
      label: 'Clients', value: clients.length, color: '#8b5cf6',
      icon: <>
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
        <circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </>,
    },
    {
      label: 'Devis acceptés', value: devisAcceptes.length, color: '#10b981',
      icon: <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <polyline points="9 15 11 17 15 13"/>
      </>,
    },
    {
      label: 'Factures émises', value: facturesEmises.length, color: '#f59e0b',
      icon: <>
        <rect x="5" y="2" width="14" height="20" rx="2"/>
        <line x1="9" y1="7" x2="15" y2="7"/>
        <line x1="9" y1="11" x2="15" y2="11"/>
        <line x1="9" y1="15" x2="12" y2="15"/>
      </>,
    },
    {
      label: 'Factures en retard', value: facturesEnRetard.length, color: '#ef4444',
      icon: <>
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </>,
    },
  ]

  return (
    <div style={{ padding: '1.5rem' }}>

      {/* Page title */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
          Tableau de bord
        </h2>
        <p style={{ margin: '3px 0 0', fontSize: '0.82rem', color: '#64748b' }}>
          Vue d'ensemble de votre activité
        </p>
      </div>

      {/* KPI cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        gap: '1rem',
        marginBottom: '1.25rem',
      }}>
        {kpis.map(kpi => (
          <div key={kpi.label} style={{
            background: '#ffffff',
            borderRadius: 14,
            padding: '1.1rem 1.2rem',
            boxShadow: '0 1px 3px rgba(0,0,0,0.07), 0 1px 2px rgba(0,0,0,0.04)',
            borderTop: `3px solid ${kpi.color}`,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            <KpiIcon color={kpi.color}>{kpi.icon}</KpiIcon>
            <div>
              <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#0f172a', lineHeight: 1 }}>
                {kpi.value}
              </div>
              <div style={{ fontSize: '0.77rem', color: '#64748b', marginTop: 5 }}>
                {kpi.label}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Bottom row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>

        {/* Chiffre d'affaires */}
        <div style={{
          background: '#ffffff', borderRadius: 14, padding: '1.25rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        }}>
          <h3 style={{ margin: '0 0 8px', fontSize: '0.92rem', fontWeight: 600, color: '#1e293b' }}>
            Chiffre d'affaires mensuel
          </h3>
          <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: 0 }}>
            Graphique disponible en Phase 4
          </p>
        </div>

        {/* Devis par statut */}
        <div style={{
          background: '#ffffff', borderRadius: 14, padding: '1.25rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.07)',
        }}>
          <h3 style={{ margin: '0 0 14px', fontSize: '0.92rem', fontWeight: 600, color: '#1e293b' }}>
            Devis par statut
          </h3>
          {devis.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {Object.entries(STATUT_DEVIS).map(([statut, { label, color }]) => {
                const count = devis.filter(d => d.statut === statut).length
                if (count === 0) return null
                const pct = Math.round((count / devis.length) * 100)
                return (
                  <div key={statut}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.81rem', marginBottom: 5 }}>
                      <span style={{ color: '#475569' }}>{label}</span>
                      <span style={{ fontWeight: 600, color }}>{count}</span>
                    </div>
                    <div style={{ height: 4, borderRadius: 2, background: '#f1f5f9' }}>
                      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 2, background: color, transition: 'width 0.4s ease' }}/>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <p style={{ color: '#94a3b8', fontSize: '0.82rem', margin: 0 }}>Aucun devis</p>
          )}
        </div>
      </div>

      {/* Factures en retard alert */}
      {facturesEnRetard.length > 0 && (
        <div style={{
          marginTop: '1rem',
          background: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: 12,
          padding: '1rem 1.25rem',
        }}>
          <h3 style={{
            margin: '0 0 8px', fontSize: '0.88rem', fontWeight: 600, color: '#b91c1c',
            display: 'flex', alignItems: 'center', gap: 7,
          }}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            Factures en retard ({facturesEnRetard.length})
          </h3>
          <ul style={{ margin: 0, padding: '0 0 0 1rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
            {facturesEnRetard.map(f => (
              <li key={f.id} style={{ fontSize: '0.83rem', color: '#b91c1c' }}>
                {f.reference} — {f.client_nom}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
