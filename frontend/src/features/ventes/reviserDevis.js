// QJR533 (Groupe QJR5, D-QJR5-2) — UN seul geste « Réviser (nouvelle version) »
// pour la liste et le cockpit lead : avertit si un chantier est en cours, appelle
// le serveur, DIT ce qui se passe (toast) puis ouvre la V2 en Édition complète.
// Aucun masquage par rôle : le droit est porté par le serveur (IsResponsableOrAdmin).
import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { chantierEnCours } from './devisStatuts'

const MESSAGE_ECHEC = 'La révision a échoué — réessayez.'

/**
 * VNT80 — un refus serveur qui NOMME un autre devis (forme unique VNT24 :
 * `version_remplacee.successeur` ou `vente_active_existante.vente_active`,
 * `{id, reference}`) ⇒ `{code, conflit, successeur}` ; sinon `null`. Lit le
 * CORPS (son `code`), jamais le statut HTTP.
 */
export function conflitDevis(data) {
  if (!data || typeof data !== 'object') return null
  const cible = data.code === 'vente_active_existante' ? data.vente_active : data.successeur
  if (!cible || cible.id == null) return null
  return {
    code: data.code || '',
    conflit: (typeof data.detail === 'string' && data.detail) || MESSAGE_ECHEC,
    successeur: { id: cible.id, reference: cible.reference || `#${cible.id}` },
  }
}

/**
 * @param {object}   p
 * @param {object}   p.devis     ligne devis (id, reference, chantier?)
 * @param {Function} p.navigate  react-router navigate
 * @param {Function} [p.onApres] appelé après une révision réussie (rechargement)
 * @param {Function} [p.onConflit] VNT80 — reçoit `{conflit, successeur}` quand le
 *   serveur nomme un autre devis : l'appelant montre l'erreur sous la carte et
 *   propose « Ouvrir <ref> » (aucun toast alors)
 * @returns {Promise<object|null>} le devis V2 ; `{conflit, successeur}` sur un
 *   refus qui nomme un autre devis ; null sur tout autre échec
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
    const data = err?.response?.data
    const c = conflitDevis(data)
    if (c && onConflit) {
      onConflit({ conflit: c.conflit, successeur: c.successeur })
      return { conflit: c.conflit, successeur: c.successeur }
    }
    toast.error((typeof data?.detail === 'string' && data.detail) || MESSAGE_ECHEC)
    return c ? { conflit: c.conflit, successeur: c.successeur } : null
  }
  if (onApres) onApres(nouveau)
  toast.success(`Version créée : ${nouveau?.reference ?? ''}`.trim())
  if (nouveau?.id != null) navigate(`/ventes/devis/nouveau?edit=${nouveau.id}`)
  return nouveau
}
