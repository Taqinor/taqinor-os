// VT5 — Onglet « Visite » du rail contexte : les visites techniques du lead
// (peut y en avoir plusieurs — renvoyée « à refaire » = une nouvelle boucle
// sur la MÊME visite, jamais un doublon) + le bouton de création qui pré-
// remplit `lead` (c'est le « bouton de création depuis la fiche lead » de
// VT5). Aucune mesure/complétude n'est recalculée ici : `complet`/
// `manquants_count` viennent tels quels de `GET /crm/visites/?lead=<id>`.
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../../../api/crmApi'
import { Button, Card, Spinner, Badge } from '../../../ui'
import { toast } from '../../../ui/confirm'
import { STATUT_VISITE_LABEL } from '../../../pages/crm/visites/visiteHelpers'

export default function VisiteTab({ leadId }) {
  const navigate = useNavigate()
  const [visites, setVisites] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)

  const load = useCallback(() => {
    if (!leadId) return
    setLoading(true)
    crmApi.getVisites({ lead: leadId })
      .then((res) => setVisites(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error('Impossible de charger les visites techniques.'))
      .finally(() => setLoading(false))
  }, [leadId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement initial au montage
  useEffect(() => { load() }, [load])

  const creerVisite = async () => {
    setCreating(true)
    try {
      const res = await crmApi.createVisite({ lead: leadId })
      navigate(`/crm/visites/${res.data.id}`)
    } catch {
      toast.error('Création de la visite impossible.')
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="space-y-3" data-testid="visite-tab">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Visite technique</h3>
        <Button type="button" size="sm" onClick={creerVisite} disabled={creating}>
          Planifier une visite
        </Button>
      </div>
      {visites.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune visite technique planifiée pour ce lead.</p>
      ) : (
        <ul className="space-y-2">
          {visites.map((v) => (
            <li key={v.id}>
              <Card
                className="cursor-pointer p-3 text-sm hover:border-primary/50"
                onClick={() => navigate(`/crm/visites/${v.id}`)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>{STATUT_VISITE_LABEL[v.statut] ?? v.statut}</span>
                  <Badge tone={v.complet ? 'success' : 'neutral'}>
                    {v.complet ? 'Complète' : `${v.manquants_count ?? 0} manquant(s)`}
                  </Badge>
                </div>
                {v.date_prevue && (
                  <p className="mt-1 text-xs text-muted-foreground">Prévue le {v.date_prevue}</p>
                )}
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
