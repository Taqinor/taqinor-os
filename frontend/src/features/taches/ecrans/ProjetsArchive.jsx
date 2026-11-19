import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « ProjetsArchive » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/ProjetsArchive')
CHARGEURS.archive = charger
const Page = lazy(charger)

export default function ProjetsArchive() {
  return <Frontiere ecran="projets-archive" titre="Archive"><Page /></Frontiere>
}
