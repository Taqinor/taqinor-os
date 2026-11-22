import { EcranDOnglets } from '../emplacements'

/* Coque — l'écran guidé de l'étape « Toit » (gabarit L0, refait par la lane L1 sur la
   maquette Main) : le contenu EXISTANT de l'étape — la saisie de la pente (onglet `pente`).
   Les commandes du constructeur (formes, réglages du pan, obstacles) restent montées par la
   coque sous cet écran (`BuilderOutils` / `BuilderToit`), jamais ici : elles ne se démontent pas. */
export default function EtapeToit(props) {
  return <EcranDOnglets cles={['pente']} {...props} />
}
