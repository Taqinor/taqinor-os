import { Component, Suspense, lazy, useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ContextePresentation } from '../atelier/coque/contexteCoque'
import HabillageClient from './HabillageClient'
import { AvisEchec3D, IconeTourner, PiedClient, PlanDessus, PuceProjet, TuilesClient } from './partiesClient'
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
function VueClient2D({ id, echec3d = false }) {
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
        {echec3d ? <AvisEchec3D onReessayer={() => window.location.reload()} /> : (
          <Link to={`/calepinage/${id}`} className="cal-client-pastille" data-testid="client-voir-3d">
            <IconeTourner />
            Vue de dessus · voir la 3D dans l’atelier
          </Link>
        )}
      </div>
      <div className="cal-client-corps">
        <TuilesClient tuiles={d.tuiles} ville={d.ville} />
      </div>
      <PiedClient id={id} />
    </div>
  )
}

const PRESENTATION = { rendu: (props) => <HabillageClient {...props} /> }

/** H6 — le chunk de l'atelier (ou du constructeur) ne se charge pas : la vue client reste, en repli 2D, et le DIT
 *  (« Réessayer ») — jamais la page d'erreur générique devant le client. */
class GardeAtelier extends Component {
  constructor(props) { super(props); this.state = { echec: false } }
  static getDerivedStateFromError() { return { echec: true } }
  render() { return this.state.echec ? <VueClient2D id={this.props.id} echec3d /> : this.props.children }
}

export default function VueClient({ webgl }) {
  const { id } = useParams()
  const peut3d = useMemo(() => (webgl === undefined ? webglDisponible() : webgl), [webgl])
  if (!peut3d) return <VueClient2D id={id} />
  return (
    <ContextePresentation.Provider value={PRESENTATION}>
      <GardeAtelier id={id}>
        <Suspense fallback={<VueClient2D id={id} />}>
          <Atelier mode="calepinage" lectureSeuleImposee />
        </Suspense>
      </GardeAtelier>
    </ContextePresentation.Provider>
  )
}
