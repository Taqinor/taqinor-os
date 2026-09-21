import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../../api/calepinageApi'
import { Badge, Button, Card, EmptyState, Spinner } from '../../../ui'
import { History } from 'lucide-react'
import { formatDateTime } from '../../../lib/format'

/* ============================================================================
   CALX36 — L'HISTORIQUE DES VERSIONS ET LA RESTAURATION.
   ----------------------------------------------------------------------------
   Constat : `calepinageApi.js` expose déjà `versions`/`restaurerVersion`
   (servis, `views/calepinages.py:413-458`), et AUCUN écran ne les appelait —
   `FicheCalepinage.jsx` n'affichait que le NOMBRE de versions.

   LA VERSION COURANTE est la PREMIÈRE de la liste : le sélecteur
   (`selectors.versions`) trie `-created_at` — la plus récente EST l'état
   actuel du calepinage. Elle est marquée et n'a pas de bouton « Restaurer »
   (restaurer la version déjà courante ne voudrait rien dire).

   RESTAURER CRÉE UNE VERSION NEUVE (`services/versions.py::restaurer_version`,
   appelé en tête d'écriture commune) : AUCUNE version n'est jamais réécrite
   ni supprimée — le rappel est affiché en permanence, pas seulement au clic.
   Confirmation en DEUX TEMPS (« Restaurer » → « Confirmer » / « Annuler »)
   avant l'appel réseau : une restauration est irréversible-conceptuellement
   (elle change l'état COURANT), jamais un simple clic.
   ========================================================================== */

export default function PanneauVersions({ calepinageId: idPropose } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl

  const [versions, setVersions] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [confirmationId, setConfirmationId] = useState(null)
  const [restaurationEnCours, setRestaurationEnCours] = useState(null)

  const charger = useCallback(() => {
    if (!calepinageId) return Promise.resolve()
    return Promise.resolve(calepinageApi.calepinages.versions(calepinageId))
      .then((res) => setVersions(Array.isArray(res?.data) ? res.data : []))
      .catch(() => setErreur('L’historique des versions n’a pas pu être chargé.'))
  }, [calepinageId])

  useEffect(() => { charger() }, [charger])

  const demanderRestauration = (id) => { setConfirmationId(id); setErreur(null) }
  const annulerRestauration = () => setConfirmationId(null)

  const confirmerRestauration = (id) => {
    setRestaurationEnCours(id)
    Promise.resolve(calepinageApi.calepinages.restaurerVersion(calepinageId, id))
      .then(() => {
        setConfirmationId(null)
        return charger()
      })
      .catch(() => setErreur('La restauration n’a pas pu être effectuée.'))
      .finally(() => setRestaurationEnCours(null))
  }

  return (
    <div className="mt-6" data-testid="cal-versions">
      <p className="tech-label rule-brass text-brass-300">Versions</p>
      <p className="mt-2 text-xs text-lune-faint" data-testid="cal-versions-rappel">
        Restaurer une version CRÉE une version neuve : aucune version n’est
        jamais réécrite ni supprimée.
      </p>

      {erreur && (
        <p role="alert" className="mt-3 text-sm text-destructive" data-testid="cal-versions-erreur">
          {erreur}
        </p>
      )}

      <div className="mt-3">
        {versions === null ? (
          <div className="flex items-center gap-2 text-sm text-lune-faint">
            <Spinner />
            Chargement des versions…
          </div>
        ) : versions.length === 0 ? (
          <EmptyState
            icon={History}
            title="Aucune version pour l’instant"
            description="Un instantané apparaît ici à chaque écriture sur la conception."
          />
        ) : (
          <ul className="space-y-2">
            {versions.map((version, index) => {
              const courante = index === 0
              const enConfirmation = confirmationId === version.id
              return (
                <Card key={version.id} className="p-3" data-testid={`cal-versions-ligne-${version.id}`}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 text-sm text-white">
                        <span>{version.libelle || `Version ${version.id}`}</span>
                        {courante && (
                          <Badge variant="outline" data-testid={`cal-versions-courante-${version.id}`}>
                            Version courante
                          </Badge>
                        )}
                        {version.a_un_resultat && (
                          <Badge variant="outline">Avec résultat</Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {formatDateTime(version.cree_le)}
                        {version.cree_par?.nom_complet ? ` · ${version.cree_par.nom_complet}` : ''}
                      </div>
                    </div>

                    {!courante && (
                      enConfirmation ? (
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-lune-soft">Confirmer la restauration ?</span>
                          <Button
                            size="sm"
                            onClick={() => confirmerRestauration(version.id)}
                            disabled={restaurationEnCours === version.id}
                            data-testid={`cal-versions-confirmer-${version.id}`}
                          >
                            {restaurationEnCours === version.id ? 'Restauration…' : 'Confirmer'}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={annulerRestauration}
                            disabled={restaurationEnCours === version.id}
                            data-testid={`cal-versions-annuler-${version.id}`}
                          >
                            Annuler
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => demanderRestauration(version.id)}
                          data-testid={`cal-versions-restaurer-${version.id}`}
                        >
                          Restaurer
                        </Button>
                      )
                    )}
                  </div>
                </Card>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
