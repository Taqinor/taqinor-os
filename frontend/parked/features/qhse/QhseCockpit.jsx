import { useEffect, useState } from 'react'
import {
  ShieldCheck, Activity, Gauge, AlertTriangle, CheckCircle2,
} from 'lucide-react'
import qhseApi from '../../api/qhseApi'
import {
  ModuleDashboard, EcheanceCenter,
} from '../../ui/module'
import { Card, Badge, Progress, EmptyState } from '../../ui'
import { BarArrondie } from '../../ui/charts'
import { formatNumber } from '../../lib/format'
import { isoNiveauLabel, num } from './qhseStatus'

/* ============================================================================
   UX29 — Cockpit QHSE.
   ----------------------------------------------------------------------------
   Trois blocs :
   • KPI sécurité TF / TG (accidents, jours perdus) via `incidents/
     statistiques-tf-tg` — le taux de fréquence et de gravité sont calculés
     côté serveur (miroir pur dans `qhseStatus.computeTfTg`).
   • Préparation ISO 9001:2015 : score global + checklist par critère (clause
     ISO), via `iso9001-readiness`.
   • Centre d'échéances QHSE (inspections / permis / CNSS) via `calendrier`.
   ========================================================================== */

const ISO_TONE = (score) =>
  score >= 85 ? 'success' : score >= 60 ? 'warning' : 'danger'

