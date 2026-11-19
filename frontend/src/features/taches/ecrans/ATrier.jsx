import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « ATrier » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/ATrier')
CHARGEURS.atrier = charger
const Page = lazy(charger)

export default function ATrier() {
  return <Frontiere ecran="a-trier" titre="À trier"><Page /></Frontiere>
}
