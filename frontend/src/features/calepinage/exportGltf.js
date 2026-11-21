/* ============================================================================
   ACAL537 — EXPORT « 3D (glTF) » de l'atelier, pour un architecte.
   ----------------------------------------------------------------------------
   Sur le patron d'`exportImage.js::exporterImageHd` : ce module ne construit
   rien lui-même. Le builder (`builderApi.exporterSceneGltf`, scene3d.ts) rend la
   scène en `.glb` dans le repère LOCAL du site ; ici on nomme le fichier et on
   déclenche le téléchargement, côté navigateur. Rien n'est rangé, rien ne part
   au client, et la scène ne porte ni prix ni donnée client.
   ========================================================================== */

import { telechargerBlob } from './exportImage.js'

/** Nom du fichier : `calepinage-<id>.glb`. */
export function nomFichierGltf(reference) {
  const base = String(reference ?? '').replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'export'
  return `calepinage-${base}.glb`
}

/**
 * Demande la scène au builder et déclenche le téléchargement.
 *
 * @returns {Promise<{ok: true, nom: string} | {ok: false, motif: string}>}
 *          Jamais une exception : l'écran affiche `motif` tel quel.
 */
export async function exporterSceneGltf(builderApi, { reference, telecharger } = {}) {
  const api = builderApi?.current ?? builderApi
  if (!api || typeof api.exporterSceneGltf !== 'function') {
    return { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' }
  }
  let rendu = null
  try {
    rendu = await api.exporterSceneGltf()
  } catch {
    return { ok: false, motif: 'L’export 3D a échoué sur ce navigateur.' }
  }
  if (!rendu || !rendu.blob) return { ok: false, motif: 'Scène non rendable ici — aucun fichier produit.' }
  const nom = nomFichierGltf(reference)
  try {
    ;(telecharger ?? telechargerBlob)(rendu.blob, nom)
  } catch {
    return { ok: false, motif: 'Téléchargement refusé par le navigateur.' }
  }
  return { ok: true, nom }
}
