import { useSelector } from 'react-redux'
import { useHasPermission, useHasRole } from '../../hooks/useHasPermission'

/**
 * APAR38 — droit d'ÉCRIRE les réglages de la société, aligné sur la garde
 * serveur (`IsAdminOrResponsableTier` + `HasPermissionOrLegacy(
 * 'parametres_modifier')`, ASEC31) :
 *   - palier admin/responsable, ET
 *   - un rôle fin porte `parametres_modifier` ; un compte hérité SANS rôle fin
 *     (`role_nom` vide, aucune permission servie) garde le comportement
 *     historique du serveur (son palier suffit).
 * Un Admin RH ou un Technicien responsable voit donc Paramètres en lecture
 * seule, un Directeur/Administrateur écrit.
 */
export function useCanModifierParametres() {
  const palierEcriture = useHasRole(['admin', 'responsable'])
  const porteLeDroit = useHasPermission('parametres_modifier')
  const roleNom = useSelector((s) => s.auth.role_nom)
  return palierEcriture && (porteLeDroit || !roleNom)
}

export default useCanModifierParametres
