import { useNavigate } from 'react-router-dom'
import { Truck, Gauge, Wrench, ShieldCheck, Fuel, LineChart } from 'lucide-react'
import { ModuleDashboard, EcheanceCenter } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import flotteApi from '../../api/flotteApi'
import useResource from '../../hooks/useResource'
import { formatMAD, formatNumber } from '../../lib/format'
import { alertesToEcheanceItems } from './flotte'

/* ============================================================================
   UX15 — Cockpit Flotte (`/flotte`).
   ----------------------------------------------------------------------------
   Synthèse société (FLOTTE35) : 4 KPI (coût/km moyen, taux d'utilisation,
   immobilisation, conformité entretien) + bandeau d'alertes d'échéances via
   l'`EcheanceCenter` (FLOTTE24). Chaque KPI ouvre la liste filtrée. Lecture
   seule ; aucun prix d'achat ni marge rendu (chiffres d'exploitation internes).
   ========================================================================== */

export default function FlotteCockpit() {
  const navigate = useNavigate()

  // ARC45 — fetch/état mutualisé (data/loading/error/refetch, abort au démontage).
  const { data, loading, error } = useResource(
    () => Promise.all([flotteApi.tableauBord(), flotteApi.alertesEcheances()]),
    undefined,
    {
      initialData: { board: null, alertes: [] },
      select: ([bd, al]) => ({
        board: bd?.data ?? null,
        alertes: al?.data?.alertes ?? [],
      }),
      errorMessage: (err) =>
        err?.response?.data?.detail || 'Tableau de bord indisponible.',
    },
  )
  const { board, alertes } = data

  const veh = board?.vehicules ?? {}
  const total = veh.total ?? 0
  const disponibles = veh.disponibles ?? 0
  const enMaintenance = veh.par_statut?.maintenance ?? 0
  const couts = board?.couts ?? {}
  const echeances = board?.echeances ?? {}
  const entretien = board?.entretien ?? {}

  // Taux d'utilisation ≈ part du parc actif (disponible) sur le total.
  const tauxUtil = total > 0 ? Math.round((disponibles / total) * 100) : null
  // Immobilisation non planifiée ≈ véhicules en maintenance.
  const immob = enMaintenance
  // Coût d'exploitation total (réparations + carburant) — indicateur interne.
  const coutExploitation = Number(couts.reparations_total ?? 0)
    + Number(couts.carburant_total ?? 0)

  const stats = [
    {
      label: 'Coût d’exploitation',
      value: formatMAD(coutExploitation, { decimals: 0 }),
      hint: 'Réparations + carburant (interne)',
      icon: Fuel,
      to: '/flotte/carburant',
    },
    {
      label: 'Taux d’utilisation',
      value: tauxUtil == null ? '—' : `${tauxUtil} %`,
      hint: `${disponibles} / ${total} véhicules actifs`,
      icon: Gauge,
      to: '/flotte/vehicules',
    },
    {
      label: 'Immobilisation',
      value: formatNumber(immob),
      hint: 'Véhicules en maintenance',
      icon: Truck,
      to: '/flotte/entretien',
    },
    {
      label: 'Entretien dû',
      value: formatNumber(entretien.echeances_ouvertes ?? 0),
      hint: 'Échéances d’entretien ouvertes',
      icon: Wrench,
      to: '/flotte/entretien',
    },
    {
      // XFLT7/15/18 — accès direct au pivot des coûts, remplacement, budget.
      label: 'Analyse des coûts',
      value: '→',
      hint: 'Pivot, remplacement & budget vs réalisé',
      icon: LineChart,
      to: '/flotte/analyse-couts',
    },
  ]

  const items = alertesToEcheanceItems(alertes)

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Cockpit flotte"
        subtitle="Disponibilité, coûts d’exploitation et échéances du parc."
      />

      <ModuleDashboard stats={stats} loading={loading} error={error} />

      {!loading && !error && (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="flex flex-col gap-4">
            <ConformiteBand echeances={echeances} onGo={() => navigate('/flotte/conformite')} />
          </div>
          <EcheanceCenter
            title="Alertes d’échéances"
            items={items}
            max={12}
            emptyText="Aucune échéance dans les 30 prochains jours."
          />
        </div>
      )}
    </div>
  )
}

/* Bandeau « conformité » : rappel chiffré des seaux d'urgence réglementaire. */
function ConformiteBand({ echeances, onGo }) {
  const buckets = [
    { key: 'echu', label: 'Échu', tone: 'text-destructive' },
    { key: 'j7', label: 'J-7', tone: 'text-destructive' },
    { key: 'j15', label: 'J-15', tone: 'text-warning' },
    { key: 'j30', label: 'J-30', tone: 'text-warning' },
  ]
  return (
    <button
      type="button"
      onClick={onGo}
      className="rounded-xl border border-border bg-card p-4 text-left transition-shadow hover:ring-2 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:p-5"
    >
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" />
        <h3 className="font-display text-base font-semibold tracking-tight">
          Conformité réglementaire
        </h3>
      </div>
      <div className="grid grid-cols-4 gap-3">
        {buckets.map((b) => (
          <div key={b.key} className="text-center">
            <div className={`font-display text-2xl font-semibold tabular-nums ${b.tone}`}>
              {echeances[b.key] ?? 0}
            </div>
            <div className="text-xs text-muted-foreground">{b.label}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        {echeances.total ?? 0} échéance(s) à surveiller — ouvrir le centre de conformité.
      </p>
    </button>
  )
}
