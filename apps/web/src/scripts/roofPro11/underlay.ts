/**
 * CALX107 — LE CALQUE DE FOND CALÉ DE L'ATELIER (plan importé, ou photo de site).
 *
 * Constat : le panneau de calques propose « Plan importé » et « Photo calée »
 * (`frontend/src/features/calepinage/calques.js`) mais ces deux calques pilotaient une
 * liste VIDE de couches MapLibre (`mapDraw.ts`, `MAPLIBRE_LAYERS_PAR_CALQUE`) : les
 * bascules existaient sans rien à montrer. Ce module apporte la géométrie et la lecture
 * de contrat du fond — PURES : aucun DOM, aucun MapLibre, aucun Three — et `mapDraw.ts`
 * s'en sert pour poser les deux sources/couches réelles.
 *
 * RÈGLE DURE DU MODULE (contrat CALX86, D-CALX 7) : AUCUNE ÉCHELLE N'EST DEVINÉE.
 *  - une `photo` de site est DÉJÀ calée à QUATRE coins par CAL53 (`PhotoSite.calage`,
 *    `services/photos.py::calage_photo_site`) : ce calage-là fait foi, et un document
 *    qui prétendrait lui greffer un second calage à deux points est REFUSÉ en nommant
 *    `calage` (deux calages d'une même image se contrediraient sans que rien ne dise
 *    lequel a raison) ;
 *  - un `plan` importé arrive SANS échelle (l'analyseur rend un contour dans l'unité du
 *    fichier et s'arrête là, `services/import_plan.py`) : il se cale à DEUX points plus
 *    une distance réelle SAISIE, qui porte obligatoirement sa `source`. Sans elle, rien
 *    n'est placé et le motif est affiché (CALX108).
 *
 * Le fond est un CONFORT DE DESSIN : il ne touche ni `ctx.vertices`, ni les obstacles, ni
 * le pavage, ni aucune production. Il ne fait que se peindre sous le tracé.
 */
import { type LngLat } from '../../lib/roof';
import { normaliserDeg, pivoterPoint } from './snap';
import { DEG2M, DEG2RAD } from './constants';

// ————————————————————————————————————————————————————————————————————————
// Vocabulaire du contrat CALX86 (`roof_layout_v2.schema.json`, `$defs.underlay`)
// ————————————————————————————————————————————————————————————————————————

/** Genre de fond — énumération FERMÉE du contrat. */
export type GenreFond = 'plan' | 'photo';

/** Les genres reconnus, dans l'ordre du contrat. Toute autre valeur est refusée. */
export const GENRES_FOND: readonly GenreFond[] = ['plan', 'photo'];

/** Calage à DEUX points d'un PLAN (CALX86 `$defs.calageDeuxPoints`). */
export interface CalageDeuxPoints {
  /** Les DEUX points correspondants SUR LA CARTE, en [[lng, lat], [lng, lat]]. */
  ancre: [LngLat, LngLat];
  /** Les DEUX points cliqués SUR L'IMAGE, en [[x, y], [x, y]], repère PROPRE du fichier. */
  pointsImage: [[number, number], [number, number]];
  /** Distance RÉELLE entre les deux points (m), SAISIE. C'est ELLE qui donne l'échelle. */
  distanceReelleM: number;
  /** Rotation retenue à l'écran (°, 0 = aucune). Optionnelle. */
  rotationDeg?: number;
  /** D'OÙ vient `distanceReelleM`, en clair (« mesurée au télémètre », « cote lue… »). */
  source: string;
}

/** Le fond tel que le document le porte (clé racine `underlay`, OPTIONNELLE et additive). */
export interface DocumentUnderlay {
  kind: GenreFond;
  /** La pièce qui porte le FICHIER — obligatoire pour un `plan`, nulle/absente pour une photo. */
  attachmentId?: number | null;
  /** La `PhotoSite` utilisée comme fond — obligatoire pour une `photo`. */
  photoSiteId?: number | null;
  /** Opacité SAISIE, entre 0 et 1. Absente = l'atelier applique son propre réglage. */
  opacite?: number;
  /** Calage à deux points — RÉSERVÉ au `plan`. */
  calage?: CalageDeuxPoints | null;
}

/** Champ que nomme un refus — jamais un « non enregistré » générique. */
export type ChampFond = 'kind' | 'attachmentId' | 'photoSiteId' | 'opacite' | 'calage';

export type LectureFond =
  | { ok: true; fond: DocumentUnderlay }
  | { ok: false; champ: ChampFond; motif: string };

