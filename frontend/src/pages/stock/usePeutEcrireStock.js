import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'

/* Droit d'écriture sur les écrans Stock : permission fine `code` (défaut
   `stock_modifier`) quand l'utilisateur en porte, sinon rôle administrateur /
   responsable. ADRG34 — `code` permet de garder un geste sur le code de SA route. */
export default function usePeutEcrireStock(code = 'stock_modifier') {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission(code)
  const canWriteViaRole = useIsAdminOrResponsable()
  return hasFinePermissions ? canWriteViaPerm : canWriteViaRole
}
