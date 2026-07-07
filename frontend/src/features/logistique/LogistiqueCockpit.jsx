import { useCallback, useEffect, useState } from 'react'
import { Truck, ClipboardList, ArrowLeftRight } from 'lucide-react'
import { ModuleDashboard } from '../../ui/module'
import PageHeader from '../../components/layout/PageHeader'
import installationsApi from '../../api/installationsApi'

/* ============================================================================
   XSTK2 — Cockpit Logistique (`/logistique`).
   ----------------------------------------------------------------------------
   Synthèse : livraisons du jour, sessions de comptage ouvertes, demandes de
   transfert en attente. Chaque KPI ouvre l'écran correspondant. Lecture
   seule ; aucun coût de transport ni prix d'achat rendu ici.
   ========================================================================== */

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

export default function LogistiqueCockpit() {
  const [counts, setCounts] = useState({ livraisons: 0, sessions: 0, transferts: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    Promise.all([
      installationsApi.getLivraisons({ date_prevue: todayIso() }),
      installationsApi.getSessionsComptage({ statut: 'en_cours' }),
      installationsApi.getDemandesTransfert({ statut: 'demande' }),
    ])
      .then(([liv, ses, tr]) => {
        if (cancelled) return
        const len = (r) => (r.data?.results ?? r.data ?? []).length
        setCounts({ livraisons: len(liv), sessions: len(ses), transferts: len(tr) })
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Tableau de bord indisponible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const stats = [
    {
      label: 'Livraisons du jour',
      value: String(counts.livraisons),
      hint: 'Planifiées/en transit aujourd’hui',
      icon: Truck,
      to: '/logistique/livraisons',
    },
    {
      label: 'Comptages en cours',
      value: String(counts.sessions),
      hint: 'Sessions de comptage cyclique ouvertes',
      icon: ClipboardList,
      to: '/logistique/comptages',
    },
    {
      label: 'Transferts en attente',
      value: String(counts.transferts),
      hint: 'Demandes à approuver',
      icon: ArrowLeftRight,
      to: '/logistique/transferts',
    },
  ]

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Cockpit logistique"
        subtitle="Livraisons, comptages cycliques et transferts inter-emplacements."
      />
      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
      />
    </div>
  )
}
