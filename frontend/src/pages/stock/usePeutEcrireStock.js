import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'

/* Droit d'écriture sur les écrans Stock : permission fine `stock_modifier`
   quand l'utilisateur en porte, sinon rôle administrateur / responsable. */
export default function usePeutEcrireStock() {
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  return hasFinePermissions ? canWriteViaPerm : canWriteViaRole
}
