// VTA11 — Historique des visites PRÉCÉDENTES du même lead, en lecture seule.
//
// Pourquoi sur le terrain : le commercial qui arrive doit savoir ce qui a
// DÉJÀ été relevé (une visite renvoyée « à refaire » il y a trois semaines, un
// passage validé l'an dernier) sans ouvrir le CRM — auquel il n'a pas accès.
//
// Tout vient du serveur (`GET /visites/visites/?lead=<id>`, mêmes champs que
// les cartes de « Ma journée ») : `complet`/`manquants_count`/`statut` sont
// AFFICHÉS, jamais recalculés. La visite courante est retirée de la liste.
// Aucune action ici : c'est un rappel, pas un second point d'édition.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Badge, Spinner } from '../../ui'
import visitesApi from '../../api/visitesApi'
import { STATUT_VISITE_LABEL } from './visiteHelpers'

export default function VisiteHistoriquePanel({ leadId, visiteCouranteId }) {
  const [visites, setVisites] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    if (!leadId) { setLoading(false); return }
    // `Promise.resolve().then(...)` : même un échec SYNCHRONE de l'appel
    // tombe dans le `.catch` ci-dessous — l'historique est un confort, il ne
    // doit jamais faire tomber l'écran de visite.
    Promise.resolve().then(() => visitesApi.getVisites({ lead: leadId }))
      .then((res) => {
        const liste = res.data?.results ?? res.data ?? []
        setVisites(liste.filter((v) => String(v.id) !== String(visiteCouranteId)))
      })
      // Silencieux À DESSEIN : l'historique est un CONFORT. Son indisponibilité
      // ne doit pas couvrir l'écran de visite d'un message d'erreur alarmant.
      .catch(() => setVisites([]))
      .finally(() => setLoading(false))
  }, [leadId, visiteCouranteId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  if (loading) return <Spinner />
  if (visites.length === 0) return null

  return (
    <Card className="mb-3 p-3 text-sm" data-testid="visite-historique-panel">
      <p className="font-medium">Visites précédentes de ce client</p>
      <ul className="mt-2 space-y-1.5">
        {visites.map((v) => (
          <li key={v.id} className="flex items-center justify-between gap-2">
            <Link to={`/visites/${v.id}`} className="min-w-0 truncate text-primary underline">
              {v.date_realisee || v.date_prevue || `Visite ${v.id}`}
              {' — '}
              {STATUT_VISITE_LABEL[v.statut] ?? v.statut}
            </Link>
            <Badge tone={v.complet ? 'success' : 'neutral'} className="shrink-0">
              {v.complet ? 'Complète' : `${v.manquants_count ?? 0} manquant(s)`}
            </Badge>
          </li>
        ))}
      </ul>
    </Card>
  )
}
