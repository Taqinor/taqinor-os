// ZSAL3 — Tableau de bord « Mes équipes » : pipeline ouvert/pondéré, activités
// en retard, CA signé du mois vs cible, par équipe commerciale active de la
// société (apps.crm.selectors.stats_equipe). Composant autonome monté depuis
// le Dashboard : rend NULL sans rien afficher si l'utilisateur n'a pas accès
// à l'endpoint (403, ex. rôle limité) ou si aucune équipe n'est configurée —
// jamais de carte vide/cassée pour les rôles sans équipe.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Users } from 'lucide-react'
import crmApi from '../api/crmApi'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Progress } from '../ui'
import { formatMAD, formatNumber } from '../lib/format'

export default function MesEquipesCard() {
  const [equipes, setEquipes] = useState(null) // null = pas encore chargé
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    crmApi.getEquipesStatistiques()
      .then((r) => { if (alive) setEquipes(r.data?.equipes ?? []) })
      .catch(() => { if (alive) setError(true) })
    return () => { alive = false }
  }, [])

  // Rien à montrer : chargement pas terminé, erreur (rôle sans accès), ou
  // aucune équipe active de la société — pas de carte pour ces trois cas.
  if (error || equipes == null || equipes.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="size-4 text-muted-foreground" aria-hidden="true" />
          Mes équipes
        </CardTitle>
        <CardDescription>
          Pipeline, activités en retard et CA signé du mois, par équipe commerciale
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {equipes.map((eq) => (
          <div key={eq.id} className="rounded-lg border border-border p-3">
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="font-medium text-foreground">{eq.nom}</span>
              <span className="text-xs text-muted-foreground">
                {formatNumber(eq.nb_membres)} membre(s)
                {eq.responsable ? ` · ${eq.responsable}` : ''}
              </span>
            </div>
            {/* VX236 — fin des culs-de-sac : chaque chiffre d'équipe ouvre la
                liste correspondante, pré-filtrée sur les membres de CETTE
                équipe (jamais un dashboard qu'on ne peut que regarder). */}
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Link to={`/crm/leads?equipe=${eq.id}`} className="block rounded-md hover:bg-accent/50">
                <div className="text-xs text-muted-foreground">Pipeline ouvert</div>
                <div className="font-medium tabular-nums text-foreground">
                  {formatNumber(eq.pipeline_ouvert_count)} · {formatMAD(eq.pipeline_ouvert_valeur, { decimals: 0 })}
                </div>
              </Link>
              <div>
                <div className="text-xs text-muted-foreground">Pondéré</div>
                <div className="font-medium tabular-nums">
                  {formatMAD(eq.pipeline_pondere, { decimals: 0 })}
                </div>
              </div>
              <Link to="/activites" className="block rounded-md hover:bg-accent/50">
                <div className="text-xs text-muted-foreground">Activités en retard</div>
                <div className={`font-medium tabular-nums ${eq.activites_en_retard > 0 ? 'text-destructive' : 'text-foreground'}`}>
                  {formatNumber(eq.activites_en_retard)}
                </div>
              </Link>
              <Link to={`/ventes/devis?statut=accepte&equipe=${eq.id}`} className="block rounded-md hover:bg-accent/50">
                <div className="text-xs text-muted-foreground">CA signé (mois)</div>
                <div className="font-medium tabular-nums text-foreground">
                  {formatMAD(eq.ca_signe_mois, { decimals: 0 })}
                  {eq.cible_ca_signe_mois && Number(eq.cible_ca_signe_mois) > 0
                    ? ` / ${formatMAD(eq.cible_ca_signe_mois, { decimals: 0 })}` : ''}
                </div>
              </Link>
            </div>
            {eq.avancement_pct != null && (
              <div className="mt-2">
                <Progress value={Math.min(100, eq.avancement_pct)} />
                <div className="mt-1 text-right text-xs text-muted-foreground">
                  {eq.avancement_pct}% de la cible
                </div>
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}