// ————————————————————————————————————————————————————————————————————————
// Identifiants MapLibre — le vocabulaire que `mapDraw.ts` déclare dans
// `MAPLIBRE_LAYERS_PAR_CALQUE` et que le panneau de calques pilote par `setLayerState`.
// ————————————————————————————————————————————————————————————————————————

/** Source ET couche du PLAN importé, calé à deux points. */
export const UNDERLAY_PLAN_LAYER_ID = 'rp9-underlay-plan';

/** Source ET couche de la PHOTO de site, calée à quatre coins par CAL53. */
export const UNDERLAY_PHOTO_LAYER_ID = 'rp9-underlay-photo';

/** Le calque du panneau (`calques.js`) auquel chaque genre appartient. */
export const CALQUE_PAR_GENRE: Readonly<Record<GenreFond, string>> = {
  plan: 'plan',
  photo: 'photo',
};

/** L'identifiant de couche MapLibre d'un genre de fond. */
export function idCoucheFond(kind: GenreFond): string {
  return kind === 'photo' ? UNDERLAY_PHOTO_LAYER_ID : UNDERLAY_PLAN_LAYER_ID;
}

/**
 * Opacité de rendu par DÉFAUT du fond, quand le document n'en porte aucune.
 * CONVENTION DE DESSIN (pas une donnée du site, cf. contrat CALX86 : « une opacité est un
 * confort de dessin ») : le fond doit rester lisible SOUS le tracé, donc translucide.
 */
export const OPACITE_FOND_PAR_DEFAUT = 0.6;

// ————————————————————————————————————————————————————————————————————————
// Lecture du contrat
// ————————————————————————————————————————————————————————————————————————

function estEntier(v: unknown): v is number {
  return typeof v === 'number' && Number.isInteger(v);
}

function estCouple(v: unknown): v is [number, number] {
  return Array.isArray(v) && v.length === 2 && Number.isFinite(v[0]) && Number.isFinite(v[1]);
}

/** Deux couples de nombres, dans l'ordre — la forme de `ancre` et de `pointsImage`. */
function litDeuxCouples(v: unknown): [[number, number], [number, number]] | null {
  if (!Array.isArray(v) || v.length !== 2) return null;
  if (!estCouple(v[0]) || !estCouple(v[1])) return null;
  return [
    [v[0][0], v[0][1]],
    [v[1][0], v[1][1]],
  ];
}

/**
 * CALX107 — lit un calage à DEUX points selon `$defs.calageDeuxPoints`. Les quatre clés
 * requises le sont RÉELLEMENT : aucune n'est déduite des autres, et l'absence de l'une
 * rend le calage inutilisable plutôt que de lui inventer une valeur.
 */
export function lireCalageDeuxPoints(
  valeur: unknown,
): { ok: true; calage: CalageDeuxPoints } | { ok: false; motif: string } {
  if (!valeur || typeof valeur !== 'object') {
    return { ok: false, motif: 'Calage absent — un plan importé n’a pas d’échelle propre tant qu’il n’est pas calé.' };
  }
  const brut = valeur as Record<string, unknown>;
  const ancre = litDeuxCouples(brut.ancre);
  if (!ancre) {
    return { ok: false, motif: 'Calage refusé : `ancre` attend les DEUX points correspondants sur la carte, en [lng, lat].' };
  }
  const pointsImage = litDeuxCouples(brut.pointsImage);
  if (!pointsImage) {
    return { ok: false, motif: 'Calage refusé : `pointsImage` attend les DEUX points cliqués sur l’image, en [x, y].' };
  }
  const distanceReelleM = brut.distanceReelleM;
  if (typeof distanceReelleM !== 'number' || !Number.isFinite(distanceReelleM) || distanceReelleM <= 0) {
    return {
      ok: false,
      motif:
        'Calage refusé : `distanceReelleM` manquante — saisissez la distance réelle (m) entre les deux points. ' +
        'Aucune échelle n’est déduite du fichier.',
    };
  }
  const source = typeof brut.source === 'string' ? brut.source.trim() : '';
  if (!source) {
    return {
      ok: false,
      motif: 'Calage refusé : `source` manquante — dites d’où vient la distance (« mesurée au télémètre », « cote lue sur le plan »…).',
    };
  }
  const calage: CalageDeuxPoints = {
    ancre: [
      [ancre[0][0], ancre[0][1]],
      [ancre[1][0], ancre[1][1]],
    ],
    pointsImage,
    distanceReelleM,
    source,
  };
  if (typeof brut.rotationDeg === 'number' && Number.isFinite(brut.rotationDeg)) {
    calage.rotationDeg = brut.rotationDeg;
  }
  return { ok: true, calage };
}

