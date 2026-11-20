import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Revue » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Revue')
CHARGEURS.revue = charger
const Page = lazy(charger)

export default function Revue() {
  return <Frontiere ecran="revue" titre="Revue de la semaine"><Page /></Frontiere>
}
