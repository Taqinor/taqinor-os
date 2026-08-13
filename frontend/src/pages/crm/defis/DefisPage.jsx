import { useEffect, useMemo, useState } from 'react'
import { Trophy, Medal, Award } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { ModuleHero } from '../../../ui/module'
import { Segmented, Spinner, EmptyState } from '../../../ui'

/* NTCRM24 — Leaderboard des défis d'équipe (NTCRM23) : classement en cartes
   avatar+score+rang, podium top-3, filtrable par défi actif. Visible de
   toute l'équipe (pas seulement le manager — la gamification suppose la
   visibilité). Le classement affiché correspond EXACTEMENT à l'endpoint
   `classement/` — aucun tri/calcul dupliqué côté front. */

const PODIUM_ICONS = { 1: Trophy, 2: Medal, 3: Award }
const PODIUM_COLORS = {
  1: 'text-amber-500', 2: 'text-slate-400', 3: 'text-amber-700',
}

function initiales(nom) {
  return (nom || '?').trim().slice(0, 2).toUpperCase()
}

export default function DefisPage() {
  const [defis, setDefis] = useState([])
  const [defiId, setDefiId] = useState(null)
  const [classement, setClassement] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingClassement, setLoadingClassement] = useState(false)

  useEffect(() => {
    let active = true
    crmApi.getDefis({ actif: true })
      .then((r) => {
        if (!active) return
        const results = r.data?.results ?? r.data ?? []
        setDefis(results)
        if (results.length > 0) setDefiId(results[0].id)
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!defiId) { setClassement([]); return }
    let active = true
    setLoadingClassement(true)
    crmApi.getDefiClassement(defiId)
      .then((r) => { if (active) setClassement(r.data ?? []) })
      .finally(() => { if (active) setLoadingClassement(false) })
    return () => { active = false }
  }, [defiId])

  const options = useMemo(
    () => defis.map((d) => ({ value: d.id, label: d.nom })),
    [defis],
  )

  const defiActif = defis.find((d) => d.id === defiId)
  const podium = classement.slice(0, 3)
  const reste = classement.slice(3)

  return (
    <div className="page">
      <ModuleHero
        title="Défis"
        subtitle="Classement d'équipe en temps réel"
        accent="var(--module-accent-azur)"
      />

      {loading ? (
        <Spinner />
      ) : defis.length === 0 ? (
        <EmptyState
          icon={Trophy}
          title="Aucun défi actif"
          description="Créez un défi depuis les Paramètres pour lancer un classement."
        />
      ) : (
        <div className="mt-4 space-y-4">
          <Segmented options={options} value={defiId} onChange={setDefiId} aria-label="Défi actif" />

          {defiActif?.recompense && (
            <p className="text-sm text-muted-foreground">🎁 {defiActif.recompense}</p>
          )}

          {loadingClassement ? (
            <Spinner />
          ) : classement.length === 0 ? (
            <EmptyState icon={Trophy} title="Aucun résultat pour l'instant" />
          ) : (
            <>
              <div
                className="grid grid-cols-1 gap-3 sm:grid-cols-3"
                data-testid="defis-podium"
              >
                {podium.map((entry) => {
                  const Icon = PODIUM_ICONS[entry.rang] ?? Trophy
                  return (
                    <div
                      key={entry.owner_id}
                      className="flex flex-col items-center gap-2 rounded-lg border border-border bg-card p-4 text-center animate-fade-in"
                    >
                      <Icon className={`h-8 w-8 ${PODIUM_COLORS[entry.rang] ?? ''}`} aria-hidden="true" />
                      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted font-semibold">
                        {initiales(entry.owner_nom)}
                      </div>
                      <span className="font-medium">{entry.owner_nom}</span>
                      <span className="text-sm text-muted-foreground">
                        #{entry.rang} — {entry.realise}
                      </span>
                    </div>
                  )
                })}
              </div>

              {reste.length > 0 && (
                <ul className="divide-y divide-border rounded-lg border border-border">
                  {reste.map((entry) => (
                    <li key={entry.owner_id} className="flex items-center justify-between px-3 py-2">
                      <span>#{entry.rang} {entry.owner_nom}</span>
                      <span className="tabular-nums text-muted-foreground">{entry.realise}</span>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
