/* AOF83 — CONTRAT DE COORDONNÉES de l'atelier Toiture.
   ============================================================================
   SOLMVP15 — ce module vivait dans l'atelier Toiture de l'app d'appels d'offres.
   Cette app sort du produit ; la conversion repère local ↔ géographique est, elle,
   la géométrie de TOITURE du produit (le tracé et la photo de toit du CRM la
   consomment). Elle est donc rapatriée ici, à la ligne près — mêmes exports, même
   contrat d'axes, mêmes levées sur une paire nue. Rien n'est recodé : un second
   convertisseur produirait, un jour, deux géométries.
   ----------------------------------------------------------------------------
   ORDRE DES AXES — DÉCLARÉ, JAMAIS DEVINÉ.
   ----------------------------------------------------------------------------
   Le dépôt porte les DEUX ordres, et c'est un bug latent identifié :
     • le lecteur de cartes manipule des `LngLat = [lng, lat]` en interne ;
     • `roof_outline` du lead CRM (et `bootCaptureOnly.onCaptureChange.outline`)
       est en `[lat, lng]`.
   Un tableau de deux nombres ne dit PAS lequel des deux il est. Ce module refuse
   donc toute paire dont l'ordre n'est pas déclaré : soit on passe un objet nommé
   (`{ lng, lat }`), soit on passe `ORDRE_LNGLAT` / `ORDRE_LATLNG` explicitement.
   Une paire nue sans ordre lève — c'est voulu, et c'est testé.

   NOMS DE CHAMPS — également déclaratifs :
     • `origine_lnglat` : l'origine du repère local, TOUJOURS [lng, lat] ;
     • `azimut_deg`     : orientation de l'axe +y local, en degrés depuis le NORD
                          géographique, sens horaire (azimut au sens topographe) ;
     • `sommets_m`      : sommets en MÈTRES locaux { x, y } — x vers la droite du
                          repère, y vers le haut (ENU tourné de l'azimut).
   Aucun champ ne s'appelle « coords », « points » ou « xy » : un nom neutre est
   exactement ce qui a produit l'inversion qu'on corrige ici.

   PROJECTION (ACAL281) : plan tangent local (ENU) sur la SPHÈRE de rayon
   R = 6 378 137 m — LA convention de l'atelier, d'apps/web (roof.ts) et du
   serveur (core/calepinage/geo.py) : x = Δlng·R·cos(lat0), y = Δlat·R (en
   radians). Choix de cohérence (une seule aire du même tracé partout), pas de
   précision ; l'aller-retour reste l'inverse algébrique exact. */

/** Rayon de la sphère (m) — MÊME constante que core/calepinage/geo.py. */
export const RAYON_TERRE_M = 6378137.0
const RAD = Math.PI / 180

export const ORDRE_LNGLAT = 'lnglat'
export const ORDRE_LATLNG = 'latlng'

/**
 * Normalise une paire en `[lng, lat]`.
 * @param {[number,number]|{lng:number,lat:number}} paire
 * @param {'lnglat'|'latlng'} [ordre] OBLIGATOIRE pour un tableau ; interdit de
 *        l'omettre — une paire nue est ambiguë et lève.
 * @returns {[number, number]} `[lng, lat]`, dans CET ordre.
 */
export function versLngLat(paire, ordre) {
  if (paire && typeof paire === 'object' && !Array.isArray(paire)) {
    const lng = Number(paire.lng ?? paire.longitude)
    const lat = Number(paire.lat ?? paire.latitude)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      throw new TypeError('Point invalide : `lng` et `lat` doivent être des nombres.')
    }
    return controler([lng, lat])
  }
  if (!Array.isArray(paire) || paire.length !== 2) {
    throw new TypeError('Point invalide : attendu [a, b] ou { lng, lat }.')
  }
  if (ordre !== ORDRE_LNGLAT && ordre !== ORDRE_LATLNG) {
    throw new TypeError(
      "Ordre des axes non déclaré : passez ORDRE_LNGLAT ('lnglat') ou ORDRE_LATLNG " +
        "('latlng'). Une paire de nombres nue est ambiguë — c'est exactement " +
        'l’inversion lng/lat que ce module existe pour empêcher.',
    )
  }
  const a = Number(paire[0])
  const b = Number(paire[1])
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    throw new TypeError('Point invalide : les deux composantes doivent être des nombres.')
  }
  return controler(ordre === ORDRE_LNGLAT ? [a, b] : [b, a])
}

/* Contrôle de domaine : une latitude hors [-90, 90] signale presque toujours un
   ordre déclaré à l'envers. On le dit franchement plutôt que de projeter du faux. */
function controler([lng, lat]) {
  if (lat < -90 || lat > 90) {
    throw new RangeError(
      `Latitude hors domaine (${lat}) : l'ordre des axes déclaré est probablement inversé.`,
    )
  }
  if (lng < -180 || lng > 180) {
    throw new RangeError(`Longitude hors domaine (${lng}).`)
  }
  return [lng, lat]
}

/** Sérialise `[lng, lat]` dans l'ordre demandé (pour rendre au CRM ou au tool). */
export function depuisLngLat([lng, lat], ordre) {
  if (ordre === ORDRE_LATLNG) return [lat, lng]
  if (ordre === ORDRE_LNGLAT) return [lng, lat]
  throw new TypeError('Ordre des axes non déclaré en sortie (ORDRE_LNGLAT | ORDRE_LATLNG).')
}

