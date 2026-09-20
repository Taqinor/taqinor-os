/* ============================================================================
   CAL180 — EXPORT « IMAGE HD » du calepinage.
   ----------------------------------------------------------------------------
   L'affiche client existante (`devis/<pk>/roof-image`, `Devis.roof_image`) est
   postée par le navigateur à la RÉSOLUTION D'ÉCRAN. Ici l'atelier demande au
   builder un rendu HORS ÉCRAN à 2× ou 3× (`renderImageHd`, `scene3d.ts`) et
   remet le PNG à l'utilisateur — CÔTÉ NAVIGATEUR, sans passer par le serveur :
   aucun second magasin d'images n'est créé et l'affiche client reste INCHANGÉE.

   Ce module ne rend rien lui-même : il orchestre, nomme le fichier et déclenche
   le téléchargement. Le facteur RÉELLEMENT obtenu vient du builder (il rabaisse
   quand le plafond de taille l'impose) — on l'affiche, on ne le suppose pas.
   ========================================================================== */

/** Facteurs proposés par l'atelier, les mêmes que `HD_SCALES` côté builder. */
export const FACTEURS_HD = [2, 3]

/** Nom de fichier : jamais deux exports qui s'écrasent, et la taille est dans le nom. */
export function nomFichierHd(reference, width, height) {
  const base = String(reference ?? 'calepinage').replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'calepinage'
  return `${base}-${width}x${height}.png`
}

/**
 * Demande le rendu HD et déclenche le téléchargement.
 *
 * @returns {Promise<{ok: true, width: number, height: number, scale: number, nom: string}
 *                  | {ok: false, motif: string}>}
 *          Jamais une exception : l'écran affiche `motif` tel quel.
 */
export async function exporterImageHd(builderApi, { scale = 2, reference, telecharger } = {}) {
  const api = builderApi?.current ?? builderApi
  if (!api || typeof api.renderImageHd !== 'function') {
    return { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' }
  }
  let rendu = null
  try {
    rendu = await api.renderImageHd(scale)
  } catch {
    return { ok: false, motif: 'Le rendu haute résolution a échoué sur ce navigateur.' }
  }
  if (!rendu || !rendu.blob) {
    return { ok: false, motif: 'Scène non rendable ici (3D indisponible) — aucune image produite.' }
  }
  const nom = nomFichierHd(reference, rendu.width, rendu.height)
  try {
    ;(telecharger ?? telechargerBlob)(rendu.blob, nom)
  } catch {
    return { ok: false, motif: 'Téléchargement refusé par le navigateur.' }
  }
  return { ok: true, width: rendu.width, height: rendu.height, scale: rendu.scale, nom }
}

/** Téléchargement par défaut (remplaçable en test : aucun DOM requis là-bas). */
export function telechargerBlob(blob, nom) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nom
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
