import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Truck, ClipboardList, ArrowLeftRight, Undo2 } from 'lucide-react'
import { ModuleDashboard, ModuleHero } from '../../ui/module'
import { Button } from '../../ui'
import installationsApi from '../../api/installationsApi'
import { INVENTAIRE_ACCENT } from '../stock/inventaireAccent'

/* ============================================================================
   XSTK2 — Cockpit Logistique (`/logistique`).
   ----------------------------------------------------------------------------
   Synthèse : livraisons du jour, sessions de comptage ouvertes, demandes de
   transfert en attente. Chaque KPI ouvre l'écran correspondant. Lecture
   seule ; aucun coût de transport ni prix d'achat rendu ici.

   APX22 — le cockpit affichait TROIS chiffres nus sous un en-tête legacy,
   très en retrait de Pilotage Stock. Il devient une FILE D'OPÉRATIONS façon
   Odoo Inventory : identité de module (ModuleHero + accent de la famille
   inventaire), tuiles « N à traiter » qui mènent chacune à la liste FILTRÉE
   existante, et le même conteneur `ui-root` que les autres écrans de la
   famille (Magasin/Stock divergaient : `page` d'un côté, `ui-root` de
   l'autre). Aucun endpoint nouveau : ce sont les trois appels déjà faits ici.
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

  // APX22 — chaque tuile est une FILE D'ACTION : « N à traiter » + le lien vers
  // la liste déjà filtrée sur le même statut que le compteur (aucun filtre
  // inventé : `?statut=` est le paramètre que ces écrans lisent déjà).
  const stats = [
    {
      label: 'Livraisons à traiter',
      value: String(counts.livraisons),
      hint: 'Planifiées ou en transit aujourd’hui',
      icon: Truck,
      to: '/logistique/livraisons',
    },
    {
      label: 'Comptages à traiter',
      value: String(counts.sessions),
      hint: 'Sessions de comptage cyclique ouvertes',
      icon: ClipboardList,
      to: '/logistique/comptages',
    },
    {
      label: 'Transferts à traiter',
      value: String(counts.transferts),
      hint: 'Demandes en attente d’approbation',
      icon: ArrowLeftRight,
      to: '/logistique/transferts',
    },
  ]

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      <ModuleHero
        title="Logistique"
        subtitle="Livraisons, comptages cycliques et transferts inter-emplacements."
        accent={INVENTAIRE_ACCENT}
        actions={(
          <>
            <Button asChild variant="outline" size="sm">
              <Link to="/logistique/livraisons"><Truck /> Livraisons</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/logistique/comptages"><ClipboardList /> Comptages</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/logistique/transferts"><ArrowLeftRight /> Transferts</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/logistique/retours"><Undo2 /> Retours</Link>
            </Button>
          </>
        )}
      />
      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
        accent={INVENTAIRE_ACCENT}
      />
    </div>
  )
}
