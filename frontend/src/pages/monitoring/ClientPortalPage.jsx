import { useEffect, useMemo, useState } from 'react'
import { Coins, Leaf, Sun, Zap } from 'lucide-react'
import crmApi from '../../api/crmApi'
import monitoringApi from '../../api/monitoringApi'
import {
  EmptyState, Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Spinner,
} from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { formatMAD, formatNumber } from '../../lib/format'
import MonitoringNav from './MonitoringNav'

/* WR7 — Portail environnemental client (FG288). Synthèse CUMULÉE des systèmes
   d'un client : production / économies / CO₂ évité, depuis
   GET /monitoring/configs/client-portal/?client=ID. Rend STRICTEMENT ce que
   renvoie le backend (payload orienté client — aucune donnée interne : ni prix
   d'achat, ni marge). */

export default function ClientPortalPage() {
  const [clients, setClients] = useState([])
  const [loadingClients, setLoadingClients] = useState(true)
  const [clientId, setClientId] = useState('')

  const [portal, setPortal] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    crmApi.getClients({ page: 1 })
      .then((r) => { if (active) setClients(r.data.results ?? r.data ?? []) })
      .catch(() => { if (active) setClients([]) })
      .finally(() => { if (active) setLoadingClients(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!clientId) return undefined
    let active = true
    const load = async () => {
      await Promise.resolve()
      if (!active) return
      setLoading(true)
      try {
        const r = await monitoringApi.getClientPortal(clientId)
        if (active) { setPortal(r.data); setError(null) }
      } catch {
        if (active) setError('Impossible de charger le portail client.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [clientId])

  const stats = useMemo(() => (portal ? [
    {
      label: 'Systèmes',
      value: formatNumber(portal.systems_count),
      icon: Sun,
    },
    {
      label: 'Production cumulée',
      value: `${formatNumber(portal.total_production_kwh, { decimals: 0 })} kWh`,
      icon: Zap,
    },
    {
      label: 'Économies estimées',
      value: formatMAD(portal.economies_mad),
      icon: Coins,
      hint: `${formatNumber(portal.tarif_mad_par_kwh, { decimals: 2 })} MAD/kWh`,
    },
    {
      label: 'CO₂ évité',
      value: `${formatNumber(portal.co2_tonnes, { decimals: 3 })} t`,
      icon: Leaf,
      hint: `${formatNumber(portal.co2_kg, { decimals: 0 })} kg`,
    },
  ] : []), [portal])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Portail client</h1>
        <div className="page-subtitle">
          Synthèse environnementale cumulée des systèmes d’un client : production, économies, CO₂ évité.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 min-w-[18rem]">
        {loadingClients ? (
          <p className="flex items-center gap-2 py-2 text-sm text-muted-foreground"><Spinner /> Chargement des clients…</p>
        ) : (
          <Select value={clientId} onValueChange={setClientId} aria-label="Choisir un client">
            <SelectTrigger aria-label="Choisir un client"><SelectValue placeholder="Choisir un client…" /></SelectTrigger>
            <SelectContent>
              {clients.map((c) => (
                <SelectItem key={c.id} value={String(c.id)}>
                  {c.nom || c.raison_sociale || `Client #${c.id}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {!loadingClients && clients.length === 0 ? (
        <EmptyState
          title="Aucun client"
          description="Aucun client à afficher."
          className="my-6"
        />
      ) : !clientId ? (
        <EmptyState
          title="Choisissez un client"
          description="Sélectionnez un client pour voir sa synthèse environnementale."
          className="my-6"
        />
      ) : (
        <ModuleDashboard stats={stats} loading={loading} error={error} />
      )}
    </div>
  )
}