/**
 * CALX107 — lit la clé `underlay` du document (contrat CALX86). Chaque refus NOMME le
 * champ fautif. Une valeur absente/nulle n'est PAS un refus : c'est « aucun fond », donc
 * l'atelier d'aujourd'hui exactement — l'appelant distingue par `valeur == null`.
 */
export function lireUnderlay(valeur: unknown): LectureFond {
  if (!valeur || typeof valeur !== 'object' || Array.isArray(valeur)) {
    return { ok: false, champ: 'kind', motif: 'Fond refusé : le document attend un objet `underlay` portant son genre.' };
  }
  const brut = valeur as Record<string, unknown>;
  const kind = brut.kind;
  if (kind !== 'plan' && kind !== 'photo') {
    return {
      ok: false,
      champ: 'kind',
      motif: `Fond refusé : genre « ${String(kind ?? '')} » inconnu — seuls « plan » (fichier importé) et « photo » (photo de site) existent.`,
    };
  }
  const fond: DocumentUnderlay = { kind };

  if (typeof brut.opacite !== 'undefined' && brut.opacite !== null) {
    const o = brut.opacite;
    if (typeof o !== 'number' || !Number.isFinite(o) || o < 0 || o > 1) {
      return { ok: false, champ: 'opacite', motif: 'Fond refusé : `opacite` attend un nombre entre 0 (invisible) et 1 (opaque).' };
    }
    fond.opacite = o;
  }

  if (kind === 'plan') {
    if (!estEntier(brut.attachmentId)) {
      return {
        ok: false,
        champ: 'attachmentId',
        motif: 'Fond refusé : `attachmentId` manquant — un plan de fond désigne toujours son fichier, sinon il n’affiche rien.',
      };
    }
    fond.attachmentId = brut.attachmentId;
    if (typeof brut.calage !== 'undefined' && brut.calage !== null) {
      const lu = lireCalageDeuxPoints(brut.calage);
      if (!lu.ok) return { ok: false, champ: 'calage', motif: lu.motif };
      fond.calage = lu.calage;
    }
    return { ok: true, fond };
  }

  // kind === 'photo'
  if (!estEntier(brut.photoSiteId)) {
    return {
      ok: false,
      champ: 'photoSiteId',
      motif: 'Fond refusé : `photoSiteId` manquant — une photo de fond désigne toujours sa photo de site, et donc son calage à quatre coins.',
    };
  }
  if (typeof brut.calage !== 'undefined' && brut.calage !== null) {
    return {
      ok: false,
      champ: 'calage',
      motif:
        'Fond refusé : une photo est DÉJÀ calée à quatre coins (CAL53) — elle ne porte pas de second calage à deux points. ' +
        'Deux calages d’une même image se contrediraient.',
    };
  }
  fond.photoSiteId = brut.photoSiteId;
  if (brut.attachmentId === null) fond.attachmentId = null;
  return { ok: true, fond };
}

/**
 * CALX107 — ce que `serializeLayout` (`prefill.ts`) écrit à la racine du document pour le
 * fond. ADDITIF et sans surprise : tant que l'atelier ne porte AUCUN fond valide, la
 * fonction rend `{}` et le document sort byte pour byte comme aujourd'hui (aucune clé
 * `underlay`). Un fond invalide n'est jamais écrit à moitié — il n'est pas écrit du tout.
 *
 * Le fond est lu sur `ctx` par un cast LOCAL (patron WJ41 de `mapDraw.ts`) : `Ctx`
 * (`context.ts`) appartient à une autre lane et n'est pas rouvert ici.
 */
export function underlayPourDocument(ctx: unknown): { underlay?: DocumentUnderlay } {
  const brut = (ctx as { underlay?: unknown } | null | undefined)?.underlay;
  if (brut == null) return {};
  const lu = lireUnderlay(brut);
  return lu.ok ? { underlay: lu.fond } : {};
}

// ————————————————————————————————————————————————————————————————————————
// Placement sur la carte
// ————————————————————————————————————————————————————————————————————————

/** Les QUATRE coins d'une image posée sur la carte, dans l'ordre MapLibre :
 *  haut-gauche, haut-droite, bas-droite, bas-gauche. */
export type CoinsImage = [LngLat, LngLat, LngLat, LngLat];

/**
 * CALX107 — les QUATRE coins d'une `PhotoSite` calée (CAL53), convertis du stockage
 * `[lat, lng]` (`services/photos.py::calage_photo_site`) vers l'ordre `[lng, lat]` que
 * MapLibre attend. L'ORDRE des coins est conservé tel quel : c'est l'ordre de pose des
 * quatre poignées (`frontend/src/features/calepinage/PhotoSiteCalage.jsx`), donc déjà
 * haut-gauche → haut-droite → bas-droite → bas-gauche. Rien n'est réordonné ni deviné.
 *
 * Une photo NON calée (calage absent/incomplet) n'est pas placée : le motif le dit.
 */
