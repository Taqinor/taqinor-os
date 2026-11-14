// NTMOB28 — déclencheur du pré-chargement matinal de la tournée.
// Monté par `Layout` (donc sur tout écran authentifié), il ne rend RIEN et ne
// fait rien du tout hors du créneau matinal, hors-ligne, ou si le
// pré-chargement du jour a déjà eu lieu sur cet appareil.
// ADRG122 — ni pour un compte auquel le serveur refuse la tournée (Commercial…) :
// l'appel partait sur tout écran, chaque matin, et revenait en 403.
import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import installationsApi from '../../api/installationsApi'
import { useCanLireInterventions } from '../../hooks/useHasPermission'
// NOTE : le module de logique s'appelle `prechargeMatinale.js` et non
// `prechargementTournee.js` — sur un FS insensible à la casse (Windows),
// `./PrechargementTournee` résoudrait vers le `.js` avant le `.jsx`.
import { readCache } from './readCache'
import {
  doitPrecharger, prechargerTournee, dernierPrechargement,
} from './prechargeMatinale'
import { todayLocalIso } from '../../lib/dateLocale'

export default function PrechargementTournee() {
  // Session ouverte ET droit lu sur le profil servi par `/auth/me/` (le crochet
  // dit non tant que ce profil n'est pas là).
  const sessionOuverte = useSelector((s) => s.auth.isAuthenticated)
  const peutLireTournee = useCanLireInterventions()

  useEffect(() => {
    if (!sessionOuverte || !peutLireTournee) return
    const maintenant = new Date()
    const jour = todayLocalIso(maintenant)
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
  }, [sessionOuverte, peutLireTournee])

  return null
}
