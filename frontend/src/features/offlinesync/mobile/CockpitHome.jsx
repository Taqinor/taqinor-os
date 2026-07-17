// NTMOB5 — Accueil mobile rôle Dirigeant : `/mobile/cockpit`, cockpit compact
// chiffres clés (CA du mois, pipeline pondéré, factures en retard, chantiers
// en cours) réutilisant reporting/dashboard/ + reporting/pipeline/ (mêmes
// endpoints que la page Reporting desktop, aucun nouveau calcul), plus une
// section « Mes approbations » qui agrège les items en attente cross-module
// via reporting/approbations-en-attente/ (le sélecteur déjà utilisé par
// FE-XKB1-3 / VX86 ApprobationsAttentionCard, réutilisé ici en lecture) —
// pas de nouvelle logique d'approbation, seulement l'agrégation en vue mobile.
import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Inbox, TrendingUp, AlertTriangle, HardHat, Wallet } from 'lucide-react'
import reportingApi from '../../../api/reportingApi'
import installationsApi from '../../../api/installationsApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent,
  Badge, Spinner, EmptyState, Stat,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { formatMAD, formatNumber } from '../../../lib/format'

const SOURCE_LABELS = {
  automation: 'Automatisation',
  contrats: 'Contrats',
  ged: 'GED',
  installations: 'Installations',
  workflow: 'Workflow',
}

export default function CockpitHome() {
  const isMobile = useIsMobile()
  const navigate = useNavigate()
  const [kpis, setKpis] = useState(null)
  const [approbations, setApprobations] = useState(null)

  useEffect(() => {
    if (!isMobile) return undefined
    let alive = true

    Promise.all([
      reportingApi.getDashboard(),
      reportingApi.getPipeline(),
      installationsApi.getInstallations({ statut: 'en_cours', page_size: 1 }),
    ]).then(([dashboardRes, pipelineRes, chantiersRes]) => {
      if (!alive) return
      const d = dashboardRes.data || {}
      const caMensuel = d.ca_mensuel || []
      const caDuMois = caMensuel.length > 0 ? caMensuel[caMensuel.length - 1].ca : 0
      const facturesEnRetard = (d.statuts_factures || [])
        .find((s) => s.name === 'En retard')?.value ?? 0
      const chantiersEnCours = chantiersRes.data?.count
        ?? chantiersRes.data?.results?.length ?? 0
      setKpis({
        caDuMois,
        pipelinePondere: pipelineRes.data?.prevision_ponderee,
        facturesEnRetard,
        chantiersEnCours,
      })
    }).catch(() => { if (alive) setKpis(false) })

    reportingApi.approbationsEnAttente()
      .then((r) => { if (alive) setApprobations(r.data?.items ?? []) })
      .catch(() => { if (alive) setApprobations([]) })

    return () => { alive = false }
  }, [isMobile])

  if (!isMobile) return <Navigate to="/dashboard" replace />

  return (
    <div className="flex flex-col gap-3 p-3 pb-24">
      <Card>
        <CardHeader>
          <CardTitle>Chiffres clés</CardTitle>
          <CardDescription>Ce mois-ci</CardDescription>
        </CardHeader>
        <CardContent>
          {kpis === null
            ? <Spinner />
            : kpis === false
              ? <EmptyState title="Chiffres indisponibles" />
              : (
                <div className="grid grid-cols-2 gap-3">
                  <Stat
                    label="CA du mois" icon={Wallet}
                    value={formatMAD(kpis.caDuMois)}
                  />
                  <Stat
                    label="Pipeline pondéré" icon={TrendingUp}
                    value={formatMAD(kpis.pipelinePondere)}
                  />
                  <Stat
                    label="Factures en retard" icon={AlertTriangle}
                    value={formatNumber(kpis.facturesEnRetard)}
                  />
                  <Stat
                    label="Chantiers en cours" icon={HardHat}
                    value={formatNumber(kpis.chantiersEnCours)}
                  />
                </div>
              )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Inbox className="size-4 text-muted-foreground" aria-hidden="true" />
                Mes approbations
              </CardTitle>
              <CardDescription>En attente de votre décision</CardDescription>
            </div>
            {approbations && approbations.length > 0 && (
              <Badge tone="warning">{approbations.length}</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {approbations === null
            ? <Spinner />
            : approbations.length === 0
              ? <EmptyState title="Aucune approbation en attente" />
              : (
                <ul className="flex flex-col divide-y divide-border">
                  {approbations.map((item) => (
                    <li key={`${item.source}-${item.id}`}>
                      <button
                        type="button"
                        className="flex w-full items-center justify-between gap-2 py-2 text-left"
                        onClick={() => navigate(item.lien || '/approbations')}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {item.libelle || `#${item.id}`}
                        </span>
                        <Badge tone="neutral">
                          {SOURCE_LABELS[item.source] || item.source}
                        </Badge>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
        </CardContent>
      </Card>
    </div>
  )
}
