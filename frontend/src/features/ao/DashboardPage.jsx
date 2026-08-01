import { useMemo } from 'react'
import { Briefcase, Trophy, Wallet, Layers, Gauge } from 'lucide-react'
import aoApi from '../../api/aoApi'
import useResource from '../../hooks/useResource'
import { ModuleDashboard, EcheanceCenter } from '../../ui/module'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   AOF172 — Tableau de bord AO + centre d'échéances.
   ----------------------------------------------------------------------------
   `ModuleDashboard` + `EcheanceCenter` alimentés par l'appel agrégé UNIQUE
   d'AOF166 (`GET /ao/tableau-marches/` — nom d'endpoint et selector repris
   nominativement de NTMAR27, cf. `docs/plans/PLAN_FINANCE.md:660`, pour
   éviter deux tableaux de bord AO concurrents) : AO en cours, taux de
   réussite (calculé côté serveur depuis `ResultatAO`, jamais saisi),
   cautions immobilisées, marchés en exécution, capacité vs engagement,
   échéances dues. AUCUN calcul de KPI côté front — chaque stat est une
   LECTURE directe du payload agrégé (au plus un arrondi d'affichage).
   `EcheanceCenter` porte lui-même les seuils d'urgence (`ui/module/urgency.js`
   — daysUntil/urgencyLevel/urgencyTone/urgencyLabel/compareUrgency) : ce
   fichier ne définit AUCUNE constante de seuil locale.
   ========================================================================== */

export default function DashboardPage() {
  const { data, loading, error } = useResource(
    () => aoApi.tableauMarches(),
    undefined,
    {
      select: (res) => res.data,
      errorMessage: 'Impossible de charger le tableau de bord.',
    },
  )

  const stats = useMemo(() => {
    if (!data) return []
    return [
      {
        label: 'AO en cours', icon: Briefcase,
        value: data.ao_en_cours ?? 0, to: '/ao/affaires',
      },
      {
        label: 'Taux de réussite', icon: Trophy,
        value: data.taux_reussite != null ? `${Math.round(data.taux_reussite)} %` : '—',
      },
      {
        label: 'Cautions immobilisées', icon: Wallet,
        value: data.cautions_immobilisees != null ? formatMAD(data.cautions_immobilisees) : '—',
      },
      {
        label: 'Marchés en exécution', icon: Layers,
        value: data.marches_en_execution ?? 0,
      },
      {
        label: 'Capacité vs engagement', icon: Gauge,
        value: data.capacite_vs_engagement ?? '—',
      },
    ]
  }, [data])

  // Même appel agrégé : les échéances dues voyagent dans LE MÊME payload
  // (jamais une seconde requête réseau pour le centre d'échéances).
  const echeances = useMemo(() => (data?.echeances_dues ?? []).map((e) => ({
    id: e.id,
    label: e.libelle,
    date: e.date_echeance,
    meta: e.affaire_reference,
    to: e.affaire_id ? `/ao/affaires/${e.affaire_id}` : undefined,
  })), [data])

  return (
    <div className="flex flex-col gap-6">
      <ModuleDashboard stats={stats} loading={loading} error={error} accent="var(--module-accent-brass)" />
      <EcheanceCenter title="Échéances AO" items={echeances} loading={loading} error={error} />
    </div>
  )
}
