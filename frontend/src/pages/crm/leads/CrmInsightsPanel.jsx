import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Target, TrendingUp, AlarmClock, Gauge, Flame } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Badge, Spinner,
} from '../../../ui'
import { formatMAD, formatNumber, formatPercent } from '../../../lib/format'
import ScoreBadge from '../../../features/crm/ScoreBadge'

// WR9 — surfaces consultatives du pipeline (lecture seule) :
//  - FG39 : atteinte des objectifs commerciaux (réalisé vs cible) ;
//  - FG34 : ROI par canal / campagne UTM ;
//  - FG28 : leads NEW non contactés au-delà du SLA société.
// Les règles vivent côté serveur ; ce panneau ne fait qu'afficher.

// LB30 — cache SESSION en mémoire, TTL 60s (même motif que
// `features/crm/workspace/leadPrefetch.js`), invalidé au changement de
// company : sans lui, basculer graphique→kanban→graphique re-fetchait les 3
// endpoints à CHAQUE fois (`CrmInsightsPanel` démonte entièrement avec
// `ChartsView` — LeadsPage ne rend qu'une seule vue à la fois, cf.
// `{view === 'graphique' && <ChartsView .../>}`). Ce cache n'est JAMAIS une
// source de vérité : un remontage au-delà du TTL refait les 3 appels comme
// avant.
const INSIGHTS_TTL_MS = 60_000
// { companyId, at, attainment, roi, sla, errors, pAttainment, pRoi, pSla } —
// l'entrée porte AUSSI ses 3 promesses en vol (critique Fable LB #5) : un
// remontage PENDANT le vol s'abonne aux promesses au lieu de lire des champs
// encore null et de croire le cache « déjà chargé » (spinner infini sinon).
let insightsCache = null

// loadInsights — retourne l'entrée fraîche du cache ou en crée UNE (les 3
// appels partent une seule fois) ; les promesses ne rejettent jamais (les
// erreurs deviennent des champs `errors.*` + valeur vide, comme avant).
function loadInsights(companyId) {
  const existing = readInsightsCache(companyId)
  if (existing) return existing
  const entry = {
    companyId, at: Date.now(), attainment: null, roi: null, sla: null, errors: {},
  }
  entry.pAttainment = crmApi.getObjectifsAttainment()
    .then((r) => { entry.attainment = r.data ?? [] })
    .catch(() => { entry.attainment = []; entry.errors.attainment = true })
  entry.pRoi = crmApi.getRoiSources()
    .then((r) => { entry.roi = r.data ?? [] })
    .catch(() => { entry.roi = []; entry.errors.roi = true })
  entry.pSla = crmApi.getSlaBreach()
    .then((r) => { entry.sla = r.data ?? { count: 0, results: [] } })
    .catch(() => { entry.sla = { count: 0, results: [] }; entry.errors.sla = true })
  insightsCache = entry
  return entry
}

function readInsightsCache(companyId) {
  if (!insightsCache || insightsCache.companyId !== companyId) return null
  if (Date.now() - insightsCache.at > INSIGHTS_TTL_MS) return null
  return insightsCache
}

/** resetInsightsCache — vide le cache (tests uniquement, même convention que
 * `resetPrefetchCache`). */
// eslint-disable-next-line react-refresh/only-export-components -- utilitaire de test co-localisé (même motif que STAGE_PROBABILITY, KanbanView.jsx)
export function resetInsightsCache() {
  insightsCache = null
}

const fmtMAD = (v) => formatMAD(v)

const periodLabel = (o) => {
  if (o.period_type === 'month' && o.period_month) {
    return `${String(o.period_month).padStart(2, '0')}/${o.period_year}`
  }
  if (o.period_type === 'quarter' && o.period_quarter) {
    return `T${o.period_quarter} ${o.period_year}`
  }
  return String(o.period_year)
}

function SectionState({ loading, error, empty, emptyLabel, children }) {
  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </p>
    )
  }
  if (error) {
    return (
      <p className="text-sm text-muted-foreground">
        Données indisponibles — réessayez.
      </p>
    )
  }
  if (empty) return <p className="text-sm text-muted-foreground">{emptyLabel}</p>
  return children
}