export function coinsDepuisCalagePhoto(
  calage: unknown,
): { ok: true; coins: CoinsImage } | { ok: false; motif: string } {
  const coins = (calage as { coins?: unknown } | null | undefined)?.coins;
  if (!Array.isArray(coins) || coins.length !== 4) {
    return {
      ok: false,
      motif: 'Photo non affichée : elle n’est pas calée sur la carte — posez ses quatre coins avant de l’utiliser comme fond.',
    };
  }
  const out: LngLat[] = [];
  for (const coin of coins) {
    if (!estCouple(coin)) {
      return { ok: false, motif: 'Photo non affichée : un de ses quatre coins n’est pas une paire [latitude, longitude].' };
    }
    const [lat, lng] = coin;
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      return { ok: false, motif: 'Photo non affichée : un de ses coins est hors amplitude GPS.' };
    }
    out.push([lng, lat]);
  }
  return { ok: true, coins: [out[0], out[1], out[2], out[3]] };
}

/** La ressource d'affichage que l'hôte fournit pour un fond : le FICHIER (URL pré-signée)
 *  et, selon le genre, son calage. Rien n'est téléchargé ni mesuré ici. */
export interface RessourceFond {
  /** URL pré-signée du fichier du fond. Absente ⇒ rien à peindre, et on le dit. */
  url?: string | null;
  /** `PhotoSite.calage` TEL QUEL (`{ coins: [[lat, lng] × 4] }`) — genre `photo`. */
  calagePhoto?: unknown;
  /** Les quatre coins déjà calculés pour un `plan`. Absents, CALX108 les DÉRIVE du calage
   *  à deux points + `tailleImage`. Ni l'un ni l'autre ⇒ le plan n'est pas placé, et le
   *  motif le dit. */
  coinsPlan?: readonly LngLat[] | null;
  /** CALX108 — dimensions du fichier de fond, dans SON repère (pixels pour une image,
   *  unité du fichier pour un plan vectoriel). Le repère n'est PAS converti : c'est
   *  justement parce qu'on ignore son unité qu'une distance réelle est exigée. */
  tailleImage?: TailleImage | null;
}

/** Ce qu'il faut pour peindre un fond, ou le motif du refus — jamais un placement partiel. */
export type PlacementFond =
  | { ok: true; layerId: string; calque: string; url: string; coins: CoinsImage; opacite: number }
  | { ok: false; champ: ChampFond | 'url'; motif: string };

/**
 * CALX107 — assemble le placement d'un fond : quelle couche, quelle image, quels quatre
 * coins, quelle opacité. PURE (aucune carte touchée) : `mapDraw.ts` n'a plus qu'à poser
 * la source et la couche, ou à afficher le motif.
 *
 * `rp9-underlay-photo` est construite depuis les QUATRE coins de `PhotoSite`, JAMAIS depuis
 * `underlay.calage` à deux points (qui ne vaut que pour un plan) — c'est précisément ce que
 * le contrat CALX86 refuse de confondre.
 */
export function placementDuFond(fond: DocumentUnderlay, ressource: RessourceFond): PlacementFond {
  const url = typeof ressource?.url === 'string' ? ressource.url.trim() : '';
  if (!url) {
    return {
      ok: false,
      champ: 'url',
      motif: 'Fond non affiché : le fichier du fond n’est pas accessible (aucune URL fournie pour cette pièce).',
    };
  }
  const opacite = typeof fond.opacite === 'number' ? fond.opacite : OPACITE_FOND_PAR_DEFAUT;
  if (fond.kind === 'photo') {
    const lu = coinsDepuisCalagePhoto(ressource.calagePhoto);
    if (!lu.ok) return { ok: false, champ: 'photoSiteId', motif: lu.motif };
    return {
      ok: true,
      layerId: UNDERLAY_PHOTO_LAYER_ID,
      calque: CALQUE_PAR_GENRE.photo,
      url,
      coins: lu.coins,
      opacite,
    };
  }
  let coins = ressource.coinsPlan;
  // CALX108 — sans coins fournis, ils se DÉRIVENT du calage à deux points + la taille du
  // fichier. Sans calage ni taille, rien n'est placé : aucune échelle n'est devinée.
  if (!Array.isArray(coins) && fond.calage && ressource.tailleImage) {
    const derive = coinsDuPlanCale(fond.calage, ressource.tailleImage);
    if (!derive.ok) return { ok: false, champ: 'calage', motif: derive.motif };
    coins = derive.coins;
  }
  if (!Array.isArray(coins) || coins.length !== 4 || !coins.every(estCouple)) {
    return {
      ok: false,
      champ: 'calage',
      motif: MOTIF_PLAN_NON_CALE,
    };
  }
  return {
    ok: true,
    layerId: UNDERLAY_PLAN_LAYER_ID,
    calque: CALQUE_PAR_GENRE.plan,
    url,
    coins: [
      [coins[0][0], coins[0][1]],
      [coins[1][0], coins[1][1]],
      [coins[2][0], coins[2][1]],
      [coins[3][0], coins[3][1]],
    ],
    opacite,
  };
}

