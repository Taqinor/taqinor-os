/* ACAL896 — « Vidéo 10 s » : une orbite de la scène enregistrée dans le navigateur, que la
   commerciale envoie elle-même par WhatsApp (D-ACAL-38 b : jamais de prix, hors /proposal).
   Même patron que `exportImage.js::exporterImageHd` : on orchestre, on nomme, on télécharge ;
   rien n'est posté ni rangé. Jamais une exception : l'écran affiche `motif` tel quel. */

import { telechargerBlob } from './exportImage.js'

/** Nom de fichier : `<reference>-orbite.<mp4|webm>`, l'extension suit le format RÉELLEMENT enregistré. */
export function nomFichierOrbite(reference, extension) {
  const base = String(reference ?? 'calepinage').replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'calepinage'
  return `${base}-orbite.${extension}`
}

/**
 * @returns {Promise<{ok: true, nom: string} | {ok: false, motif: string}>}
 */
export async function exporterVideoOrbite(builderApi, { reference, telecharger, surProgres } = {}) {
  const enregistrer = builderApi?.current?.enregistrerOrbite
  if (typeof enregistrer !== 'function') return { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' }
  let res
  try {
    res = await enregistrer({ surProgres })
  } catch {
    return { ok: false, motif: 'L’enregistrement vidéo a échoué sur ce navigateur.' }
  }
  if (!res?.ok) return { ok: false, motif: res?.motif || 'Enregistrement vidéo indisponible — aucun fichier produit.' }
  const nom = nomFichierOrbite(reference, res.extension)
  try {
    ;(telecharger ?? telechargerBlob)(res.blob, nom)
  } catch {
    return { ok: false, motif: 'Téléchargement refusé par le navigateur.' }
  }
  return { ok: true, nom }
}
