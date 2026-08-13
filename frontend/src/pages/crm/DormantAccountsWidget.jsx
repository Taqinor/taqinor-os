import { useEffect, useState } from 'react'
import { MoonStar } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../api/crmApi'
import {
  Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Spinner,
} from '../../ui'

/* ============================================================================
   NTCRM15 — Widget dashboard « Comptes à réactiver » (comptes dormants,
   NTCRM14 : au moins un devis/facture passé, aucune activité depuis le seuil
   société — défaut 90 jours). Liste + bouton one-click « créer une activité
   de relance » (journalise une note sur le lead le plus récent du client,
   `clients/{id}/relancer-dormance/`). Lecture + une seule action d'écriture
   ciblée ; le reste du widget reste purement consultatif.
   ========================================================================== */
export default function DormantAccountsWidget({ seuil = 90 }) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [comptes, setComptes] = useState([])
  const [relanceId, setRelanceId] = useState(null)
  const [relanceDoneIds, setRelanceDoneIds] = useState(() => new Set())

  useEffect(() => {
    let active = true
    // setState différé au prochain microtask (jamais synchrone dans l'effet) —
    // évite react-hooks/set-state-in-effect sans changer le comportement visible.
    queueMicrotask(() => { if (active) setLoading(true) })
    crmApi.getComptesDormants(seuil)
      .then((r) => { if (active) setComptes(r.data?.results ?? []) })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [seuil])

  const relancer = async (id) => {
    setRelanceId(id)
    try {
      await crmApi.relancerDormance(id)
      setRelanceDoneIds((prev) => new Set(prev).add(id))
    } catch {
      // best-effort UI — l'échec reste silencieux, le bouton redevient cliquable
    } finally {
      setRelanceId(null)
    }
  }

  return (
    <Card data-testid="dormant-accounts-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MoonStar className="h-4 w-4" /> Comptes à réactiver
        </CardTitle>
        <CardDescription>
          Aucune activité depuis {seuil} jours (devis, facture, contact).
        </CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Spinner />
        ) : error ? (
          <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
        ) : comptes.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun compte dormant. 🎉</p>
        ) : (
          <ul className="space-y-2">
            {comptes.map((c) => (
              <li
                key={c.id}
                className="flex items-center justify-between gap-2 rounded-md border border-border p-2"
              >
                <button
                  type="button"
                  className="truncate text-left text-sm font-medium hover:underline"
                  onClick={() => navigate(`/crm?id=${c.id}`)}
                >
                  {c.nom}
                  <span className="block text-xs font-normal text-muted-foreground">
                    {c.jours_inactivite != null
                      ? `${c.jours_inactivite} j sans activité`
                      : 'Jamais actif'}
                  </span>
                </button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={relanceId === c.id || relanceDoneIds.has(c.id)}
                  onClick={() => relancer(c.id)}
                >
                  {relanceDoneIds.has(c.id) ? 'Relancé' : 'Créer une relance'}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