/** La spécification de source MapLibre d'un fond — une source `image` géo-référencée par
 *  ses quatre coins, rien de plus (aucune tuile, aucun service tiers). */
export function specSourceFond(placement: Extract<PlacementFond, { ok: true }>): {
  type: 'image';
  url: string;
  coordinates: CoinsImage;
} {
  return { type: 'image', url: placement.url, coordinates: placement.coins };
}

/** La spécification de couche MapLibre d'un fond. `type: 'raster'` — donc l'opacité du
 *  panneau de calques la pilote par `raster-opacity` (`opacityPropFor`, CAL103). */
export function specCoucheFond(placement: Extract<PlacementFond, { ok: true }>): {
  id: string;
  type: 'raster';
  source: string;
  paint: Record<string, number>;
} {
  return {
    id: placement.layerId,
    type: 'raster',
    source: placement.layerId,
    paint: { 'raster-opacity': placement.opacite },
  };
}

/**
 * CALX107 — l'identifiant de couche AVANT laquelle insérer le fond pour qu'il atterrisse
 * au rang prévu par `ORDRE_RENDU_CALQUES` : la PREMIÈRE couche installée appartenant à un
 * calque situé AU-DESSUS du sien. `undefined` = rien au-dessus n'est encore posé, donc
 * l'ajout en fin de pile convient (MapLibre empile par défaut).
 *
 * Le fond reste ainsi SOUS le tracé et AU-DESSUS de l'imagerie, sans dépendre de l'ordre
 * dans lequel les couches ont été ajoutées.
 */
export function coucheAvantPourFond(
  calque: string,
  ordre: readonly string[],
  couchesParCalque: Readonly<Record<string, readonly string[]>>,
  coucheInstallee: (id: string) => boolean,
): string | undefined {
  const rang = ordre.indexOf(calque);
  if (rang < 0) return undefined;
  for (let i = rang + 1; i < ordre.length; i++) {
    for (const layerId of couchesParCalque[ordre[i]] ?? []) {
      let installee = false;
      try {
        installee = Boolean(coucheInstallee(layerId));
      } catch {
        installee = false; /* style pas prêt : cette couche ne compte pas */
      }
      if (installee) return layerId;
    }
  }
  return undefined;
}

// ————————————————————————————————————————————————————————————————————————
// CALX108 — CALER LE FOND À L'ÉCHELLE PAR DEUX POINTS ET UNE DISTANCE RÉELLE SAISIE
//
// Constat : l'échelle venait EXCLUSIVEMENT de la projection géodésique — aucune
// calibration n'existait dans le module — et `services/import_plan.py` le dit : un DXF
// sans `$INSUNITS` ou un PDF rend `unite='inconnu'` et « c'est la calibration de l'atelier
// qui donne l'échelle ». Cette calibration-là n'existait pas. La voici.
//
// RÈGLE DURE : le facteur d'échelle vient de DEUX points cliqués sur l'image et de la
// distance réelle SAISIE entre eux, JAMAIS d'une unité lue (ou devinée) dans le fichier.
// Une clé `unite`, `echelle`, `dpi`… que porterait le fichier est IGNORÉE : elle n'entre
// dans aucun des calculs ci-dessous. Sans distance saisie, rien n'est calé et le motif le
// dit, en nommant `distanceReelleM`.
// ————————————————————————————————————————————————————————————————————————

/** Le motif unique du « plan pas encore calé » — une seule formulation dans tout l'atelier. */
export const MOTIF_PLAN_NON_CALE =
  'Plan non affiché : il n’est pas calé — cliquez deux points sur le plan et saisissez la distance réelle qui les sépare. ' +
  'Aucune échelle n’est déduite du fichier.';

/** Dimensions du fichier de fond, dans SON repère (jamais converties). */
export interface TailleImage {
  largeur: number;
  hauteur: number;
}

