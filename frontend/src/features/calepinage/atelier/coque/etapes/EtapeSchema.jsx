import { EcranDOnglets } from '../emplacements'

/* Coque — le sous-écran « Schéma électrique » de l'étape Électrique (gabarit L0, refait par
   la lane L3 sur la maquette Schema) : cadre `plein-panneau`, le schéma unifilaire EXISTANT au
   centre. La légende et le cartouche iront dans le panneau par `<DansPanneau>`. */
export default function EtapeSchema(props) {
  return <EcranDOnglets cles={['schema']} {...props} />
}
