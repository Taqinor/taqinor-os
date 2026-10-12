// ENF22 — helpers extraits de Ombriere.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * CAL91 — LES TOTAUX PAR BÂTIMENT : les pans de toiture (`zones[]`, compte
 * posé dans `geometry.count`) ET les surfaces de pose (`poseSurfaces[]`,
 * compte rendu par le moteur), regroupés par `buildingId`.
 *
 * Un bâtiment dont RIEN n'est encore posé rend `modules: null` — pas `0`, qui
 * se lirait « rien ne tient » alors que rien n'a été calculé.
 */
export function totauxParBatiment(layout) {
  const total = new Map()
  const ajouter = (batiment, compte, genre) => {
    const cle = batiment || '(bâtiment unique)'
    const courant = total.get(cle) ?? { batiment: cle, modules: null, pans: 0, ombrieres: 0, sols: 0 }
    if (Number.isFinite(compte)) courant.modules = (courant.modules ?? 0) + compte
    if (genre === 'pan') courant.pans += 1
    if (genre === 'ombriere') courant.ombrieres += 1
    if (genre === 'sol') courant.sols += 1
    total.set(cle, courant)
  }
  for (const zone of layout?.zones ?? []) {
    ajouter(zone?.buildingId, Number(zone?.geometry?.count), 'pan')
  }
  for (const surface of layout?.poseSurfaces ?? []) {
    ajouter(surface?.buildingId, Number(surface?.engine?.modules), surface?.kind)
  }
  return Array.from(total.values())
}

/* ============================================================================
   CALX51 — L'OMBRIÈRE EST DESSINÉE, ET LEVÉE À LA HAUTEUR SAISIE.
   ----------------------------------------------------------------------------
   Constat : cet écran était le jumeau du mode terrain — un formulaire et des
   totaux, sans vue. Le placement existait pourtant, PUR et testé, dans le
   builder (`construireOmbriere`, `@roofpro/scene3d`) et n'avait aucun appelant.
   On le branche : c'est LUI qui lève la couverture, et c'est LUI qui refuse de
   deviner. Hauteur libre absente ⇒ l'altitude des tables reste 0 et le manque
   est affiché avec les mots du service ; aucune hauteur de confort n'est
   écrite nulle part, ni dans le code, ni sur l'écran.

   DEUX DESSINS, AUCUN CALCUL : le PLAN réutilise la mise en page du mode
   terrain (`planVue2D`) — une seule mise en page pour les deux surfaces de
   pose, sinon elles divergeraient. La COUPE (ci-dessous) ne fait que lire
   l'altitude que le service a posée sur chaque table.

   AUCUNE CHARGE, AUCUNE STRUCTURE — la règle de CAL91 ne bouge pas : ces
   dessins placent des formes, ils ne dimensionnent aucun ouvrage.
   ========================================================================== */

/** Zone de dessin de la coupe (unités du `viewBox`). */
export const COUPE_LARGEUR = 900

export const COUPE_HAUTEUR = 260

/**
 * CALX51 — la COUPE sur la largeur de l'ombrière : le sol, et la couverture à
 * l'altitude que `construireOmbriere` a posée sur chaque table.
 *
 * Le sol (altitude 0) fait TOUJOURS partie du cadre : c'est par rapport à lui
 * que la hauteur libre se lit. Altitude nulle ⇒ aucune cote de hauteur n'est
 * tracée, parce qu'il n'y a rien à coter. Aucune table ⇒ `null` : rien n'est
 * dessiné plutôt qu'une ombrière supposée.
 */
export function coupeOmbriere({
  tables = [],
  largeurPx = COUPE_LARGEUR,
  hauteurPx = COUPE_HAUTEUR,
  margePx = 28,
} = {}) {
  if (!(largeurPx > 0) || !(hauteurPx > 0)) return null
  const segments = []
  for (const t of tables ?? []) {
    const cx = Number(t?.cx)
    const l = Number(t?.largeurM)
    const z = Number(t?.z)
    if (![cx, l, z].every((v) => Number.isFinite(v))) continue
    segments.push({ x0: cx - l / 2, x1: cx + l / 2, z })
  }
  if (!segments.length) return null

  let minX = Infinity
  let maxX = -Infinity
  let altitudeM = 0
  for (const s of segments) {
    if (s.x0 < minX) minX = s.x0
    if (s.x1 > maxX) maxX = s.x1
    if (s.z > altitudeM) altitudeM = s.z
  }
  const etendueX = Math.max(1e-6, maxX - minX)
  const etendueZ = Math.max(1e-6, altitudeM)
  const marge = Math.max(0, Math.min(Math.min(largeurPx, hauteurPx) / 2 - 1, margePx))
  const pxParM = Math.min((largeurPx - 2 * marge) / etendueX, (hauteurPx - 2 * marge) / etendueZ)
  const decX = (largeurPx - etendueX * pxParM) / 2
  const decZ = (hauteurPx - etendueZ * pxParM) / 2
  // Une altitude qui monte va vers le HAUT du dessin : y décroît à l'écran.
  const versPx = (x, z) => [decX + (x - minX) * pxParM, decZ + (altitudeM - z) * pxParM]

  return {
    largeurPx,
    hauteurPx,
    pxParM,
    altitudeM,
    sol: { from: versPx(minX, 0), to: versPx(maxX, 0) },
    tables: segments.map((s) => ({ z: s.z, from: versPx(s.x0, s.z), to: versPx(s.x1, s.z) })),
    coteHauteur: altitudeM > 0
      ? { lengthM: altitudeM, from: versPx(minX, 0), to: versPx(minX, altitudeM) }
      : null,
  }
}