/** Champ que nomme un refus de calage. */
export type ChampCalage = 'pointsImage' | 'ancre' | 'distanceReelleM' | 'source';

/**
 * CALX108 — le résultat du calage : rotation, translation et facteur d'échelle. Aucune
 * des trois valeurs n'est devinée : l'échelle vient de la distance SAISIE, la rotation de
 * l'écart entre la direction des deux points sur l'image et sur la carte, la translation
 * de l'ancre elle-même.
 */
export interface Calibration {
  /** Facteur d'échelle : mètres réels par unité du fichier (m/px pour une image). */
  echelleMParPx: number;
  /** Rotation du fond (°, sens horaire, même repère de cap que `snap.ts`), dans [0, 360). */
  rotationDeg: number;
  /** Le point de l'IMAGE qui sert d'origine : `pointsImage[0]`. */
  origineImage: [number, number];
  /** Le point de la CARTE sur lequel cette origine atterrit : `ancre[0]`. */
  origineCarte: LngLat;
  /** Distance mesurée entre les deux points, dans le repère du FICHIER (px/unité). */
  distanceImagePx: number;
}

export type VerdictCalage =
  | { ok: true; calibration: Calibration }
  | { ok: false; champ: ChampCalage; motif: string };

/**
 * CALX108 — cap (°, depuis le nord, sens horaire) d'un vecteur exprimé dans le repère de
 * l'IMAGE, si l'image était posée NON TOURNÉE : x croît vers l'est, y croît vers le BAS,
 * donc vers le SUD (convention universelle des repères image). Le nord vaut donc `-y`.
 */
export function capImageDeg(dx: number, dy: number): number {
  return normaliserDeg((Math.atan2(dx, -dy) * 180) / Math.PI);
}

/**
 * CALX108 — cap (°, depuis le nord, sens horaire) de `a`→`b` mesuré dans le PLAN TANGENT
 * local, et NON sur la grande ellipse (`capEntreDeg`, `snap.ts`).
 *
 * Le fond est une image PLATE posée sur ce même plan tangent (`pointImageSurCarte`,
 * `depuisOffsetM`) : mesurer sa rotation avec le cap géodésique INITIAL — qui varie le long
 * d'une grande ellipse — introduirait un écart (~0,006° à la latitude de Casablanca sur
 * deux points est-ouest) qui n'a aucun sens physique pour une image plate, et qui ferait
 * que deux points parfaitement horizontaux ne donnent pas une rotation NULLE. Le tracé du
 * toit, lui, garde ses caps géodésiques : ce repère-ci ne sert qu'au placement du fond.
 */
export function capPlanTangentDeg(a: LngLat, b: LngLat): number {
  const cosLat = Math.max(1e-6, Math.cos(((a[1] + b[1]) / 2) * DEG2RAD));
  const est = (b[0] - a[0]) * cosLat;
  const nord = b[1] - a[1];
  return normaliserDeg((Math.atan2(est, nord) * 180) / Math.PI);
}

/**
 * CALX108 — LA fonction de calage. Deux points cliqués sur l'image, les deux points
 * correspondants sur la carte, et la distance RÉELLE saisie entre eux : elle en tire le
 * facteur d'échelle, la rotation et la translation.
 *
 *  - `echelleMParPx = distanceReelleM / distance entre les deux points de l'IMAGE` — c'est
 *    tout : 100 px déclarés à 10 m font 0,1 m/px, quelle que soit la carte dessous ;
 *  - `rotationDeg = cap des deux ancres (carte) − cap des deux points (image non tournée)` ;
 *  - la translation est l'ancre elle-même : `pointsImage[0]` atterrit sur `ancre[0]`.
 *
 * Chaque refus NOMME son champ. Une distance non saisie ⇒ AUCUN calage n'est rendu (et donc
 * rien n'est écrit dans `underlay.calage`) : l'atelier affiche le motif, il ne se rabat sur
 * aucune échelle de fichier.
 */
