import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Projets » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Projets')
CHARGEURS.projets = charger
const Page = lazy(charger)

export default function Projets() {
  return <Frontiere ecran="projets" titre="Projets"><Page /></Frontiere>
}
