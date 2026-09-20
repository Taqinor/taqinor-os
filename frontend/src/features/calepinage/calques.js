/* ============================================================================
   CAL103 — LE MODÈLE PUR DES CALQUES de l'atelier (aucun React, aucune carte).
   ----------------------------------------------------------------------------
   Il porte les DEUX choses que la tâche exige d'être déterministes et testables :
     * l'ORDRE DE SUPERPOSITION (du fond vers le dessus), qui ne doit plus dépendre
       de l'ordre d'ajout des couches ;
     * la PERSISTANCE PAR UTILISATEUR de l'état (visibilité + opacité).

   Le panneau (`PanneauCalques.jsx`) ne fait que rendre ce modèle. Ces identifiants
   sont les MÊMES que `ORDRE_RENDU_CALQUES` de `apps/web/src/scripts/roofPro11/mapDraw.ts`,
   qui applique l'état sur la carte — un seul vocabulaire des deux côtés.
   ========================================================================== */

/** ORDRE DE RENDU, du FOND vers le DESSUS. Déterminé, jamais l'ordre d'ajout. */
export const ORDRE_CALQUES = [
  { id: 'imagerie', label: 'Imagerie satellite' },
  { id: 'cadastre', label: 'Parcellaire cadastral' },
  { id: 'photo', label: 'Photo calée' },
  { id: 'plan', label: 'Plan importé' },
  { id: 'trace_client', label: 'Tracé client' },
  { id: 'obstacles', label: 'Obstacles' },
  { id: 'zones', label: 'Zones (interdites / réservées / préférées)' },
  { id: 'panneaux', label: 'Panneaux' },
  { id: 'ombres', label: 'Ombres' },
  { id: 'mesures', label: 'Mesures' },
]

export const CALQUE_IDS = ORDRE_CALQUES.map((c) => c.id)

/** Index de superposition d'un calque (0 = tout au fond). -1 si inconnu. */
export function rangCalque(id) {
  return CALQUE_IDS.indexOf(id)
}

/** État par défaut : TOUT visible, opacité pleine — l'atelier d'aujourd'hui. */
export function etatCalquesParDefaut() {
  const out = {}
  for (const id of CALQUE_IDS) out[id] = { visible: true, opacite: 1 }
  return out
}

export function cleStockage(utilisateurId) {
  return `calepinage.calques.${utilisateurId ?? 'anonyme'}`
}

/** Relit l'état rangé pour CET utilisateur. Stockage absent/illisible/corrompu ⇒
 *  état par défaut, jamais une exception. Une clé inconnue est ignorée. */
export function lireEtatCalques(utilisateurId, stockage) {
  const base = etatCalquesParDefaut()
  try {
    const store = stockage ?? (typeof localStorage !== 'undefined' ? localStorage : null)
    const brut = store?.getItem(cleStockage(utilisateurId))
    if (!brut) return base
    const lu = JSON.parse(brut)
    if (!lu || typeof lu !== 'object') return base
    for (const id of CALQUE_IDS) {
      const v = lu[id]
      if (!v || typeof v !== 'object') continue
      if (typeof v.visible === 'boolean') base[id].visible = v.visible
      if (typeof v.opacite === 'number' && v.opacite >= 0 && v.opacite <= 1) base[id].opacite = v.opacite
    }
  } catch {
    return etatCalquesParDefaut()
  }
  return base
}

export function ecrireEtatCalques(utilisateurId, etat, stockage) {
  try {
    const store = stockage ?? (typeof localStorage !== 'undefined' ? localStorage : null)
    store?.setItem(cleStockage(utilisateurId), JSON.stringify(etat))
  } catch {
    /* stockage refusé : l'écran fonctionne quand même, sans mémoire */
  }
}
