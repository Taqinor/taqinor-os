// ENF22 — helpers extraits de ModeTerrain.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.
import { nombre, contourTerrain, documentSurfacePose, KIND_SOL } from './surfacePose'

/** Axe des rangées DÉRIVÉ par le serveur (ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD). */
export const AXE_AUTO = 'AUTO'

/**
 * ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — un plan du moteur à 0 module n'est pas
 * un « optimum » à afficher en silence : on DIT qu'aucune table ne tient.
 * `null` quand il y a au moins un module (ou pas de plan).
 */
export function motifChampVide(reponse) {
  const plan = (reponse?.plans ?? [])[0] ?? null
  if (!plan) return null
  const modules = Number(plan.modules)
  if (!Number.isFinite(modules) || modules > 0) return null
  return 'Aucune table ne tient dans ce terrain avec cette saisie : le moteur '
    + 'n’a posé aucun module. Réduisez le nombre de modules par table ou '
    + 'agrandissez le terrain.'
}

/** Motif FRANÇAIS d'un refus du serveur (400 DRF `{champ: [motif]}`), ou `null`. */
export function motifRefus(data) {
  if (!data || typeof data !== 'object') return null
  if (typeof data.detail === 'string') return data.detail
  for (const cle of ['demande', 'calepinage']) {
    const v = data[cle]
    if (Array.isArray(v) && v.length) return String(v[0])
    if (typeof v === 'string' && v) return v
  }
  return null
}

/**
 * CAL89 — la DEMANDE envoyée au moteur (contrat `pose.json`, clé `demande`).
 * Aucune clé inventée : chaque nom est celui du document d'entrée du moteur.
 */
export function demandeMoteur(saisie, { alleeParDefautM = null } = {}) {
  const contour = contourTerrain(saisie.largeurM, saisie.profondeurM)
  if (!contour) return null
  const azimut = nombre(saisie.rowAzimuthDeg)
  const inclinaison = nombre(saisie.tiltDeg)
  const moduleLong = nombre(saisie.moduleLongM)
  const moduleCourt = nombre(saisie.moduleCourtM)
  const puissance = nombre(saisie.puissanceWc)
  const modulesParTable = nombre(saisie.modulesParTable)
  const allee = nombre(saisie.alleeM)
  if (moduleLong === null || moduleCourt === null || puissance === null) return null

  // ERR-QAH-CALEPINAGE-SOL-AXE-NORD-SUD — l'axe des rangées n'est PAS choisi
  // ici : il est IMPOSÉ par le kit et l'azimut (un module par table plein sud
  // ⇒ rangées est-ouest). `AUTO` demande au serveur de le dériver avec la
  // règle du moteur (`orientation.axe_rangee_impose`) — l'ancien `NORD_SUD`
  // codé en dur rendait un 400 « inconstructible » au cas le plus courant.
  const parametres = {
    kits: ['terrain'],
    axe_rangee: AXE_AUTO,
    mode_pose: 'rangees_explicites_dp',
    pas_recherche_m: 0.01,
  }
  // L'allée n'est envoyée QUE si elle est imposée : sinon le moteur applique
  // sa propre politique — on ne lui souffle jamais une valeur inventée ici.
  // ACAL75 — SEULE exception, déclarée par l'appelant : l'ombrière est une
  // couverture CONTINUE (`alleeParDefautM: 0`, pose jointive) ; l'écran le DIT.
  if (allee !== null) parametres.allee_m = allee
  else if (alleeParDefautM !== null) parametres.allee_m = alleeParDefautM

  return {
    schema_version: 1,
    repere: saisie.repere || 'TERRAIN',
    contour,
    surfaces: [{
      // Le genre « sol » n'est pas encore accepté par le contrat d'échange :
      // le terrain voyage comme surface de pose horizontale (cf. en-tête).
      type: 'polygone',
      repere: saisie.repere || 'TERRAIN',
      contour,
      trous: [],
      axe_rangee: AXE_AUTO,
      niveau: 0,
      pente_deg: 0,
      azimut_deg: azimut === null ? 180 : azimut,
      origine: [0, 0],
      coupures: [],
    }],
    kits: [{
      code: 'terrain',
      libelle: 'Table terrain',
      module_long_m: moduleLong,
      module_court_m: moduleCourt,
      puissance_module_wc: puissance,
      inclinaison_deg: inclinaison === null ? 0 : inclinaison,
      orientation: 'PORTRAIT',
      modules_par_table: modulesParTable === null ? 1 : modulesParTable,
      faitage_m: 0,
    }],
    parametres,
    obstacles: [],
    zones: [],
  }
}

