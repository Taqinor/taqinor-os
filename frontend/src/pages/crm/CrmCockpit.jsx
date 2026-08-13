import { useEffect, useMemo } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import { Users, UserPlus, Map as MapIcon } from 'lucide-react'
import { ModuleHero } from '../../ui/module'
import { Button } from '../../ui'
import { fetchClients, fetchLeads } from '../../features/crm/store/crmSlice'
import { formatNumber } from '../../lib/format'
import CrmInsightsPanel from './leads/CrmInsightsPanel'
import DormantAccountsWidget from './DormantAccountsWidget'

/* ============================================================================
   ODY15 — Cockpit CRM : porte d'entrée de l'app (ModuleHero VX15 + actions
   rapides + KPI), premier item de `nav.items` (`/crm/cockpit`) — la même
   convention que `nav.items[0].to` déjà lue ailleurs comme « cockpit du
   module » (VX9 AppLauncher, VX10 PinnedApps, VX46 préférence d'atterrissage,
   cf. `pages/preferences/prefs.js:resolveLandingPath`).
   ----------------------------------------------------------------------------
   Aucune écriture, aucun appel réseau dupliqué : les compteurs viennent des
   slices REDUX déjà chargées par les écrans CRM (clients/leads — même patron
   que `Dashboard.jsx`) et le détail KPI réutilise TEL QUEL le panneau
   d'insights existant (VX219/WR9, `leads/CrmInsightsPanel.jsx` — objectifs,
   ROI par source, SLA premier contact). Zéro deuxième implémentation, zéro
   registre d'apps local (ODY1 reste l'unique source « mes apps »).
   ========================================================================== */
export default function CrmCockpit() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { clients, leads } = useSelector((s) => s.crm)

  // VX55 — annule les requêtes en vol au démontage (même patron que
  // ClientList/LeadsPage) : une réponse tardive ne doit jamais écraser
  // l'état d'un autre écran après navigation.
  useEffect(() => {
    const tc = dispatch(fetchClients())
    const tl = dispatch(fetchLeads())
    return () => { tc?.abort?.(); tl?.abort?.() }
  }, [dispatch])

  // Compteurs légers, dérivés des mêmes champs que Dashboard.jsx
  // (`leadsChauds`) : is_archived/perdu, jamais un statut de pipeline
  // STAGES.py (règle #2) — aucune clé de stage n'est lue ici.
  const stats = useMemo(() => {
    const leadsActifs = (leads ?? []).filter((l) => l && !l.is_archived && !l.perdu).length
    return [
      { label: 'Clients', value: formatNumber((clients ?? []).length), to: '/crm' },
      { label: 'Leads actifs', value: formatNumber(leadsActifs), to: '/crm/leads' },
    ]
  }, [clients, leads])

  return (
    <div className="page">
      <ModuleHero
        title="CRM"
        subtitle="Pistes, clients, activités et carte commerciale"
        accent="var(--module-accent-azur)"
        actions={(
          <>
            <Button variant="outline" onClick={() => navigate('/crm/leads?new=1')}>
              <UserPlus /> Nouveau lead
            </Button>
            <Button variant="outline" onClick={() => navigate('/crm?new=1')}>
              <Users /> Nouveau client
            </Button>
            <Button variant="outline" onClick={() => navigate('/carte')}>
              <MapIcon /> Carte
            </Button>
          </>
        )}
        kpiSlot={(
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="crm-cockpit-stats">
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

      <div className="mt-2">
        <CrmInsightsPanel />
      </div>

      <div className="mt-4">
        <DormantAccountsWidget />
      </div>
    </div>
  )
}
