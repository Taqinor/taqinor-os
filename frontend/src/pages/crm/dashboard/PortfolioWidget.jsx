import { useEffect, useState } from 'react'
import { Briefcase } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Spinner,
} from '../../../ui'

/* ============================================================================
   NTCRM29 — Widget dashboard commercial « portefeuille de comptes » : les
   comptes du commercial CONNECTÉ (owner via leads liés, `GET /crm/clients/
   mon-portefeuille/`), triés par score d'engagement (NTCRM16) CROISSANT (les
   plus froids en premier — priorisation d'action), avec lien direct vers le
   plan de compte (NTCRM10) quand il existe. Le backend scope déjà tout par
   `request.user`/`request.user.company` — aucun paramètre ici.
   ========================================================================== */
export default function PortfolioWidget() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [comptes, setComptes] = useState([])

  useEffect(() => {
    // setState n'arrive que dans les callbacks asynchrones (jamais synchrone
    // dans l'effet) : l'état initial loading=true couvre le seul chargement
    // (deps=[] — pas de refetch à re-signaler).
    let active = true
    crmApi.getMonPortefeuille()
      .then((r) => { if (active) setComptes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  return (
    <Card data-testid="portfolio-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="h-4 w-4" /> Portefeuille de comptes
        </CardTitle>
        <CardDescription>
          Vos comptes, du plus froid au plus chaud (score d&apos;engagement).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : comptes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun compte dans votre portefeuille.</p>
        ) : (
          <ul className="space-y-2">
            {comptes.map((c) => (
              <li
                key={c.client_id}
                className="flex items-center justify-between gap-2 rounded-md border border-border p-2"
              >
                <button
                  type="button"
                  className="truncate text-left text-sm font-medium hover:underline"
                  onClick={() => navigate(`/crm?id=${c.client_id}`)}
                >
                  {c.nom}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {c.label} — score {c.score}
                    {c.plan_compte_id != null && ' · plan de compte'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
