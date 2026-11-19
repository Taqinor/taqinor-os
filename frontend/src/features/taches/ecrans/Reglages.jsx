import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Reglages » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Reglages')
CHARGEURS.reglages = charger
const Page = lazy(charger)

export default function Reglages() {
  return <Frontiere ecran="reglages" titre="Réglages"><Page /></Frontiere>
}
