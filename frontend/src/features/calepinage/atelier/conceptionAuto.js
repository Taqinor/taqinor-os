import crmApi from '../../../api/crmApi'

/* ACAL421 — « Conception automatique » : l'emprise OSM du bâtiment épinglé devient le pan,
   et l'optimiseur de l'atelier remplit le toit. Rien n'est enregistré ici : le pan sort par
   `serializeLayout` quand l'utilisateur enregistre le calepinage.
   Conversion : le serveur sert des `{lat, lng}` ; `ajouterPanDepuisContour` veut des
   `[lng, lat]` (l'inverse des paires `[lat, lng]` du boot du mode lead). */
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

/** Lit l'emprise du lead et pose le pan. → `{ ok, message }` ; aucun pan créé sur un refus. */
export async function conceptionAuto(leadId, builderApi) {
  let data
  try {
    data = (await crmApi.getRoofFootprint(leadId))?.data
  } catch {
    return { ok: false, message: 'Emprise du bâtiment indisponible (réseau) — réessayez ou tracez le toit.' }
  }
  const contour = contourLngLat(data?.polygon)
  if (contour.length < 3) {
    return { ok: false, message: data?.message || 'Aucune emprise de bâtiment trouvée pour ce lead.' }
  }
  const verdict = builderApi.ajouterPanDepuisContour(contour)
  return verdict.ok ? { ok: true, message: 'Contour posé : le toit est rempli.' } : { ok: false, message: verdict.motif }
}