/**
 * Repère local d'une toiture. `origine_lnglat` est stocké avec la toiture, tout
 * comme `azimut_deg` : sans eux, des mètres locaux ne veulent plus rien dire.
 */
export function creerRepere({ origine_lnglat, azimut_deg = 0, ordre } = {}) {
  const [lng0, lat0] = versLngLat(origine_lnglat, ordre ?? ORDRE_LNGLAT)
  const a = Number(azimut_deg)
  if (!Number.isFinite(a)) throw new TypeError('`azimut_deg` doit être un nombre.')
  return {
    origine_lnglat: [lng0, lat0],
    azimut_deg: a,
    _cosLat0: Math.cos(lat0 * RAD),
  }
}

/**
 * `[lng, lat]` → mètres locaux `{ x, y }`.
 * @param {'lnglat'|'latlng'} [ordre] requis si `point` est un tableau.
 */
export function lngLatVersMetres(repere, point, ordre) {
  const [lng, lat] = versLngLat(point, ordre)
  const [lng0, lat0] = repere.origine_lnglat
  const est = (lng - lng0) * RAD * RAYON_TERRE_M * repere._cosLat0
  const nord = (lat - lat0) * RAD * RAYON_TERRE_M
  const a = repere.azimut_deg * RAD
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  // +y local = azimut `a` (depuis le Nord, sens horaire) ; +x local = a + 90°.
  return { x: est * cos - nord * sin, y: est * sin + nord * cos }
}

/** Mètres locaux `{ x, y }` → `[lng, lat]` (l'inverse exact du précédent). */
export function metresVersLngLat(repere, { x, y }) {
  const a = repere.azimut_deg * RAD
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const est = Number(x) * cos + Number(y) * sin
  const nord = -Number(x) * sin + Number(y) * cos
  const [lng0, lat0] = repere.origine_lnglat
  const lat = lat0 + nord / RAYON_TERRE_M / RAD
  const lng = lng0 + est / (RAYON_TERRE_M * repere._cosLat0) / RAD
  return [lng, lat]
}

/** Contour géographique → `sommets_m`. L'ordre des axes du contour est DÉCLARÉ. */
export function contourVersSommetsM(repere, contour, ordre) {
  if (!Array.isArray(contour)) return []
  return contour.map((p) => lngLatVersMetres(repere, p, ordre))
}

/** `sommets_m` → contour géographique dans l'ordre d'axes DÉCLARÉ en sortie. */
export function sommetsMVersContour(repere, sommetsM, ordre) {
  if (!Array.isArray(sommetsM)) return []
  return sommetsM.map((s) => depuisLngLat(metresVersLngLat(repere, s), ordre))
}

/* ════════════════════════════════════════════════════════════════════════════
   GÉOMÉTRIE PLANE, en mètres locaux — le vocabulaire commun de l'atelier
   (tracé, zones, enveloppes). Tout est exprimé en mètres : aucune de ces
   fonctions ne connaît les pixels ni les degrés.
   ════════════════════════════════════════════════════════════════════════════ */

/** Aire signée (positive = sens trigonométrique). */
export function aireSignee(sommets) {
  if (!Array.isArray(sommets) || sommets.length < 3) return 0
  let s = 0
  for (let i = 0; i < sommets.length; i += 1) {
    const p = sommets[i]
    const q = sommets[(i + 1) % sommets.length]
    s += Number(p.x) * Number(q.y) - Number(q.x) * Number(p.y)
  }
  return s / 2
}

/** Aire en m² (toujours positive). */
export function aireM2(sommets) {
  return Math.abs(aireSignee(sommets))
}

/** Périmètre en m (polygone fermé). */
export function perimetreM(sommets) {
  if (!Array.isArray(sommets) || sommets.length < 2) return 0
  let p = 0
  for (let i = 0; i < sommets.length; i += 1) {
    const a = sommets[i]
    const b = sommets[(i + 1) % sommets.length]
    p += Math.hypot(Number(b.x) - Number(a.x), Number(b.y) - Number(a.y))
  }
  return p
}

// ACAL77 — `segmentsSeCroisent` / `contourSeCroise` (et leurs aides `orientation` /
// `surSegment`) sont SUPPRIMÉS : sans appelant de production (seule la copie parquée AO les
// utilisait), ils doublaient la garde unique de l'atelier, `lib/roof.ts::isSimplePolygon`,
// qui protège désormais aussi le glissé de sommet (obstaclesUi.ts::doVertexMove).

/** Un point est-il dans le polygone ? (lancer de rayon, mètres locaux) */
export function pointDansPolygone(point, sommets) {
  if (!Array.isArray(sommets) || sommets.length < 3) return false
  let dedans = false
  for (let i = 0, j = sommets.length - 1; i < sommets.length; j = i, i += 1) {
    const xi = Number(sommets[i].x)
    const yi = Number(sommets[i].y)
    const xj = Number(sommets[j].x)
    const yj = Number(sommets[j].y)
    const croise = yi > point.y !== yj > point.y
    if (croise && point.x < ((xj - xi) * (point.y - yi)) / (yj - yi) + xi) dedans = !dedans
  }
  return dedans
}
