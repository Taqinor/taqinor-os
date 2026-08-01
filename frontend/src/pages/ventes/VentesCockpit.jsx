import { useEffect, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { Plus, ShoppingCart, CalendarClock } from 'lucide-react'
import { ModuleHero } from '../../ui/module'
import { Button } from '../../ui'
import { fetchDevis, fetchFactures } from '../../features/ventes/store/ventesSlice'
import { formatNumber, formatMAD } from '../../lib/format'

/* ============================================================================
   ODY16 — Cockpit Ventes : porte d'entrée de l'app (ModuleHero VX15 + actions
   rapides + KPI), premier item de `nav.items` (`/ventes/cockpit`) — la même
   convention que `nav.items[0].to` déjà lue ailleurs comme « cockpit du
   module » (VX9 AppLauncher, VX10 PinnedApps, VX46 préférence d'atterrissage,
   cf. `pages/preferences/prefs.js:resolveLandingPath`).
   ----------------------------------------------------------------------------
   Aucune écriture, aucun appel réseau dupliqué : compteurs dérivés des
   slices REDUX déjà chargées par DevisList/FactureList (même patron que
   Dashboard.jsx). Statuts DOCUMENT uniquement (brouillon/envoyé/accepté —
   règle #4) : AUCUNE clé du funnel STAGES.py (règle #2) n'est lue ici — les
   deux couches ne se mélangent jamais. La Facturation reste une SECTION de
   Ventes tant qu'ODX18 n'a pas livré `features/facturation/` (cf. le
   `navGroup: 'facturation'` posé sur les items concernés du module.config).
   ========================================================================== */
export default function VentesCockpit() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { devis, factures } = useSelector((s) => s.ventes)

  // VX55 — annule les requêtes en vol au démontage (même patron que DevisList/FactureList).
  useEffect(() => {
    const td = dispatch(fetchDevis())
    const tf = dispatch(fetchFactures())
    return () => { td?.abort?.(); tf?.abort?.() }
  }, [dispatch])

  const stats = useMemo(() => {
    const devisEnCours = (devis ?? []).filter(
      (d) => d.statut === 'brouillon' || d.statut === 'envoye',
    ).length
    const devisAcceptes = (devis ?? []).filter((d) => d.statut === 'accepte').length
    const impayees = (factures ?? []).filter(
      (f) => f.statut !== 'annulee' && f.statut !== 'brouillon' && Number(f.montant_du ?? 0) > 0,
    )
    const totalDu = impayees.reduce((sum, f) => sum + Number(f.montant_du ?? 0), 0)
    return [
      { label: 'Devis en cours', value: formatNumber(devisEnCours), to: '/ventes/devis' },
      { label: 'Devis acceptés', value: formatNumber(devisAcceptes), to: '/ventes/devis' },
      {
        label: 'Factures impayées',
        value: `${formatNumber(impayees.length)} · ${formatMAD(totalDu, { decimals: 0 })}`,
        to: '/ventes/factures',
      },
    ]
  }, [devis, factures])

  return (
    <div className="page">
      <ModuleHero
        title="Ventes"
        subtitle="Devis, bons de commande, facturation et relances"
        accent="var(--module-accent-brass)"
        actions={(
          <>
            <Button onClick={() => navigate('/ventes/devis/nouveau')}>
              <Plus /> Nouveau devis
            </Button>
            <Button variant="outline" onClick={() => navigate('/ventes/bons-commande')}>
              <ShoppingCart /> Bons de commande
            </Button>
            <Button variant="outline" onClick={() => navigate('/ventes/relances')}>
              <CalendarClock /> Relances
            </Button>
          </>
        )}
        kpiSlot={(
          <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3" data-testid="ventes-cockpit-stats">
            {stats.map((s) => (
              <button
                key={s.label}
                type="button"
                onClick={() => navigate(s.to)}
                className="rounded-lg border border-border bg-card p-3 text-left transition-colors hover:bg-muted"
              >
                <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {s.label}
                </span>
                <span className="font-display text-xl font-semibold tabular-nums">{s.value}</span>
              </button>
            ))}
          </div>
        )}
      />
    </div>
  )
}
