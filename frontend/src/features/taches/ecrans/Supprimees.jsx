import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Supprimees » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Supprimees')
CHARGEURS.supprimees = charger
const Page = lazy(charger)

export default function Supprimees() {
  return <Frontiere ecran="supprimees" titre="Supprimées"><Page /></Frontiere>
}
