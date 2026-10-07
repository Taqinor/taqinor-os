/* ============================================================================
   Lot 2 critique #32 — DEUX 409 très différents sur une écriture de conception :

   * `{code: 'document_modifie'}` (ou 428, jeton absent) : le document a changé
     AILLEURS — on relit et on recommence ;
   * le VERROU (devis accepté, calepinage archivé) : `{roof_layout: [motif]}`
     (ou un autre champ, ou `{detail}`) — le motif du SERVEUR se lit tel quel,
     jamais « a changé ailleurs » (relire n'y changerait rien).
   ========================================================================== */

/** Le message à montrer pour un verrou dont le serveur n'a rien dit. */
export const MOTIF_VERROU_PAR_DEFAUT = 'Conception en lecture seule : elle ne peut pas être modifiée.'

/** Phrase de la lecture seule passée par l'atelier (prop `lectureSeule`). */
export const RAISON_LECTURE_SEULE = 'Lecture seule : la conception ne peut pas être modifiée.'

/**
 * `null` quand l'erreur n'est pas un conflit d'écriture ; sinon
 * `{documentModifie: true}` ou `{documentModifie: false, motif}`.
 */
export function lireConflit(erreur) {
  const statut = erreur?.response?.status
  const data = erreur?.response?.data
  if (statut === 428) return { documentModifie: true }
  if (statut !== 409) return null
  if (data?.code === 'document_modifie') return { documentModifie: true }
  if (data && typeof data === 'object') {
    const premier = [data.roof_layout, data.detail, ...Object.values(data)]
      .map((v) => (Array.isArray(v) ? v[0] : v))
      .find((v) => typeof v === 'string' && v.trim())
    if (premier) return { documentModifie: false, motif: premier.trim() }
  }
  return { documentModifie: false, motif: MOTIF_VERROU_PAR_DEFAUT }
}
