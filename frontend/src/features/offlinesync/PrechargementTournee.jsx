// NTMOB28 — déclencheur du pré-chargement matinal de la tournée.
// Monté par `Layout` (donc sur tout écran authentifié), il ne rend RIEN et ne
// fait rien du tout hors du créneau matinal, hors-ligne, ou si le
// pré-chargement du jour a déjà eu lieu sur cet appareil.
import { useEffect } from 'react'
import installationsApi from '../../api/installationsApi'
// NOTE : le module de logique s'appelle `prechargeMatinale.js` et non
// `prechargementTournee.js` — sur un FS insensible à la casse (Windows),
// `./PrechargementTournee` résoudrait vers le `.js` avant le `.jsx`.
import { readCache } from './readCache'
import {
  doitPrecharger, prechargerTournee, dernierPrechargement,
} from './prechargeMatinale'

export default function PrechargementTournee() {
  useEffect(() => {
    const maintenant = new Date()
    const jour = maintenant.toISOString().slice(0, 10)
    const decision = doitPrecharger({
      enLigne: typeof navigator === 'undefined' ? true : navigator.onLine !== false,
      heure: maintenant.getHours(),
      jour,
      dejaFait: dernierPrechargement(),
    })
    if (!decision) return
    prechargerTournee({
      // Lecture d'arrière-plan : jamais de toast si le réseau retombe.
      chargerTournee: (d) => installationsApi.getMaTournee(
        d, { suppressErrorToast: true }),
      cache: readCache,
      jour,
    })
  }, [])

  return null
}
