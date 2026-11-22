import { Suspense, lazy, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ContextePresentation } from '../atelier/coque/contexteCoque'
import HabillageClient from './HabillageClient'
import { PiedClient, PlanDessus, PuceProjet, TuilesClient } from './partiesClient'
import { useDonneesClient, webglDisponible } from './vueClient.helpers'

/* ============================================================================
   « MONTRER AU CLIENT » AU TÉLÉPHONE (`/calepinage/:id/client`, maquette TelephoneClient).
   ----------------------------------------------------------------------------
   CE QUI EST MONTRÉ : L'ATELIER LUI-MÊME, en MODE PRÉSENTATION — le même écran
   (`ToitureDesign mode="calepinage"`, même chunk, même démarrage `useAtelierBoot`), en
   lecture seule (`lectureSeuleImposee`), sa VRAIE 3D bord à bord ; la coque masque
   tout contrôle d'édition (`ContextePresentation`) et rend autour l'habillage client
   (`HabillageClient` : puce, soleil renvoyé aux vrais contrôles, trois tuiles, pied).
   REPLI 2D (L7) : le toit ENREGISTRÉ vu de dessus — pendant le chargement du chunk de
   l'atelier, puis sur la scène tant que la 3D démarre ; et comme écran entier quand le
   navigateur n'a pas WebGL (la 3D ne peut pas tourner).
   CHIFFRES : document enregistré + résultat publié seulement ; jamais un montant.
   ========================================================================== */

// Le MÊME module que la route de l'atelier (`module.config.jsx` › AtelierCalepinage) : le chunk est partagé.
const Atelier = lazy(() => import('../../../pages/ventes/ToitureDesign'))

/** Le repli 2D : le toit enregistré dessiné de dessus, les tuiles et le pied (écran L7). */
function VueClient2D({ id }) {
  const d = useDonneesClient(id)
  return (
    <div className="cal-tel" data-testid="cal-vue-client">
      <div className="cal-client-scene" data-testid="client-scene">
        {d.plan ? <PlanDessus plan={d.plan} /> : (
          <p className="cal-client-vide" data-testid="client-sans-toit">
            {d.doc.etat === 'chargement' ? 'Lecture du toit enregistré…' : 'Aucun toit enregistré pour ce calepinage.'}
          </p>
        )}
        <PuceProjet titre={d.titre} sousTitre={d.sousTitre} />
        <Link to={`/calepinage/${id}`} className="cal-client-pastille" data-testid="client-voir-3d">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 11-3-6.7" /><path d="M21 4v5h-5" /></svg>
          Vue de dessus · voir la 3D dans l’atelier
        </Link>
      </div>
      <div className="cal-client-corps">
        <TuilesClient tuiles={d.tuiles} ville={d.ville} />
      </div>
      <PiedClient id={id} />
    </div>
  )
}

const PRESENTATION = { rendu: (props) => <HabillageClient {...props} /> }

export default function VueClient({ webgl }) {
  const { id } = useParams()
  const peut3d = useMemo(() => (webgl === undefined ? webglDisponible() : webgl), [webgl])
  if (!peut3d) return <VueClient2D id={id} />
  return (
    <ContextePresentation.Provider value={PRESENTATION}>
      <Suspense fallback={<VueClient2D id={id} />}>
        <Atelier mode="calepinage" lectureSeuleImposee />
      </Suspense>
    </ContextePresentation.Provider>
  )
}