export function caleDeuxPoints(
  pointsImage: unknown,
  ancres: unknown,
  distanceReelleM: unknown,
  source?: unknown,
): VerdictCalage {
  const image = litDeuxCouples(pointsImage);
  if (!image) {
    return {
      ok: false,
      champ: 'pointsImage',
      motif: 'Calage incomplet : cliquez DEUX points sur le plan (`pointsImage` attend deux paires [x, y]).',
    };
  }
  const dxImage = image[1][0] - image[0][0];
  const dyImage = image[1][1] - image[0][1];
  const distanceImagePx = Math.hypot(dxImage, dyImage);
  if (!(distanceImagePx > 0)) {
    return {
      ok: false,
      champ: 'pointsImage',
      motif: 'Calage refusé : les deux points cliqués sur le plan sont confondus — écartez-les pour donner une échelle.',
    };
  }
  const ancre = litDeuxCouples(ancres);
  if (!ancre) {
    return {
      ok: false,
      champ: 'ancre',
      motif: 'Calage incomplet : désignez sur la carte les DEUX points correspondants (`ancre` attend deux paires [lng, lat]).',
    };
  }
  if (typeof distanceReelleM !== 'number' || !Number.isFinite(distanceReelleM) || distanceReelleM <= 0) {
    return {
      ok: false,
      champ: 'distanceReelleM',
      motif:
        'Distance réelle manquante — saisissez la distance mesurée (m) entre les deux points, supérieure à 0. ' +
        'Aucune échelle n’est déduite du fichier.',
    };
  }
  if (typeof source !== 'undefined' && !(typeof source === 'string' && source.trim())) {
    return {
      ok: false,
      champ: 'source',
      motif: 'Source de la distance manquante — dites d’où elle vient (« mesurée au télémètre », « cote lue sur le plan »…).',
    };
  }
  const a0: LngLat = [ancre[0][0], ancre[0][1]];
  const a1: LngLat = [ancre[1][0], ancre[1][1]];
  const capCarte = capPlanTangentDeg(a0, a1);
  const rotation = normaliserDeg(capCarte - capImageDeg(dxImage, dyImage));
  return {
    ok: true,
    calibration: {
      echelleMParPx: distanceReelleM / distanceImagePx,
      // Le contrat CALX86 borne `rotationDeg` à [0, 360] : on y ramène la valeur signée.
      rotationDeg: (rotation + 360) % 360,
      origineImage: [image[0][0], image[0][1]],
      origineCarte: a0,
      distanceImagePx,
    },
  };
}

/**
 * CALX108 — le calage tel que le document le porte (`$defs.calageDeuxPoints`), à partir
 * des deux points, de la distance SAISIE et de sa SOURCE. Rien n'est écrit tant que le
 * calage n'est pas complet : un refus rend son champ et son motif, et l'appelant ne touche
 * pas à `underlay.calage`.
 */
export function calagePourDocument(
  pointsImage: unknown,
  ancres: unknown,
  distanceReelleM: unknown,
  source: unknown,
): { ok: true; calage: CalageDeuxPoints; calibration: Calibration } | { ok: false; champ: ChampCalage; motif: string } {
  const texte = typeof source === 'string' ? source.trim() : '';
  if (!texte) {
    return {
      ok: false,
      champ: 'source',
      motif: 'Source de la distance manquante — dites d’où elle vient (« mesurée au télémètre », « cote lue sur le plan »…).',
    };
  }
  const verdict = caleDeuxPoints(pointsImage, ancres, distanceReelleM, texte);
  if (!verdict.ok) return verdict;
  const image = litDeuxCouples(pointsImage) as [[number, number], [number, number]];
  const ancre = litDeuxCouples(ancres) as [[number, number], [number, number]];
  return {
    ok: true,
    calibration: verdict.calibration,
    calage: {
      ancre: [
        [ancre[0][0], ancre[0][1]],
        [ancre[1][0], ancre[1][1]],
      ],
      pointsImage: image,
      distanceReelleM: distanceReelleM as number,
      rotationDeg: verdict.calibration.rotationDeg,
      source: texte,
    },
  };
}

/** Le point de la carte situé à (`estM`, `nordM`) de `origine` — plan tangent local, la
 *  MÊME projection que `grilleMetrique` (`mapDraw.ts`) et `redimensionnerRectangle`
 *  (`snap.ts`) : aucun rayon ni facteur neuf. */
function depuisOffsetM(origine: LngLat, estM: number, nordM: number): LngLat {
  const cosLat = Math.max(1e-6, Math.cos(origine[1] * DEG2RAD));
  return [origine[0] + estM / (DEG2M * cosLat), origine[1] + nordM / DEG2M];
}

/**
 * CALX108 — où atterrit un point de l'IMAGE, une fois le fond calé : son écart à l'origine
 * est converti en mètres par le facteur d'échelle, puis tourné de `rotationDeg` autour de
 * l'ancre. C'est la seule transformation appliquée au fond — aucune correction de
 * perspective n'est inventée.
 */
export function pointImageSurCarte(calibration: Calibration, point: readonly [number, number]): LngLat {
  const dx = point[0] - calibration.origineImage[0];
  const dy = point[1] - calibration.origineImage[1];
  // Repère image NON tourné : +x = est, +y = sud (donc nord = −y).
  const brut = depuisOffsetM(
    calibration.origineCarte,
    dx * calibration.echelleMParPx,
    -dy * calibration.echelleMParPx,
  );
  return pivoterPoint(brut, calibration.rotationDeg, calibration.origineCarte);
}

