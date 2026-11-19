import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Projet » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Projet')
CHARGEURS.projet = charger
const Page = lazy(charger)

export default function Projet() {
  return <Frontiere ecran="projet"><Page /></Frontiere>
}
