import { useState } from 'react'
import { Grid3x3 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardContent, Button } from '../../ui'
import calepinageApi from '../../api/calepinageApi'
import { downloadBlob, filenameFromResponse } from '../../utils/downloadBlob'

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
  // ACAL903 — état du téléchargement du PDF « Plan de pose » (blob par le client API).
  const [enCours, setEnCours] = useState(false)
  const [erreurPdf, setErreurPdf] = useState(null)

  // Discipline du null (CAL245) : pas de calepinage retenu -> l'encart
  // DISPARAÎT, jamais une carte vide ou un tiret qui laisserait croire à une
  // donnée manquante.
  if (!calepinage) return null

  const { kwc, nb_modules: nbModules, planche_url: plancheUrl,
    plan_pose_url: planPoseUrl, plan_pose_pdf_url: planPosePdfUrl, kwc_source: kwcSource,
    dessin_kwc: dessinKwc, ecart_kwc: ecartKwc } = calepinage
  // ACAL274 — kWc/modules servis = le VENDU (lignes du devis) ; le dessin est
  // affiché comme tel avec l'écart que le serveur a calculé (jamais redérivé).
  const vendu = kwcSource === 'devis'

  async function telechargerPlanPose() {
    setErreurPdf(null)
    setEnCours(true)
    try {
      const reponse = await calepinageApi.calepinages.telechargerDocument(
        planPosePdfUrl, undefined, { suppressErrorToast: true })
      downloadBlob(reponse.data, filenameFromResponse(reponse, 'plan-pose.pdf'))
    } catch {
      setErreurPdf('Le plan de pose (PDF) n’a pas pu être produit : ouvrez le calepinage pour voir ce qui est à reprendre.')
    } finally {
      setEnCours(false)
    }
  }

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
            {vendu && kwc != null ? ' vendus' : ''}
          </span>
          <span>
            {nbModules != null
              ? `${nbModules} module${nbModules > 1 ? 's' : ''}`
              : '—'}
          </span>
          {vendu && dessinKwc != null && (
            <span className="text-muted-foreground">
              {`dessin : ${dessinKwc} kWc`}
              {ecartKwc ? ` (écart ${ecartKwc > 0 ? '+' : ''}${ecartKwc} kWc)` : ''}
            </span>
          )}
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
          {planPosePdfUrl && (
            <Button size="sm" variant="outline" disabled={enCours} onClick={telechargerPlanPose}>
              Plan de pose (PDF)
            </Button>
          )}
        </div>
        {erreurPdf && (
          <p role="alert" className="text-xs text-destructive" data-testid="acal903-erreur-pdf">
            {erreurPdf}
          </p>
        )}
      </CardContent>
    </Card>
  )
}
