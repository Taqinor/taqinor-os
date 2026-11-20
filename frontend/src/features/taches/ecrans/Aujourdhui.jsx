import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Aujourdhui » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Aujourdhui')
CHARGEURS.aujourdhui = charger
const Page = lazy(charger)

export default function Aujourdhui() {
  return <Frontiere ecran="aujourdhui" titre="Aujourd'hui"><Page /></Frontiere>
}
