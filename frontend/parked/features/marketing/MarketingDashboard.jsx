import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import marketingApi from '../../api/marketingApi'
import {
  campagnesActives, tauxOuvertureMoyen30j, leadsEngagesDuMois, roiCumulePct,
} from './marketingDashboard'

/* ============================================================================
   NTMKT1 — Tableau de bord marketing (page d'accueil du module, `/marketing`).
   ----------------------------------------------------------------------------
   4 KPI cards consommant les endpoints RÉELS `marketing/campagnes/` et
   `marketing/envois-campagne/` (+ l'action `roi` de campagnes, XMKT17) —
   AUCUNE valeur fabriquée, jamais de `Produit.prix_achat`/marge. Le sous-menu
   Marketing (9 écrans : Campagnes, Séquences, Segments, Listes, Événements,
   Enquêtes, Fidélité, Domaine d'envoi, Calendrier) est le `module.config.jsx`
   — cette page n'en fait pas partie (landing implicite).
   ========================================================================== */

const KPI_CARD_STYLE = {
  flex: '1 1 220px', border: '1px solid #e2e8f0', borderRadius: 10,
  padding: '1rem 1.1rem', background: '#fff',
}

export default function MarketingDashboard() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [kpi, setKpi] = useState({
    campagnesActives: 0, tauxOuverture: 0, leadsEngages: 0, roiPct: 0,
    roiDisponible: false,
  })

  const load = useCallback(() => {
    setLoading(true)
    setErr('')
    Promise.all([
      marketingApi.campagnes.list(),
      marketingApi.envoisCampagne.list(),
    ]).then(async ([campagnesRes, envoisRes]) => {
      const campagnes = marketingApi.unwrapList(campagnesRes)
      const envois = marketingApi.unwrapList(envoisRes)
      // ROI cumulé (XMKT17) — une requête par campagne ENVOYÉE (borné aux 20
      // plus récentes pour rester léger sur ce dashboard d'aperçu ; le détail
      // complet vit sur `CampagneDetail.jsx`, NTMKT2).
      const envoyees = campagnes
        .filter(c => c.statut === 'envoyee')
        .slice(0, 20)
      let roiEntries = []
      let roiDisponible = true
      if (envoyees.length) {
        try {
          const reponses = await Promise.all(
            envoyees.map(c => marketingApi.campagnes.roi(c.id)))
          roiEntries = reponses.map(r => r.data)
        } catch {
          roiDisponible = false
        }
      }
      setKpi({
        campagnesActives: campagnesActives(campagnes),
        tauxOuverture: tauxOuvertureMoyen30j(campagnes),
        leadsEngages: leadsEngagesDuMois(envois),
        roiPct: roiCumulePct(roiEntries),
        roiDisponible,
      })
    }).catch(() => setErr('Chargement du tableau de bord impossible.'))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const cards = [
    {
      key: 'campagnes-actives', label: 'Campagnes actives',
      value: kpi.campagnesActives, suffix: '',
      onClick: () => navigate('/marketing/campagnes'),
    },
    {
      key: 'taux-ouverture', label: "Taux d'ouverture moyen (30j)",
      value: kpi.tauxOuverture, suffix: '%',
    },
    {
      key: 'leads-engages', label: 'Leads engagés du mois',
      value: kpi.leadsEngages, suffix: '',
      hint: 'Ouverts ou cliqués ce mois-ci (proxy — score de maturité multi-signal à venir)',
    },
    {
      key: 'roi-cumule', label: 'ROI cumulé (XMKT17)',
      value: kpi.roiDisponible ? kpi.roiPct : null, suffix: '%',
      hint: 'Coût réel vs revenu signé attribué, campagnes envoyées récentes',
    },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Tableau de bord marketing</h2>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <div data-testid="mkt-dashboard-kpis"
            style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
            {cards.map(c => (
              <div key={c.key} data-testid={`mkt-kpi-${c.key}`}
                style={{
                  ...KPI_CARD_STYLE,
                  cursor: c.onClick ? 'pointer' : 'default',
                }}
                onClick={c.onClick}
                role={c.onClick ? 'button' : undefined}
                tabIndex={c.onClick ? 0 : undefined}>
                <div style={{ fontSize: '0.8rem', color: '#64748b' }}>{c.label}</div>
                <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#0d1b3e' }}>
                  {c.value === null ? '—' : `${c.value}${c.suffix}`}
                </div>
                {c.hint && (
                  <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: 2 }}>
                    {c.hint}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
    </div>
  )
}
