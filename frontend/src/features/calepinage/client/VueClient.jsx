import { Component, Suspense, lazy, useCallback, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ContextePresentation } from '../atelier/coque/contexteCoque'
import HabillageClient from './HabillageClient'
import { AttenteScene, AvisEchec3D, AvisMoteurEchec, IconeTourner, PastilleAttente, PiedClient, PlanDessus, PuceProjet, TuilesClient } from './partiesClient'
import { useBureau, useDonneesClient, webglDisponible } from './vueClient.helpers'

/* ============================================================================
   « MONTRER AU CLIENT » AU TÉLÉPHONE (`/calepinage/:id/client`, maquette TelephoneClient).
   ----------------------------------------------------------------------------
   CE QUI EST MONTRÉ : L'ATELIER LUI-MÊME, en MODE PRÉSENTATION — le même écran
   (`ToitureDesign mode="calepinage"`, même chunk, même démarrage `useAtelierBoot`), en
   lecture seule (`lectureSeuleImposee`), sa VRAIE 3D bord à bord ; la coque masque
   tout contrôle d'édition (`ContextePresentation`) et rend autour l'habillage client
   (`HabillageClient` : puce, soleil renvoyé aux vrais contrôles, tuiles, pied).
   REPLI 2D (L7) : le toit ENREGISTRÉ vu de dessus — pendant le chargement du chunk de
   l'atelier, puis sur la scène tant que la 3D démarre ; et comme écran entier quand le
   navigateur n'a pas WebGL (la 3D ne peut pas tourner).
   J1 — LES DONNÉES SONT TENUES ICI, hors de l'atelier (document enregistré, résultat publié ; le
   contexte, celui que l'atelier a lu) : les tuiles ne dépendent pas du démarrage de la 3D, et
   « Réessayer » ne relance QUE ce qui a échoué (les lectures en échec, le démarrage de l'atelier),
   sans recharger la page ni effacer une tuile déjà montrée.
   CHIFFRES : document enregistré + résultat publié seulement ; jamais un montant.
   ========================================================================== */

// Le MÊME module que la route de l'atelier (`module.config.jsx` › AtelierCalepinage) : le chunk est partagé.
const chargerAtelier = () => import('../../../pages/ventes/ToitureDesign')

/** Le repli 2D : le toit enregistré dessiné de dessus, les tuiles et le pied (écran L7). `etat` : `attente` (la 3D se
 *  prépare), `echec` (elle n'a pas pu démarrer : « Réessayer »), `sans3d` (navigateur sans WebGL). */
function VueClient2D({ id, donnees: d, etat, onReessayer = null }) {
  const bureau = useBureau()
  return (
    <div className="cal-tel" data-testid="cal-vue-client">
      <div className="cal-client-scene" data-testid="client-scene">
        {/* ACAL1837 — l'attente de la 3D : un ciel et une silhouette, jamais le plan technique brut. */}
        {etat === 'attente' ? <AttenteScene /> : d.plan ? <PlanDessus plan={d.plan} /> : (
          <p className="cal-client-vide" data-testid="client-sans-toit">
            {d.doc.etat === 'chargement' ? 'Lecture du toit enregistré…' : 'Aucun toit enregistré pour ce calepinage.'}
          </p>
        )}
        <PuceProjet titre={d.titre} sousTitre={d.sousTitre} />
        {etat === 'echec' && <AvisEchec3D onReessayer={onReessayer} />}
        {etat === 'attente' && <PastilleAttente />}
        {etat === 'sans3d' && (
          <span className="cal-client-pastille" data-testid="client-voir-3d"><IconeTourner />Vue de dessus</span>
        )}
        {d.moteurEchec && <AvisMoteurEchec />}
      </div>
      <div className="cal-client-corps">
        <TuilesClient tuiles={d.tuiles} ville={d.ville} bureau={bureau} />
      </div>
      <PiedClient id={id} />
    </div>
  )
}

/** H6 — le chunk de l'atelier (ou du constructeur) ne se charge pas : la vue client reste, en repli 2D, et le DIT
 *  (« Réessayer ») — jamais la page d'erreur générique devant le client. */
class GardeAtelier extends Component {
  constructor(props) { super(props); this.state = { echec: false } }
  static getDerivedStateFromError() { return { echec: true } }
  render() { return this.state.echec ? this.props.repli : this.props.children }
}

export default function VueClient({ webgl, chargerMoteur = undefined }) {
  const { id } = useParams()
  const peut3d = useMemo(() => (webgl === undefined ? webglDisponible() : webgl), [webgl])
  const [contexteAtelier, setContexteAtelier] = useState(null)
  const [retard3d, setRetard3d] = useState(false)
  // Un essai = une instance de l'atelier (et de son chunk : `lazy` garde un import échoué) ; « Réessayer » en ouvre une neuve.
  const [essai, setEssai] = useState(() => ({ n: 0, Atelier: lazy(chargerAtelier) }))
  // Le contexte : celui que l'atelier a lu ; lu ici seulement sans 3D, ou quand elle tarde (la puce reste dite).
  // `chargerMoteur` (comme `webgl`) : le chargeur du moteur du toit, remplaçable ; absent = `vueClient.helpers::chargerMoteur`.
  const donnees = useDonneesClient(id, { contexte: contexteAtelier, lireContexte: !peut3d || retard3d, chargerMoteur })
  const { reessayer: relireDonnees } = donnees
  const reessayer3d = useCallback(() => {
    relireDonnees()
    setRetard3d(false)
    // Le constructeur ne démarre qu'une fois par page (`__taqinorRoofBooted`) : déjà démarré, il n'est pas relancé
    // (la vue tenue est reposée par l'habillage) ; sinon une instance neuve de l'atelier relance son démarrage.
    if (!window.__taqinorRoofBooted) setEssai((e) => ({ n: e.n + 1, Atelier: lazy(chargerAtelier) }))
  }, [relireDonnees])
  const presentation = {
    rendu: (props) => (
      <HabillageClient {...props} donnees={donnees} onContexte={setContexteAtelier} onRetard={setRetard3d}
        onReessayer={reessayer3d} />
    ),
  }
  if (!peut3d) return <VueClient2D id={id} donnees={donnees} etat="sans3d" />
  const { Atelier } = essai
  return (
    <ContextePresentation.Provider value={presentation}>
      <GardeAtelier key={essai.n} repli={<VueClient2D id={id} donnees={donnees} etat="echec" onReessayer={reessayer3d} />}>
        <Suspense fallback={<VueClient2D id={id} donnees={donnees} etat="attente" />}>
          <Atelier mode="calepinage" lectureSeuleImposee />
        </Suspense>
      </GardeAtelier>
    </ContextePresentation.Provider>
  )
}
