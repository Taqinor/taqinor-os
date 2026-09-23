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

/* ============================================================================
   CALX320 — LE DIAGRAMME DE PERTES : MÊME GESTE, SOURCE DIFFÉRENTE.
   ----------------------------------------------------------------------------
   La carte de chaleur ci-dessus vient de l'atelier 3D (``builderApi``), qui
   n'est monté que sur l'onglet 3D — indisponible depuis le panneau
   Documents. Le diagramme de pertes, lui, a déjà un SVG autonome rendu par
   le SERVEUR (``GET diagramme-pertes.svg/``, CALX308, `services
   /diagramme_pertes.py` — la MÊME cascade que la pièce imprimable, jamais un
   second calcul ici) : on le récupère, on le RASTÉRISE ICI (D-CAL10, aucun
   rasteriseur SVG côté serveur — même limite que `sorties/planche_png`,
   CAL175), puis on le dépose comme n'importe quelle autre image.
   ========================================================================== */

/** Le corps d'un refus de requête BLOB (`diagrammePertesSvg`,
    `responseType: 'blob'`) en `[{champ, message}]` — MÊME régime que
    `PanneauDocuments.jsx::erreurDeTelechargement` (le corps d'erreur voyage
    lui aussi en blob, il faut le relire en texte avant de le parser) : le
    CHAMP fautif reste NOMMÉ, jamais réduit à une phrase anonyme. Sans
    réponse du tout (réseau coupé), un motif générique — jamais un plantage
    muet. */
async function erreursDeRefusBlob(erreur) {
  const donnees = erreur?.response?.data
  let corps = donnees
  if (typeof Blob !== 'undefined' && donnees instanceof Blob) {
    try {
      corps = JSON.parse(await donnees.text())
    } catch {
      return [{ champ: '', message: 'Réponse du serveur illisible.' }]
    }
  }
  if (corps && typeof corps === 'object') {
    return Object.entries(corps).map(([champ, message]) => ({ champ, message: String(message) }))
  }
  return [{ champ: '', message: 'Le serveur est resté injoignable.' }]
}

/**
 * Un texte SVG -> ``Blob`` PNG, rastérisé dans un ``<canvas>`` hors écran
 * (même patron que ``SchemaUnifilairePanel.jsx::exporterSchemaPng``, mais
 * renvoie le Blob au lieu de le télécharger : ce Blob part vers
 * ``deposerImageDocument`` ci-dessus, pas le disque). Un échec de
 * rastérisation revient en REJET avec un motif affichable — jamais une
 * exception qui casserait l'écran.
 */
export function svgTexteEnPng(svgTexte) {
  return new Promise((resolve, reject) => {
    let url
    try {
      url = URL.createObjectURL(new Blob([svgTexte], { type: 'image/svg+xml;charset=utf-8' }))
    } catch (err) {
      reject(err)
      return
    }
    const img = new Image()
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas')
        canvas.width = img.width || 1
        canvas.height = img.height || 1
        const ctx = canvas.getContext('2d')
        if (!ctx) throw new Error('Contexte de dessin 2D indisponible sur ce navigateur.')
        ctx.drawImage(img, 0, 0)
        canvas.toBlob((blobPng) => {
          URL.revokeObjectURL(url)
          if (!blobPng) { reject(new Error('Rendu PNG indisponible sur ce navigateur.')); return }
          resolve(blobPng)
        }, 'image/png')
      } catch (err) {
        URL.revokeObjectURL(url)
        reject(err)
      }
    }
    img.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Le diagramme n’a pas pu être rastérisé sur ce navigateur.'))
    }
    img.src = url
  })
}

/**
 * Dépose le diagramme de pertes comme image ``genre: 'sankey'`` : récupère
 * le SVG autonome du SERVEUR, le rastérise dans CE navigateur, puis le
 * dépose. Un calepinage sans résultat refuse déjà côté serveur (`GET
 * diagramme-pertes.svg/` rend 400 en NOMMANT le champ) — le motif remonte
 * tel quel, même régime que ``deposerCarteDeChaleur`` ci-dessus.
 */
export async function deposerDiagrammeDePertes(calepinageId) {
  if (!calepinageId) {
    return { ok: false, motif: 'Calepinage inconnu — rien à déposer.' }
  }
  let svgTexte
  try {
    const reponse = await calepinageApi.calepinages.diagrammePertesSvg(calepinageId)
    svgTexte = await reponse.data.text()
  } catch (erreur) {
    const erreurs = await erreursDeRefusBlob(erreur)
    return { ok: false, motif: erreurs[0]?.message || 'Le serveur a refusé la demande.', erreurs }
  }
  if (!svgTexte) {
    return { ok: false, motif: 'Diagramme de pertes indisponible (réponse vide).' }
  }
  let blob
  try {
    blob = await svgTexteEnPng(svgTexte)
  } catch (err) {
    return { ok: false, motif: err?.message || 'Rendu du diagramme impossible sur ce navigateur.' }
  }
  return deposerImageDocument(calepinageId, { genre: 'sankey', blob })
}
