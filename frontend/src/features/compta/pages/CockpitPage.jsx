import { useCallback, useEffect, useState } from 'react'
import {
  Wallet, TrendingUp, Landmark, Clock, Percent, Users,
} from 'lucide-react'
import { ModuleDashboard } from '../../../ui/module'
import { BarArrondie } from '../../../ui/charts'
import { toast } from '../../../ui'
import { formatMAD, formatNumber, formatPercent } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'

/* ============================================================================
   UX2 — Cockpit financier (GET /compta/pilotage/cockpit/).
   ----------------------------------------------------------------------------
   Lecture seule. Le selector renvoie : resultat_periode, chiffre_affaires,
   tresorerie, marge_brute(_pct), encours_clients/fournisseurs, dso, dpo,
   top_encours_clients[]. (Le backend n'expose PAS de série mensuelle sur 12
   mois ni de « créances en retard » — on rend donc les KPI réels + un top des
   encours clients, avec liens de drill-down vers les états.)
   ========================================================================== */

export default function CockpitPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    let alive = true
    setLoading(true)
    setError(null)
    comptaApi.cockpit()
      .then((res) => { if (alive) setData(res.data) })
      .catch(() => {
        if (!alive) return
        setError('Impossible de charger le cockpit financier.')
        toast.error('Impossible de charger le cockpit financier.')
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const d = data || {}
  const stats = [
    {
      label: 'Résultat de la période',
      value: formatMAD(d.resultat_periode),
      hint: "Produits − charges (CPC) de l'exercice en cours",
      icon: TrendingUp,
      to: '/comptabilite/etats',
    },
    {
      label: 'Trésorerie nette',
      value: formatMAD(d.tresorerie),
      hint: 'Solde net des comptes de classe 5',
      icon: Wallet,
      to: '/comptabilite/tresorerie',
    },
    {
      label: 'Marge brute',
      value: formatMAD(d.marge_brute),
      hint: `Taux : ${formatPercent(d.marge_brute_pct, { decimals: 1 })}`,
      icon: Percent,
    },
    {
      label: 'Chiffre d’affaires',
      value: formatMAD(d.chiffre_affaires),
      hint: 'Total des produits sur la période',
      icon: Landmark,
    },
    {
      label: 'DSO (encaissement client)',
      value: `${formatNumber(d.dso)} j`,
      hint: `Encours clients : ${formatMAD(d.encours_clients)}`,
      icon: Clock,
      to: '/comptabilite/etats',
    },
    {
      label: 'DPO (paiement fournisseur)',
      value: `${formatNumber(d.dpo)} j`,
      hint: `Encours fournisseurs : ${formatMAD(d.encours_fournisseurs)}`,
      icon: Clock,
    },
    {
      label: 'Créances clients',
      value: formatMAD(d.encours_clients),
      hint: 'Encours non lettré (compte 3421)',
      icon: Users,
      to: '/comptabilite/etats',
    },
    {
      label: 'Dettes fournisseurs',
      value: formatMAD(d.encours_fournisseurs),
      hint: 'Encours (compte 4411)',
      icon: Users,
    },
  ]

  // Top des encours clients (bar horizontal) — drill-down implicite vers états.
  const topEncours = (d.top_encours_clients || []).map((row) => ({
    label: row.tiers_id ? `Tiers #${row.tiers_id}` : 'Non affecté',
    value: Number(row.encours) || 0,
  }))

  const charts = topEncours.length > 0
    ? [{
        title: 'Top encours clients',
        span: 'full',
        node: (
          <BarArrondie
            data={topEncours}
            layout="vertical"
            height={Math.max(160, topEncours.length * 34)}
            tone="info"
            tooltipFormat={(v) => formatMAD(v)}
          />
        ),
      }]
    : []

  return (
    <div className="page">
      <div className="page-header">
        <h2>Cockpit financier</h2>
      </div>
      <ModuleDashboard
        stats={stats}
        charts={charts}
        loading={loading}
        error={error}
      />
    </div>
  )
}
