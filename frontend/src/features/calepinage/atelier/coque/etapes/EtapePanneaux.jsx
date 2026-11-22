import { EcranDOnglets } from '../emplacements'

/* Coque — l'écran guidé de l'étape « Panneaux » (gabarit L0, refait par la lane L2 sur la
   maquette Panneaux) : le contenu EXISTANT de l'étape — les fiches d'équipements (onglet
   `fiches`). La pose du constructeur (`BuilderPose`) reste montée par la coque sous cet écran. */
export default function EtapePanneaux(props) {
  return <EcranDOnglets cles={['fiches']} {...props} />
}
