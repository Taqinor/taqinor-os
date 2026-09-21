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
  /** Les quatre coins déjà calculés pour un `plan` (CALX108 les dérive du calage à
   *  deux points). Absents ⇒ le plan n'est pas placé, et le motif le dit. */
  coinsPlan?: readonly LngLat[] | null;
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
  const coins = ressource.coinsPlan;
  if (!Array.isArray(coins) || coins.length !== 4 || !coins.every(estCouple)) {
    return {
      ok: false,
      champ: 'calage',
      motif:
        'Plan non affiché : il n’est pas calé — cliquez deux points sur le plan et saisissez la distance réelle qui les sépare. ' +
        'Aucune échelle n’est déduite du fichier.',
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
