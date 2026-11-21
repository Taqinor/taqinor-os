import crmApi from '../../../api/crmApi'

/* ACAL421 — « Conception automatique » : l'emprise OSM du bâtiment épinglé devient le pan,
   et l'optimiseur de l'atelier remplit le toit. Rien n'est enregistré ici : le pan sort par
   `serializeLayout` quand l'utilisateur enregistre le calepinage.
   Décision fondateur du 21/11 : la recherche tourne en TÂCHE DE FOND (Overpass peut mettre
   30 s) — POST lance, puis le statut est relu toutes les 2 s, 90 s au plus.
   Conversion : le serveur sert des `{lat, lng}` ; `ajouterPanDepuisContour` veut des
   `[lng, lat]` (l'inverse des paires `[lat, lng]` du boot du mode lead). */
export const MSG_EN_COURS = 'Recherche du bâtiment en cours…'
export const INTERVALLE_MS = 2000
export const DUREE_MAX_MS = 90000

export function contourLngLat(polygon) {
  if (!Array.isArray(polygon)) return []
  return polygon
    .map((p) => [Number(p?.lng), Number(p?.lat)])
    .filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat))
}

/** Un pan tracé (≥ 3 sommets) existe déjà dans l'atelier : jamais écrasé, bouton absent. */
export function aDejaUnPan(builderApi) {
  const zones = builderApi?.serializeLayout?.()?.zones
  return Array.isArray(zones) && zones.some((z) => Array.isArray(z?.vertices) && z.vertices.length >= 3)
}

const attendreDefaut = (ms) => new Promise((resolve) => { setTimeout(resolve, ms) })
const messageServeur = (err, repli) => err?.response?.data?.detail || err?.response?.data?.message || repli

/** Lance la recherche, suit son statut, pose le pan. → `{ ok, message }` ; aucun pan sur un refus.
 *  `attendre` est injectable (tests : aucune vraie pause). */
export async function conceptionAuto(leadId, builderApi, { attendre = attendreDefaut } = {}) {
  let data
  try {
    data = (await crmApi.lancerRechercheEmprise(leadId))?.data
    for (let ecoule = 0; data?.statut === 'en_cours'; ecoule += INTERVALLE_MS) {
      if (ecoule >= DUREE_MAX_MS) {
        return { ok: false, message: 'La recherche du bâtiment prend trop de temps — réessayez ou tracez le toit.' }
      }
      await attendre(INTERVALLE_MS)
      data = (await crmApi.getRechercheEmprise(data.job_id))?.data
    }
  } catch (err) {
    return { ok: false, message: messageServeur(err, 'Emprise du bâtiment indisponible (réseau) — réessayez ou tracez le toit.') }
  }
  const contour = contourLngLat(data?.polygon)
  if (data?.statut !== 'pret' || contour.length < 3) {
    return { ok: false, message: data?.message || 'Aucune emprise de bâtiment trouvée pour ce lead.' }
  }
  const verdict = builderApi.ajouterPanDepuisContour(contour)
  return verdict.ok ? { ok: true, message: 'Contour posé : le toit est rempli.' } : { ok: false, message: verdict.motif }
}