/**
 * CALX108 — les QUATRE coins d'un plan calé, dans l'ordre MapLibre (haut-gauche,
 * haut-droite, bas-droite, bas-gauche), c'est-à-dire les coins (0,0), (L,0), (L,H), (0,H)
 * du fichier passés par le calage. La rotation RETENUE à l'écran (`calage.rotationDeg`,
 * ajustée à la molette) l'emporte sur celle déduite des deux points.
 */
export function coinsDuPlanCale(
  calage: unknown,
  taille: TailleImage | null | undefined,
): { ok: true; coins: CoinsImage } | { ok: false; motif: string } {
  const lu = lireCalageDeuxPoints(calage);
  if (!lu.ok) return { ok: false, motif: lu.motif };
  const largeur = taille?.largeur;
  const hauteur = taille?.hauteur;
  if (!Number.isFinite(largeur) || !Number.isFinite(hauteur) || (largeur as number) <= 0 || (hauteur as number) <= 0) {
    return {
      ok: false,
      motif: 'Plan non affiché : les dimensions du fichier sont inconnues — impossible de savoir quelle étendue couvre le calage.',
    };
  }
  const verdict = caleDeuxPoints(lu.calage.pointsImage, lu.calage.ancre, lu.calage.distanceReelleM, lu.calage.source);
  if (!verdict.ok) return { ok: false, motif: verdict.motif };
  const calibration: Calibration = {
    ...verdict.calibration,
    rotationDeg:
      typeof lu.calage.rotationDeg === 'number' && Number.isFinite(lu.calage.rotationDeg)
        ? lu.calage.rotationDeg
        : verdict.calibration.rotationDeg,
  };
  const L = largeur as number;
  const H = hauteur as number;
  return {
    ok: true,
    coins: [
      pointImageSurCarte(calibration, [0, 0]),
      pointImageSurCarte(calibration, [L, 0]),
      pointImageSurCarte(calibration, [L, H]),
      pointImageSurCarte(calibration, [0, H]),
    ],
  };
}

/**
 * CALX108 — GLISSÉ : translate le fond de (`deltaEstM`, `deltaNordM`) en déplaçant les DEUX
 * ancres du même vecteur. Le facteur d'échelle (qui ne dépend que de `pointsImage` et de
 * `distanceReelleM`) et la rotation retenue sont donc INCHANGÉS : un glissé ne remet jamais
 * en cause la mesure saisie.
 */
export function deplacerCalage(calage: CalageDeuxPoints, deltaEstM: number, deltaNordM: number): CalageDeuxPoints {
  if (!Number.isFinite(deltaEstM) || !Number.isFinite(deltaNordM)) return calage;
  // Translation RIGIDE dans le plan tangent : le MÊME décalage lng/lat est appliqué aux deux
  // ancres (cosinus de latitude pris UNE fois, sur l'ancre d'origine — comme
  // `pointImageSurCarte` le fait pour les quatre coins). Deux cosinus différents
  // déformeraient légèrement le fond à chaque glissé.
  const origine = calage.ancre[0];
  const arrivee = depuisOffsetM(origine, deltaEstM, deltaNordM);
  const dLng = arrivee[0] - origine[0];
  const dLat = arrivee[1] - origine[1];
  const bouge = (p: LngLat): LngLat => [p[0] + dLng, p[1] + dLat];
  return { ...calage, ancre: [bouge(calage.ancre[0]), bouge(calage.ancre[1])] };
}

/**
 * CALX108 — MOLETTE : fait tourner le fond de `deltaDeg` (sens horaire). Seule la rotation
 * RETENUE bouge ; `pointsImage`, `ancre`, `distanceReelleM` et donc le facteur d'échelle
 * restent identiques — tourner un plan ne change pas sa mesure.
 */
export function tournerCalage(calage: CalageDeuxPoints, deltaDeg: number): CalageDeuxPoints {
  if (!Number.isFinite(deltaDeg)) return calage;
  const verdict = caleDeuxPoints(calage.pointsImage, calage.ancre, calage.distanceReelleM, calage.source);
  const actuelle =
    typeof calage.rotationDeg === 'number' && Number.isFinite(calage.rotationDeg)
      ? calage.rotationDeg
      : verdict.ok
        ? verdict.calibration.rotationDeg
        : 0;
  return { ...calage, rotationDeg: (((actuelle + deltaDeg) % 360) + 360) % 360 };
}