// ── VX219 — « Mes chiffres » : le vendeur `normal` voit ENFIN sa propre
// performance, en tête du Dashboard (tous rôles, aucun gate). Les compteurs
// devis/CA/leads chauds sont dérivés des slices REDUX déjà chargées par
// Dashboard.jsx (filtrées `created_by===moi` / `owner===moi` côté APPELANT —
// cette carte reste purement présentationnelle pour ces props, aucun appel
// réseau) ; seule l'atteinte d'objectif (FG39) refait un appel, scopé
// `?owner=` pour ne JAMAIS agréger l'équipe. `/reporting/commercial` reste le
// seul outil manager (gate `roleLoader` inchangé) — cette carte n'en est ni
// un remplacement ni une porte dérobée.
export function MesChiffresCard({
  envoyes = 0, acceptes = 0, tauxSignature = 0, caSigne = 0,
  leadsChauds = [], userId, navigate,
}) {
  const [attainment, setAttainment] = useState(null)
  const [attainmentError, setAttainmentError] = useState(false)

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- load-on-mount/re-fetch state */
    if (!userId) { setAttainment([]); return undefined }
    let alive = true
    setAttainment(null)
    setAttainmentError(false)
    /* eslint-enable react-hooks/set-state-in-effect */
    crmApi.getObjectifsAttainment({ owner: userId })
      .then((r) => { if (alive) setAttainment(r.data ?? []) })
      .catch(() => { if (alive) { setAttainment([]); setAttainmentError(true) } })
    return () => { alive = false }
  }, [userId])

  return (
    <Card className="mb-4 sm:mb-5" data-testid="mes-chiffres-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="size-4 text-muted-foreground" aria-hidden="true" />
          Mes chiffres
        </CardTitle>
        <CardDescription>Votre performance personnelle du mois</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Devis envoyés
            </span>
            <span className="font-display text-xl font-semibold tabular-nums">{formatNumber(envoyes)}</span>
          </div>
          <div>
            <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Devis acceptés
            </span>
            <span className="font-display text-xl font-semibold tabular-nums">{formatNumber(acceptes)}</span>
          </div>
          <div>
            <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Taux de signature
            </span>
            <span className="font-display text-xl font-semibold tabular-nums">{formatPercent(tauxSignature)}</span>
          </div>
          <div>
            <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
              CA signé
            </span>
            <span className="font-display text-xl font-semibold tabular-nums">
              {formatMAD(caSigne, { decimals: 0 })}
            </span>
          </div>
        </div>

        {attainment != null && attainment.length > 0 && (
          <ul className="mt-3 flex flex-col gap-1.5 border-t border-border pt-3" data-testid="mes-chiffres-objectifs">
            {attainment.map((o) => (
              <li key={o.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="font-medium">{o.metric_display}</span>
                <Badge tone={o.taux >= 100 ? 'success' : o.taux >= 60 ? 'warning' : 'neutral'}>
                  {Math.round(o.taux)} %
                </Badge>
              </li>
            ))}
          </ul>
        )}
        {attainmentError && (
          <p className="mt-2 text-xs text-muted-foreground">Objectifs indisponibles — réessayez.</p>
        )}

        {leadsChauds.length > 0 && (
          <div className="mt-3 border-t border-border pt-3">
            <span className="mb-1.5 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Flame className="size-3.5" aria-hidden="true" />
              Leads chauds à traiter
            </span>
            <ul className="flex flex-col gap-1">
              {leadsChauds.map((l) => (
                <li key={l.id}>
                  <button
                    type="button"
                    onClick={() => navigate?.(`/crm/leads?lead=${l.id}`)}
                    className="flex w-full items-center justify-between gap-2 rounded px-1 py-1 text-left text-sm hover:bg-muted"
                  >
                    <span className="truncate font-medium text-foreground">
                      {`${l.nom ?? ''} ${l.prenom ?? ''}`.trim() || 'Lead'}
                    </span>
                    <ScoreBadge lead={l} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function CrmInsightsPanel() {
  // LB30 — la company active invalide le cache (jamais d'agrégat d'une autre
  // company affiché après un changement de compte). Lu au premier rendu :
  // si un cache FRAIS existe déjà pour cette company, on démarre avec ses
  // valeurs (aucun spinner « Chargement… » revu pour rien).
  const companyId = useSelector((s) => s.auth.user?.active_company_id)
  const cached = readInsightsCache(companyId)
  const [attainment, setAttainment] = useState(cached?.attainment ?? null)
  const [roi, setRoi] = useState(cached?.roi ?? null)
  const [sla, setSla] = useState(cached?.sla ?? null)
  const [errors, setErrors] = useState(cached?.errors ?? {})

  useEffect(() => {
    // Une seule entrée par company (fraîche ou créée ici) ; on peint ce qui
    // est déjà résolu puis on s'abonne aux promesses — un remontage PENDANT
    // le vol reçoit donc les données à l'arrivée au lieu d'un spinner infini
    // (critique Fable LB #5).
    let alive = true
    const entry = loadInsights(companyId)
    const sync = () => {
      if (!alive) return
      setAttainment(entry.attainment)
      setRoi(entry.roi)
      setSla(entry.sla)
      setErrors({ ...entry.errors })
    }
    sync()
    entry.pAttainment.then(sync)
    entry.pRoi.then(sync)
    entry.pSla.then(sync)
    return () => { alive = false }
  }, [companyId])

  const slaResults = sla?.results ?? []

  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-3" data-testid="crm-insights">
      {/* FG39 — objectifs commerciaux */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="size-4 text-muted-foreground" aria-hidden="true" />
            Objectifs — atteinte
          </CardTitle>
          <CardDescription>Réalisé vs cible par vendeur / période</CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={attainment == null} error={errors.attainment}
                        empty={(attainment ?? []).length === 0}
                        emptyLabel="Aucun objectif défini.">
            <ul className="flex flex-col gap-2">
              {(attainment ?? []).map((o) => (
                <li key={o.id} className="rounded-lg border border-border p-2.5 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium">
                      {o.metric_display} — {o.owner_nom ?? 'Équipe'}
                    </span>
                    <Badge tone={o.taux >= 100 ? 'success' : o.taux >= 60 ? 'warning' : 'neutral'}>
                      {Math.round(o.taux)} %
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {periodLabel(o)} · réalisé {formatNumber(o.realise)}
                    {' '}/ cible {formatNumber(o.cible)}
                  </p>
                </li>
              ))}
            </ul>
          </SectionState>
        </CardContent>
      </Card>

      {/* FG34 — ROI par source */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" aria-hidden="true" />
            ROI par source
          </CardTitle>
          <CardDescription>Taux de signature et valeur signée par canal / campagne</CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={roi == null} error={errors.roi}
                        empty={(roi ?? []).length === 0}
                        emptyLabel="Aucune donnée de source.">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1 pr-2 font-medium">Source</th>
                  <th className="py-1 pr-2 text-right font-medium">Leads</th>
                  <th className="py-1 pr-2 text-right font-medium">Signés</th>
                  <th className="py-1 text-right font-medium">Valeur TTC</th>
                </tr>
              </thead>
              <tbody>
                {(roi ?? []).map((r, i) => (
                  <tr key={`${r.canal}-${r.utm_campaign ?? i}`} className="border-t border-border">
                    <td className="py-1 pr-2">
                      {r.canal || '—'}
                      {r.utm_campaign ? (
                        <span className="text-xs text-muted-foreground"> · {r.utm_campaign}</span>
                      ) : null}
                    </td>
                    <td className="py-1 pr-2 text-right">{r.lead_count}</td>
                    <td className="py-1 pr-2 text-right">
                      {r.signed_count} ({r.win_rate} %)
                    </td>
                    <td className="py-1 text-right">{fmtMAD(r.signed_value_ttc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionState>
        </CardContent>
      </Card>

      {/* FG28 — retards SLA de premier contact */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlarmClock className="size-4 text-muted-foreground" aria-hidden="true" />
            SLA premier contact
            {sla != null && sla.count > 0 && (
              <Badge tone="danger">{sla.count}</Badge>
            )}
          </CardTitle>
          <CardDescription>
            {sla?.sla_hours
              ? `Leads NEW non contactés depuis plus de ${sla.sla_hours} h`
              : 'Leads NEW non contactés au-delà du délai société'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SectionState loading={sla == null} error={errors.sla}
                        empty={slaResults.length === 0}
                        emptyLabel={sla?.sla_hours === 0
                          ? 'SLA désactivé (0 h) — configurable dans Paramètres → Leads.'
                          : 'Aucun lead en retard de premier contact.'}>
            <ul className="flex flex-col gap-1.5">
              {slaResults.slice(0, 10).map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-2 rounded-lg border border-border p-2 text-sm">
                  <span className="font-medium">{l.nom}</span>
                  <span className="text-xs text-muted-foreground">
                    créé le {l.date_creation
                      ? new Date(l.date_creation).toLocaleDateString('fr-FR') : '—'}
                  </span>
                </li>
              ))}
              {slaResults.length > 10 && (
                <li className="text-xs text-muted-foreground">
                  … et {slaResults.length - 10} autre(s).
                </li>
              )}
            </ul>
          </SectionState>
        </CardContent>
      </Card>
    </div>
  )
}