/**
 * CAL89 — la surface de pose PERSISTÉE dans le document v2
 * (`poseSurfaces[]`, contrat `roof_layout_v2.schema.json`). ACAL25 : un simple
 * appel du survivant `surfacePose.js::documentSurfacePose` (le même que pour
 * l'ombrière) — module et allée compris.
 */
export function documentTerrain(saisie, reponse) {
  return documentSurfacePose(saisie, reponse, KIND_SOL)
}

/* ============================================================================
   CALX50 — LE CHAMP EST DESSINÉ, PLUS SEULEMENT COMPTÉ.
   ----------------------------------------------------------------------------
   Constat : cet écran postait au moteur et n'affichait que quatre nombres. Le
   placement des tables existait pourtant déjà, PUR et testé, dans le builder
   (`construireChampPose`, `@roofpro/scene3d`) — sans aucun appelant applicatif.
   On le branche : les tables, le compte, le pas, l'emprise et le taux viennent
   de LUI ; cet écran ne fait que les METTRE EN PAGE.

   CHARGEMENT PARESSEUX, comme le builder dans `ToitureDesign.jsx` : le module
   `scene3d` porte aussi la couche WebGL (Three + le lecteur de cartes). Un
   import statique les ferait tomber dans le paquet de CETTE route alors qu'on
   n'a besoin que d'une fonction de placement. Le module ne se charge donc
   qu'une fois l'écran ouvert ; s'il ne se charge pas, on le DIT et on ne
   dessine rien à sa place.

   CE QUI N'EST PAS RÉUTILISÉ, ET POURQUOI — `Vue2DPlan.jsx` projette un toit
   GÉORÉFÉRENCÉ : son résumé nomme des axes E-O / N-S et son compte s'intitule
   « module(s) ». Ici il n'y a AUCUN ancrage géographique (le terrain est saisi
   en mètres, les rangées tournées d'un azimut saisi) et les rectangles posés
   sont des TABLES, pas des modules : afficher ces deux libellés serait
   affirmer deux choses fausses. On garde donc les primitives de plan
   (`formatCote`, `milieu` de `plan2d.js`) et on pose le dessin dessus.

   `nonMesure` EST AFFICHÉ TEL QUEL : pente non renseignée, pas non mesurable,
   taux non calculable — chaque manque est dit avec les mots du service, jamais
   comblé par une valeur de remplacement.
   ========================================================================== */

/** Zone de dessin du champ (unités du `viewBox`, pas des pixels d'écran). */
export const VUE_LARGEUR = 900

export const VUE_HAUTEUR = 520

/**
 * CALX50 — la MISE EN PAGE du champ : mètres du moteur → coordonnées de la
 * zone de dessin. La MÊME échelle sur les deux axes (une longueur lue sur le
 * dessin est la longueur réelle), et l'axe des rangées vers le HAUT.
 *
 * Aucune géométrie n'est décidée ici : le contour vient de la saisie, les
 * tables de `construireChampPose`, les rangées et le pas du moteur. Contour de
 * moins de trois sommets ⇒ `null` : il n'y a rien à dessiner, et on ne dessine
 * pas un champ supposé.
 */
