import { useEffect, useState } from 'react'
import { Users, UserCheck, CalendarClock, ShieldAlert, TrendingUp, FileWarning } from 'lucide-react'
import { ModuleDashboard, EcheanceCenter } from '../../ui/module'
import { BarArrondie } from '../../ui/charts'
import { toast } from '../../ui'
import { formatNumber, formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { ECHEANCE_TYPE_LABELS, TYPE_CONTRAT_LABELS } from './constants.jsx'

/* ============================================================================
   UX21 — Cockpit RH + centre d'échéances.
   ----------------------------------------------------------------------------
   Agrège trois lectures serveur : le cockpit RH (`/rh/cockpit/` — effectifs,
   répartitions, turnover, alertes), le moteur d'échéances unifié
   (`/rh/echeances/` — CDD/certifs/visites/EPI à expirer) et le tableau de bord
   HSE (`/rh/tableau-bord-hse/`). Aucune écriture. Réservé
   Responsable/Administrateur (gaté par la route).
   ========================================================================== */

export default function RhCockpit() {
  const [cockpit, setCockpit] = useState(null)
  const [echeances, setEcheances] = useState([])
  const [hse, setHse] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let vivant = true
    const charger = () => {
      setLoading(true)
      setError(null)
      Promise.all([
        rhApi.getCockpit(),
        rhApi.getEcheances({ within: 30 }),
        rhApi.getTableauBordHse({ within: 30 }),
      ])
        .then(([cRes, eRes, hRes]) => {
          if (!vivant) return
          setCockpit(cRes.data)
          setEcheances(Array.isArray(eRes.data) ? eRes.data : [])
          setHse(hRes.data)
        })
        .catch(() => {
          if (!vivant) return
          setError('Impossible de charger le cockpit RH.')
          toast.error('Impossible de charger le cockpit RH.')
        })
        .finally(() => { if (vivant) setLoading(false) })
    }
    charger()
    return () => { vivant = false }
  }, [])

  const alertes = cockpit?.alertes ?? {}
  const turnover = cockpit?.turnover ?? {}

  const stats = [
    {
      label: 'Effectif total',
      value: formatNumber(cockpit?.effectif_total ?? 0),
      hint: 'Employés non sortis',
      icon: Users,
      to: '/rh/employes',
    },
    {
      label: 'CDD à échéance',
      value: formatNumber(alertes.cdd_a_echeance ?? 0),
      hint: 'Fin de contrat sous 30 jours',
      icon: UserCheck,
      to: '/rh/employes',
    },
    {
      label: 'Visites médicales',
      value: formatNumber(alertes.visites_medicales_a_renouveler ?? 0),
      hint: 'À renouveler sous 30 jours',
      icon: CalendarClock,
      to: '/rh/competences',
    },
    {
      label: 'Turnover 12 mois',
      value: `${formatNumber(turnover.taux_pct ?? 0, { decimals: 1 })} %`,
      hint: `${turnover.entrees_12m ?? 0} entrées · ${turnover.sorties_12m ?? 0} sorties`,
      icon: TrendingUp,
    },
  ]

  // Répartition par type de contrat (bar chart).
  const parContrat = Object.entries(cockpit?.par_contrat ?? {}).map(
    ([code, n]) => ({ label: TYPE_CONTRAT_LABELS[code] ?? code, value: n }),
  )
  // Effectif par département.
  const parDepartement = (cockpit?.par_departement ?? []).map((d) => ({
    label: d.nom, value: d.effectif,
  }))

  const charts = [
    {
      title: 'Effectif par type de contrat',
      node: parContrat.length
        ? <BarArrondie data={parContrat} height={240} />
        : <p className="text-sm text-muted-foreground">Aucune donnée.</p>,
    },
    {
      title: 'Effectif par département',
      node: parDepartement.length
        ? <BarArrondie data={parDepartement} layout="horizontal" height={240} />
        : <p className="text-sm text-muted-foreground">Aucune donnée.</p>,
    },
  ]

  // Indicateurs HSE (bandeau secondaire, jamais bloquant).
  const hseStats = hse ? [
    {
      label: 'Accidents (30 j)',
      value: formatNumber(hse.accidents_total ?? hse.nb_accidents ?? 0),
      hint: 'Déclarés sur la période',
      icon: ShieldAlert,
      to: '/rh/hse',
    },
    {
      label: 'Presqu’accidents (30 j)',
      value: formatNumber(hse.presqu_accidents_total ?? hse.nb_presqu_accidents ?? 0),
      hint: 'Signalés sur la période',
      icon: FileWarning,
      to: '/rh/hse',
    },
    {
      label: 'Taux de fréquence',
      value: hse.taux_frequence != null
        ? formatNumber(hse.taux_frequence, { decimals: 2 }) : '—',
      hint: 'Accidents / heures travaillées',
    },
    {
      label: 'Taux de gravité',
      value: hse.taux_gravite != null
        ? formatNumber(hse.taux_gravite, { decimals: 2 }) : '—',
      hint: 'Jours perdus / heures travaillées',
    },
  ] : []

  // Transforme les échéances serveur en items du centre d'échéances.
  const echeanceItems = echeances.map((e, i) => ({
    id: `${e.type}-${e.employe_id}-${i}`,
    label: `${ECHEANCE_TYPE_LABELS[e.type] ?? e.type} — ${e.libelle}`,
    date: e.date_validite,
    daysLeft: e.jours_restants,
    meta: `${e.employe}${e.date_validite ? ` · ${formatDate(e.date_validite)}` : ''}`,
    to: '/rh/employes',
  }))

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h2>Cockpit RH</h2>
      </div>

      <ModuleDashboard
        stats={stats}
        charts={charts}
        loading={loading}
        error={error}
      />

      {!loading && !error && (
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="flex flex-col gap-6">
            {hseStats.length > 0 && (
              <ModuleDashboard stats={hseStats} />
            )}
          </div>
          <EcheanceCenter
            title="Échéances RH (30 jours)"
            items={echeanceItems}
            emptyText="Aucune échéance dans les 30 prochains jours."
            max={12}
          />
        </div>
      )}
    </div>
  )
}
