import { Grid3x3 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent, Button } from '../../ui'

/* ============================================================================
   CAL213 — encart « Calepinage retenu » de la fiche chantier (lecture seule).
   ----------------------------------------------------------------------------
   Alimenté par le bloc `calepinage` du détail chantier (CAL245,
   `InstallationSerializer.calepinage` — voir
   `backend/django_core/apps/installations/contract_samples/calepinage_retenu.json`) :
   `{calepinage_id, kwc, nb_modules, planche_url, plan_pose_url}` ou `null`
   quand le devis du chantier n'a pas de calepinage avec une variante RETENUE
   (CAL209). Lecture seule et AUCUN recalcul : l'encart n'affiche que ce que le
   serveur a déjà dimensionné — jamais un chiffre redérivé côté écran (règle
   fondateur « zéro chiffre inventé »).

   Règle fondateur 12/09/2026 : « le module chantier ne garde QUE son cœur » —
   ce composant est purement un AFFICHAGE de la donnée servie ; il n'existe
   aucun état local, aucune écriture, aucune dépendance à `apps.calepinage`.
   ========================================================================== */
export default function CalepinageRetenuCard({ calepinage }) {
  const navigate = useNavigate()

  // Discipline du null (CAL245) : pas de calepinage retenu -> l'encart
  // DISPARAÎT, jamais une carte vide ou un tiret qui laisserait croire à une
  // donnée manquante.
  if (!calepinage) return null

  const { kwc, nb_modules: nbModules, planche_url: plancheUrl,
    plan_pose_url: planPoseUrl } = calepinage

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="flex items-center gap-2 text-sm">
          <Grid3x3 className="size-4 text-muted-foreground" aria-hidden="true" />
          Calepinage retenu
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap gap-4 text-sm">
          <span>
            <strong>{kwc != null ? `${kwc} kWc` : '—'}</strong>
          </span>
          <span>
            {nbModules != null
              ? `${nbModules} module${nbModules > 1 ? 's' : ''}`
              : '—'}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {plancheUrl && (
            <Button size="sm" variant="outline" onClick={() => navigate(plancheUrl)}>
              Voir le calepinage
            </Button>
          )}
          {planPoseUrl && (
            <Button size="sm" variant="outline" onClick={() => navigate(planPoseUrl)}>
              Plan de pose 3D
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
