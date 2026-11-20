import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Recherche » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Recherche')
CHARGEURS.recherche = charger
const Page = lazy(charger)

export default function Recherche() {
  return <Frontiere ecran="recherche" titre="Recherche"><Page /></Frontiere>
}
