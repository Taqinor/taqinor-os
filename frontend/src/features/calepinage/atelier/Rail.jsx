import { Suspense } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { ErrorBoundary, Spinner, Tabs, TabsContent, TabsList, TabsTrigger } from '../../../ui'
import { PARAM_ONGLET, groupesOnglets, resoudreOnglet } from './onglets'

/* ============================================================================
   CALX1 — LE RAIL D'ONGLETS DE L'ATELIER.
   ----------------------------------------------------------------------------
   Il lit `atelier/onglets.js` (le registre, seule surface qu'une tâche rouvre
   pour ajouter un panneau) et monte le composant de l'onglet actif. Il ne
   connaît AUCUN panneau par son nom : ajouter un onglet ne rouvre jamais ce
   fichier.

   L'ONGLET ACTIF EST DANS L'URL (`?onglet=<cle>`), jamais dans un `useState`
   caché : le lien est partageable, le bouton « précédent » du navigateur
   fonctionne, et un rechargement rouvre le même panneau. Les treize routes
   profondes historiques (`/calepinage/:id/<cle>`) restent servies telles
   quelles par `module.config.jsx` : elles sont les liens profonds qui ouvrent
   le même écran, avec la MÊME clé.

   PARITÉ (Aurora) — la conception d'un projet se parcourt par onglets d'un seul
   écran (Site / System / Simulate) plutôt que par des URL qu'il faut connaître :
   https://help.aurorasolar.com/hc/en-us/articles/21240604594963

   SANS `?onglet=`, AUCUN PANNEAU N'EST OUVERT : l'atelier rend exactement ce
   qu'il rendait hier, plus le rail. On n'impose pas un panneau — et un onglet
   ouvert d'office chargerait des données que personne n'a demandées.

   JAMAIS D'ÉCRAN BLANC, DEUX FOIS :
     - une clé inconnue retombe sur le PREMIER onglet (`resoudreOnglet`) ;
     - un panneau qui échoue au rendu est rattrapé par un `ErrorBoundary` qui
       NOMME l'onglet fautif — jamais un « une erreur est survenue » anonyme
       (règle fondateur : l'erreur désigne ce qui a échoué).
   ========================================================================== */

/** Le bandeau d'erreur d'un panneau : il NOMME l'onglet qui n'a pas pu s'ouvrir. */
function EchecOnglet({ libelle }) {
  return (
    <p
      role="alert"
      data-testid="cal-onglet-erreur"
      className="mt-3 border border-destructive/50 bg-destructive/5 px-4 py-3 text-sm text-destructive"
    >
      {`L'onglet « ${libelle} » n'a pas pu s'afficher. Les autres onglets restent ouvrables ; rechargez la page si le problème persiste.`}
    </p>
  )
}

export default function Rail({ calepinageId: idPropose = null } = {}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl ?? null

  const [parametres, setParametres] = useSearchParams()
  const actif = resoudreOnglet(parametres.get(PARAM_ONGLET))
  const groupes = groupesOnglets()

  /* Un changement d'onglet n'écrase pas les autres paramètres de l'URL : le
     calepinage peut en porter d'autres (filtre, variante) qu'on n'a pas à
     connaître ici. */
  const ouvrir = (cle) => {
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, cle)
    setParametres(suivants)
  }

  const Composant = actif?.composant ?? null

  return (
    <Tabs
      value={actif?.cle ?? ''}
      onValueChange={ouvrir}
      className="mt-5"
      data-testid="cal-rail-onglets"
    >
      <TabsList
        aria-label="Onglets du calepinage"
        className="flex w-full flex-wrap gap-x-1 gap-y-1.5"
      >
        {groupes.map(({ groupe, onglets }) => (
          <span key={groupe} className="flex flex-wrap items-center gap-1">
            {/* L'intertitre du groupe : un repère visuel, jamais un élément
                interactif (il resterait sur le chemin du clavier pour rien). */}
            <span className="tech-label px-1 text-lune-faint" aria-hidden="true">{groupe}</span>
            {onglets.map((onglet) => (
              <TabsTrigger
                key={onglet.cle}
                value={onglet.cle}
                data-testid={`cal-onglet-${onglet.cle}`}
              >
                {onglet.libelle}
              </TabsTrigger>
            ))}
          </span>
        ))}
      </TabsList>

      {actif && Composant && (
        <TabsContent value={actif.cle} data-testid="cal-onglet-panneau">
          <ErrorBoundary
            key={actif.cle}
            fallback={<EchecOnglet libelle={actif.libelle} />}
          >
            <Suspense
              fallback={(
                <p className="mt-3 flex items-center gap-2 text-sm text-lune-faint">
                  <Spinner />
                  {`Ouverture de l'onglet « ${actif.libelle} »…`}
                </p>
              )}
            >
              <Composant calepinageId={calepinageId} />
            </Suspense>
          </ErrorBoundary>
        </TabsContent>
      )}
    </Tabs>
  )
}