export default function QhseCockpit() {
  const [tftg, setTftg] = useState(null)
  const [iso, setIso] = useState(null)
  const [cal, setCal] = useState(null)
  const [pareto, setPareto] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    async function load() {
      setLoading(true)
      setError(null)
      try {
        // Les sources sont indépendantes : on les charge en parallèle et on
        // tolère qu'une échoue (settlements) sans casser tout le cockpit.
        const [tRes, iRes, cRes, pRes] = await Promise.allSettled([
          qhseApi.incidents.statistiquesTfTg(),
          qhseApi.iso9001Readiness(),
          qhseApi.calendrier(),
          qhseApi.paretoDefauts(),
        ])
        if (!alive) return
        setTftg(tRes.status === 'fulfilled' ? tRes.value.data : null)
        setIso(iRes.status === 'fulfilled' ? iRes.value.data : null)
        setCal(cRes.status === 'fulfilled' ? cRes.value.data : null)
        setPareto(pRes.status === 'fulfilled' ? pRes.value.data : null)
        if (
          tRes.status === 'rejected' &&
          iRes.status === 'rejected' &&
          cRes.status === 'rejected'
        ) {
          setError('Cockpit QHSE indisponible — réessayez.')
        }
      } catch {
        if (alive) setError('Cockpit QHSE indisponible — réessayez.')
      } finally {
        if (alive) setLoading(false)
      }
    }
    load()
    return () => { alive = false }
  }, [])

  // XQHS4 — Pareto défauts (comptes + % cumulé), agrégé NCR + relevés + incidents.
  const paretoBars = (pareto?.pareto ?? []).map((p) => ({
    label: p.libelle ?? p.code ?? '—',
    value: num(p.nb) ?? 0,
    color: undefined,
  }))

  const tf = tftg?.tf
  const tg = tftg?.tg
  const stats = [
    {
      label: 'Taux de fréquence (TF)',
      value: tf == null ? '—' : formatNumber(tf, { decimals: 2 }),
      hint: 'Accidents avec arrêt × 1 M / heures travaillées',
      icon: Activity,
    },
    {
      label: 'Taux de gravité (TG)',
      value: tg == null ? '—' : formatNumber(tg, { decimals: 2 }),
      hint: 'Jours perdus × 1 000 / heures travaillées',
      icon: Gauge,
    },
    {
      label: 'Accidents avec arrêt',
      value: formatNumber(tftg?.accidents_avec_arret ?? 0),
      hint: 'Registre incidents (type accident)',
      icon: AlertTriangle,
      to: '/qhse/risques',
    },
    {
      label: 'Préparation ISO 9001',
      value: iso ? `${formatNumber(iso.score_global, { decimals: 0 })} %` : '—',
      hint: iso ? isoNiveauLabel(iso.niveau) : 'Non calculée',
      icon: ShieldCheck,
    },
  ]

  // Graphe des critères ISO (score par critère, borné 0–100).
  const isoBars = (iso?.criteres ?? []).map((c) => ({
    label: c.libelle ?? c.code ?? c.nom ?? '—',
    value: Math.round(num(c.score_effectif ?? c.score) ?? 0),
    color: undefined,
  }))

  const charts = [
    ...(isoBars.length
      ? [{
          title: 'Critères ISO 9001 (score %)',
          span: 'full',
          node: (
            <BarArrondie
              data={isoBars}
              layout="vertical"
              height={Math.max(160, isoBars.length * 34)}
              categoryWidth={220}
              tone="primary"
              name="Score"
              tooltipFormat={(v) => `${v} %`}
            />
          ),
        }]
      : []),
    ...(paretoBars.length
      ? [{
          title: 'Pareto des défauts qualité',
          span: 'full',
          node: (
            <BarArrondie
              data={paretoBars}
              layout="vertical"
              height={Math.max(160, paretoBars.length * 34)}
              categoryWidth={220}
              tone="warning"
              name="Occurrences"
            />
          ),
        }]
      : []),
  ]

  // Échéances calendrier → items EcheanceCenter (lien vers l'écran concerné).
  const TARGET = {
    inspection: '/qhse/inspections',
    permis: '/qhse/risques',
    declaration_cnss: '/qhse/risques',
  }
  const echeances = (cal?.evenements ?? []).map((e) => ({
    id: `${e.type}-${e.id}`,
    label: e.titre || e.reference || 'Échéance QHSE',
    date: e.date,
    meta: `${
      { inspection: 'Inspection', permis: 'Permis de travail',
        declaration_cnss: 'Déclaration CNSS' }[e.type] ?? e.type
    }${e.reference ? ` · ${e.reference}` : ''}`,
    to: TARGET[e.type],
    tone: e.en_retard ? 'danger' : undefined,
  }))

  return (
    <div className="page flex flex-col gap-6">
      <div className="page-header">
        <h2 className="flex items-center gap-2">
          <ShieldCheck size={20} strokeWidth={1.75} aria-hidden="true" />
          Cockpit QHSE
        </h2>
      </div>

      <ModuleDashboard
        stats={stats}
        charts={charts}
        loading={loading}
        error={error}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        {/* ── Checklist de préparation ISO 9001 ── */}
        <Card className="p-4 sm:p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="font-display text-base font-semibold tracking-tight">
              Préparation ISO 9001:2015
            </h3>
            {iso && (
              <Badge tone={ISO_TONE(iso.score_global)}>
                {formatNumber(iso.score_global, { decimals: 0 })} % ·{' '}
                {isoNiveauLabel(iso.niveau)}
              </Badge>
            )}
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">Chargement…</p>
          ) : !iso || !(iso.criteres?.length) ? (
            <EmptyState
              icon={ShieldCheck}
              title="Readiness non disponible"
              description="Aucune donnée qualité à agréger pour le moment."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {iso.criteres.map((c) => {
                const score = Math.round(num(c.score_effectif ?? c.score) ?? 0)
                const ok = !c.no_data && score >= 85
                return (
                  <li key={c.code ?? c.libelle} className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="flex items-center gap-1.5">
                        {ok ? (
                          <CheckCircle2
                            className="size-4 text-success"
                            aria-hidden="true"
                          />
                        ) : (
                          <AlertTriangle
                            className="size-4 text-warning"
                            aria-hidden="true"
                          />
                        )}
                        <span className="font-medium">
                          {c.libelle ?? c.nom ?? c.code}
                        </span>
                        {c.clause && (
                          <span className="text-xs text-muted-foreground">
                            (clause {c.clause})
                          </span>
                        )}
                      </span>
                      <span className="tabular-nums text-muted-foreground">
                        {c.no_data ? 'Aucune donnée' : `${score} %`}
                      </span>
                    </div>
                    <Progress
                      value={c.no_data ? 0 : score}
                      tone={ok ? 'success' : 'warning'}
                    />
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        {/* ── Centre d'échéances QHSE ── */}
        <EcheanceCenter
          title="Échéances QHSE"
          items={echeances}
          loading={loading}
          emptyText="Aucune inspection, permis ou déclaration à échéance."
          max={12}
        />
      </div>
    </div>
  )
}
