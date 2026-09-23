import calepinageApi from '../../../api/calepinageApi'

/* ============================================================================
   CALX302 — DÉPOSER UNE IMAGE PRODUITE PAR LE NAVIGATEUR.
   ----------------------------------------------------------------------------
   Aucun rasteriseur SVG n'est installé côté serveur (weasyprint 62.3 n'a plus
   de sortie PNG) — même limite que `sorties/planche_png` (CAL175). Une carte
   de chaleur d'ombrage, un diagramme de pertes ou un rendu 3D ne peuvent donc
   être imprimés dans une pièce PDF QUE si le NAVIGATEUR les a déjà rendus et
   les dépose ici : `POST calepinages/<pk>/image-document/`
   (`{genre, fichier}` — `services/images_document.py`, genre parmi une
   énumération FERMÉE : `ombrage`, `sankey`, `plan3d`).

   `fichier` voyage en DATA-URL BASE64 (le corps JSON du contrat
   `calepinage_documents.json::publication_image`) — jamais un multipart : le
   serveur décode l'un ou l'autre, mais rester sur UNE seule forme évite deux
   chemins à maintenir côté écran.
   ========================================================================== */

/** Un ``Blob`` -> data-URL base64 (``data:<mime>;base64,...``). */
export function blobEnDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const lecteur = new FileReader()
    lecteur.onload = () => resolve(String(lecteur.result || ''))
    lecteur.onerror = () => reject(lecteur.error || new Error('Lecture du fichier impossible.'))
    lecteur.readAsDataURL(blob)
  })
}

/**
 * Dépose ``blob`` comme image ``genre`` du calepinage. Jamais une exception :
 * l'écran affiche ``motif`` tel quel (même patron que ``exportImage.js``).
 *
 * @returns {Promise<{ok: true, genre: string, attachment: number, deposeLe: string}
 *                  | {ok: false, motif: string, erreurs?: Array<{champ: string, message: string}>}>}
 */
export async function deposerImageDocument(calepinageId, { genre, blob }) {
  if (!calepinageId) {
    return { ok: false, motif: 'Calepinage inconnu — rien à déposer.' }
  }
  if (!blob) {
    return { ok: false, motif: 'Aucune image à déposer.' }
  }
  let fichier
  try {
    fichier = await blobEnDataUrl(blob)
  } catch {
    return { ok: false, motif: 'Encodage de l’image impossible sur ce navigateur.' }
  }
  try {
    const reponse = await calepinageApi.calepinages.deposerImageDocument(calepinageId, { genre, fichier })
    return {
      ok: true,
      genre: reponse.data.genre,
      attachment: reponse.data.attachment,
      deposeLe: reponse.data.depose_le,
    }
  } catch (erreur) {
    const donnees = erreur?.response?.data
    if (donnees && typeof donnees === 'object') {
      const erreurs = Object.entries(donnees).map(([champ, message]) => ({ champ, message: String(message) }))
      return { ok: false, motif: erreurs[0]?.message || 'Le serveur a refusé le dépôt.', erreurs }
    }
    return { ok: false, motif: 'Le serveur est resté injoignable.' }
  }
}

/**
 * Dépose la carte de chaleur ACTIVE de l'atelier 3D — appelle
 * ``builderApi.renderImageHd(2)`` (même rendu hors écran que
 * ``exportImage.js``), puis ``deposerImageDocument(..., genre: 'ombrage')``.
 */
export async function deposerCarteDeChaleur(calepinageId, builderApi, { scale = 2 } = {}) {
  const api = builderApi?.current ?? builderApi
  if (!api || typeof api.renderImageHd !== 'function') {
    return { ok: false, motif: 'Outil non prêt — ouvrez la conception puis réessayez.' }
  }
  let rendu = null
  try {
    rendu = await api.renderImageHd(scale)
  } catch {
    return { ok: false, motif: 'Le rendu de la carte de chaleur a échoué sur ce navigateur.' }
  }
  if (!rendu || !rendu.blob) {
    return { ok: false, motif: 'Scène non rendable ici (3D indisponible) — aucune carte produite.' }
  }
  return deposerImageDocument(calepinageId, { genre: 'ombrage', blob: rendu.blob })
}
