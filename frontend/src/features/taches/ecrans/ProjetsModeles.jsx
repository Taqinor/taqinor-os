import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « ProjetsModeles » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/ProjetsModeles')
CHARGEURS.modeles = charger
const Page = lazy(charger)

export default function ProjetsModeles() {
  return <Frontiere ecran="projets-modeles" titre="Modèles"><Page /></Frontiere>
}
