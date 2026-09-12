// VTA10 — BRANCHEMENT de l'app Visites sur la primitive offline de la
// plateforme (NTMOB1). Ce fichier ne contient AUCUN moteur : pas de file, pas
// de stockage, pas de politique de rejeu, pas de badge. Tout cela vit déjà
// dans `lib/offlineOutbox.js` / `lib/offlineStore.js` et dans l'unique file
// binaire (`features/installations/offline/fieldOutbox.js`, EZ8) — un deuxième
// outbox ou un deuxième compteur est INTERDIT (décision VX105).
//
// Ce qu'on branche :
//   * les MESURES (JSON) → file de module `visites` (`queueIfOffline`), dont
//     la contrepartie serveur est `offlinesync` (handler `visite.mesures`) ;
//   * les PHOTOS (binaire) → l'unique `binaryOutbox`, rejouées par l'endpoint
//     multipart existant `POST /visites/visites/<id>/photos/`.
//
// Dans les deux cas : on tente D'ABORD en ligne ; seule une panne RÉSEAU
// (aucune réponse serveur) met en file. Une erreur applicative 4xx est
// relancée — l'utilisateur doit la voir, jamais l'enterrer dans une file.
import { queueIfOffline, notifyOfflineOutboxChange } from '../../lib/offlineOutbox'
import {
  BINARY_OPS, binaryOutbox, OutboxQuotaError, requestBackgroundSync,
} from '../installations/offline/fieldOutbox'
import { compressImage } from '../../ui/file-utils'
import visitesApi from '../../api/visitesApi'

export const MODULE_VISITES = 'visites'

// Types d'op JSON — DOIVENT correspondre aux clés enregistrées côté serveur
// (`apps/offlinesync/handlers.py`).
export const VISITE_OPS = {
  MESURES: 'visite.mesures',
}

export { OutboxQuotaError }

/**
 * Enregistre les mesures d'une catégorie. En ligne : `PATCH .../mesures/` et
 * on renvoie l'agrégat serveur. Hors ligne : l'op part en file et on renvoie
 * `{ queued: true }` — l'écran le DIT, il ne fait pas semblant d'avoir
 * enregistré.
 */
export function enregistrerMesures(visiteId, categorie, valeurs) {
  return queueIfOffline(
    MODULE_VISITES,
    () => visitesApi.patchVisiteMesures(visiteId, categorie, valeurs),
    VISITE_OPS.MESURES,
    { visite: Number(visiteId), categorie, valeurs },
    { target: visiteId },
  )
}

/**
 * Envoie une photo de checklist. La photo est COMPRESSÉE avant tout (VX77/
 * NTMOB16 — `compressImage`, bord long ≤1600 px, JPEG q0.75) : c'est la même
 * compression que partout ailleurs dans l'app, jamais une deuxième recette.
 * Sur panne RÉSEAU elle rejoint la file binaire UNIQUE ; `OutboxQuotaError`
 * (file pleine / stockage saturé) remonte avec son message français prêt à
 * afficher, pour que l'échec soit VISIBLE et non silencieux.
 */
export async function envoyerPhotoVisite(visiteId, { slotCode, fichier, gpsLat, gpsLng }) {
  const compresse = await compressImage(fichier)
  try {
    const data = await visitesApi.uploadVisitePhoto(visiteId, {
      slotCode, fichier: compresse, gpsLat, gpsLng,
    })
    return { queued: false, data }
  } catch (err) {
    if (err?.response) throw err // refus applicatif : jamais filé en silence
    const bytes = await compresse.arrayBuffer()
    const clientOpId = await binaryOutbox.enqueue(
      BINARY_OPS.PHOTO_VISITE,
      { visite: Number(visiteId), slot_code: slotCode, gps_lat: gpsLat, gps_lng: gpsLng },
      {
        bytes,
        name: compresse.name || `${slotCode}.jpg`,
        type: compresse.type || 'image/jpeg',
      },
    )
    notifyOfflineOutboxChange()
    requestBackgroundSync()
    return { queued: true, clientOpId }
  }
}
