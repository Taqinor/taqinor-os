import { useSelector } from 'react-redux'
import { useHasPermission } from '../../hooks/useHasPermission'

/**
 * ASTK15 (D-ASTK-2) — l'utilisateur voit-il les prix et montants d'ACHAT ?
 *
 * Miroir front de `User.can_view_buy_prices` : permission `prix_achat_voir`
 * pour un compte à rôle fin ; un compte légacy SANS codes ERP garde le
 * comportement historique (le serveur lui sert les prix). Sans ce droit, le
 * serveur RETIRE les clés de prix : l'écran affiche « — », masque les gestes
 * qui n'existent que pour les prix (PDF interne, historique, tarifs, accords)
 * et n'envoie jamais de prix.
 */
export function useVoitPrixAchat() {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const viaPermission = useHasPermission('prix_achat_voir')
  return hasFinePermissions ? viaPermission : true
}

export default useVoitPrixAchat
