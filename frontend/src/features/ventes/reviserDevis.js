// QJR533 (Groupe QJR5, D-QJR5-2) — UN seul geste « Réviser (nouvelle version) »
// pour la liste et le cockpit lead : avertit si un chantier est en cours, appelle
// le serveur, DIT ce qui se passe (toast) puis ouvre la V2 en Édition complète.
// Aucun masquage par rôle : le droit est porté par le serveur (IsResponsableOrAdmin).
import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { chantierEnCours } from './devisStatuts'

const MESSAGE_ECHEC = 'La révision a échoué — réessayez.'

/**
 * @param {object}   p
 * @param {object}   p.devis     ligne devis (id, reference, chantier?)
 * @param {Function} p.navigate  react-router navigate
 * @param {Function} [p.onApres] appelé après une révision réussie (rechargement)
 * @returns {Promise<object|null>} le devis V2, ou null si la révision a échoué
 */
export async function reviserEtOuvrir({ devis, navigate, onApres }) {
  if (chantierEnCours(devis?.chantier)) {
    toast.warning(
      `Le chantier ${devis.chantier.reference} lié à ${devis.reference} est en cours — sa nomenclature est gelée.`,
    )
  }
  let nouveau
  try {
    const res = await ventesApi.reviserDevis(devis.id)
    nouveau = res?.data
  } catch (err) {
    const data = err?.response?.data
    toast.error((typeof data?.detail === 'string' && data.detail) || MESSAGE_ECHEC)
    return null
  }
  if (onApres) onApres(nouveau)
  toast.success(`Version créée : ${nouveau?.reference ?? ''}`.trim())
  if (nouveau?.id != null) navigate(`/ventes/devis/nouveau?edit=${nouveau.id}`)
  return nouveau
}
