import { lazy } from 'react'

import Frontiere from './Frontiere'
import { CHARGEURS } from './precharger'

// L'écran « Agenda » : son morceau, sa frontière de chargement dans le module (R4-41), son chargeur de préchargement.
const charger = () => import('../../../pages/taches/Agenda')
CHARGEURS.agenda = charger
const Page = lazy(charger)

export default function Agenda() {
  return <Frontiere ecran="agenda" titre="Agenda" pleine><Page /></Frontiere>
}