export function planVue2D({
  contourM,
  tables = [],
  rangees = [],
  pasM = null,
  compteModules = null,
  largeurPx = VUE_LARGEUR,
  hauteurPx = VUE_HAUTEUR,
  margePx = 28,
} = {}) {
  const contour = (contourM ?? [])
    .map((p) => [Number(p?.[0]), Number(p?.[1])])
    .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]))
  if (contour.length < 3) return null
  if (!(largeurPx > 0) || !(hauteurPx > 0)) return null

  // Les tables telles que le service les a PLACÉES (centre + emprise, mètres).
  const rectangles = []
  for (const t of tables ?? []) {
    const cx = Number(t?.cx)
    const cy = Number(t?.cy)
    const l = Number(t?.largeurM)
    const p = Number(t?.profondeurM)
    if (![cx, cy, l, p].every((v) => Number.isFinite(v))) continue
    rectangles.push([
      [cx - l / 2, cy - p / 2],
      [cx + l / 2, cy - p / 2],
      [cx + l / 2, cy + p / 2],
      [cx - l / 2, cy + p / 2],
    ])
  }

  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  for (const [x, y] of [...contour, ...rectangles.flat()]) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  const etendueX = Math.max(1e-6, maxX - minX)
  const etendueY = Math.max(1e-6, maxY - minY)
  const marge = Math.max(0, Math.min(Math.min(largeurPx, hauteurPx) / 2 - 1, margePx))
  const pxParM = Math.min((largeurPx - 2 * marge) / etendueX, (hauteurPx - 2 * marge) / etendueY)
  const decX = (largeurPx - etendueX * pxParM) / 2
  const decY = (hauteurPx - etendueY * pxParM) / 2
  // L'axe des rangées monte vers le HAUT du dessin : y décroît à l'écran.
  const versPx = ([x, y]) => [decX + (x - minX) * pxParM, decY + (maxY - y) * pxParM]

  const yRangees = Array.from(new Set((rangees ?? [])
    .map((r) => Number(r?.y0))
    .filter((v) => Number.isFinite(v)))).sort((a, b) => a - b)

  const pas = Number.isFinite(pasM) ? pasM : null
  const xCote = minX + etendueX / 2
  const cotePas = pas !== null && yRangees.length >= 2
    ? {
      // Le trait de cote mesure EXACTEMENT le pas rendu par le service : on
      // part de la première rangée et on avance de ce pas, plutôt que de
      // joindre deux rangées qui pourraient être plus éloignées que lui.
      lengthM: pas,
      from: versPx([xCote, yRangees[0]]),
      to: versPx([xCote, yRangees[0] + pas]),
    }
    : null

  return {
    largeurPx,
    hauteurPx,
    pxParM,
    contour: contour.map(versPx),
    tables: rectangles.map((q) => q.map(versPx)),
    rangees: yRangees.map((y) => ({
      y0: y,
      from: versPx([minX, y]),
      to: versPx([maxX, y]),
    })),
    cotes: contour.map((a, i) => {
      const b = contour[(i + 1) % contour.length]
      return {
        lengthM: Math.hypot(b[0] - a[0], b[1] - a[1]),
        from: versPx(a),
        to: versPx(b),
      }
    }),
    cotePas,
    // Le compte du MOTEUR, recopié — jamais le nombre de rectangles dessinés.
    compteModules,
  }
}

/**
 * ENF19 — la mise en page 2D du champ PLACÉ par le service (terrain ou
 * ombrière) : le contour vient des dimensions SAISIES, les tables, le pas et le
 * compte du `champ` rendu par le service, les rangées du plan du moteur. Pas de
 * champ posé ⇒ rien à dessiner (`null`), jamais un champ supposé.
 */
export function vueDuChamp(champ, plan, saisie) {
  if (!champ) return null
  return planVue2D({
    contourM: contourTerrain(saisie.largeurM, saisie.profondeurM),
    tables: champ.tables,
    rangees: plan?.rangees ?? [],
    pasM: champ.pasInterRangeeM,
    compteModules: champ.modules,
  })
}
