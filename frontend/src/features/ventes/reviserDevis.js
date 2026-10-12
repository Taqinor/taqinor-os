// QJR533 (Groupe QJR5, D-QJR5-2) — UN seul geste « Réviser (nouvelle version) »
// pour la liste et le cockpit lead : avertit si un chantier est en cours, appelle
// le serveur, DIT ce qui se passe (toast) puis ouvre la V2 en Édition complète.
// Aucun masquage par rôle : le droit est porté par le serveur (IsResponsableOrAdmin).
import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { chantierEnCours } from './devisStatuts'

const MESSAGE_ECHEC = 'La révision a échoué — réessayez.'

/**
 * VNT80 — un 409 qui NOMME un autre devis : `version_remplacee` (→ `successeur`,
 * la tête de la chaîne) ou `vente_active_existante` (→ `vente_active`, la vente
 * en vigueur du lead). Rend `{conflit, code, message, successeur}` (le devis
 * nommé sous le nom `successeur`) ou `null` pour toute autre erreur.
 */
export function lireConflit(err) {
  const data = err?.response?.data
  if (err?.response?.status !== 409 || !data || typeof data !== 'object') return null
  const cible = data.successeur || data.vente_active
  if (!cible || cible.id == null) return null
  return {
    conflit: true,
    code: data.code || '',
    message: (typeof data.detail === 'string' && data.detail) || MESSAGE_ECHEC,
    successeur: { id: cible.id, reference: cible.reference || '' },
  }
}

/**
 * @param {object}   p
 * @param {object}   p.devis     ligne devis (id, reference, chantier?)
 * @param {Function} p.navigate  react-router navigate
 * @param {Function} [p.onApres] appelé après une révision réussie (rechargement)
 * @param {Function} [p.onConflit] VNT80 — reçoit `{conflit, successeur}` quand un 409
 *   nomme un autre devis : l'appelant montre l'erreur sous sa carte (sans toast)
 * @returns {Promise<object|null>} le devis V2 ; `{conflit, successeur}` sur un 409
 *   qui nomme un autre devis ; null sinon si la révision a échoué
 */
export async function reviserEtOuvrir({ devis, navigate, onApres, onConflit }) {
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
    const conflit = lireConflit(err)
    if (conflit) {
      if (onConflit) onConflit(conflit)
      else {
        toast.error(conflit.message, conflit.successeur.reference ? {
          action: {
            label: `Ouvrir ${conflit.successeur.reference}`,
            onClick: () => navigate?.(`/ventes/devis?devis=${conflit.successeur.id}`),
          },
        } : undefined)
      }
      return conflit
    }
    const data = err?.response?.data
    toast.error((typeof data?.detail === 'string' && data.detail) || MESSAGE_ECHEC)
    return null
  }
  if (onApres) onApres(nouveau)
  toast.success(`Version créée : ${nouveau?.reference ?? ''}`.trim())
  if (nouveau?.id != null) navigate(`/ventes/devis/nouveau?edit=${nouveau.id}`)
  return nouveau
}
