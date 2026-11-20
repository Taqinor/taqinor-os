import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Rythme » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Rythme')
CHARGEURS.rythme = charger
const Page = lazy(charger)

export default function Rythme() {
  return <Frontiere ecran="rythme" titre="Mon rythme"><Page /></Frontiere>
}
