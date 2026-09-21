/**
 * Calepinage HAUTE FIDÉLITÉ : vrais panneaux Canadian Solar 720 W, vrai plein sud
 * géo-ancré, et ESPACEMENT INTER-RANGÉES calculé par la géométrie solaire réelle
 * (pour qu'une rangée n'ombrage pas la suivante au soleil de référence).
 *
 * Diffère de src/lib/roofPro.ts (1,7 × 1,0 m / 550 W) : ici le panneau est le vrai
 * CS7N-690-720TB-AG (2384 × 1303 × 33 mm, 0,72 kWc), monté PAYSAGE. Le pas de
 * rangée vient du soleil : rise = petit côté × sin(tilt) ; élévation de design =
 * midi au solstice d'hiver ≈ 90° − |lat| − 23,44° ; ombre = rise ÷ tan(élévation) ;
 * pas ≥ empreinte + ombre → aucune rangée n'ombre la suivante à cet angle.
 *
 * Le nombre de panneaux RÉELLEMENT posés pilote kWc (= n × 0,72) → production
 * PVGIS → économies. Géométrie pure, testée (tests/roofPro2.test.ts). RÉUTILISE
 * roof.ts (aire géodésique, point-dans-polygone) — roof.ts n'est PAS modifié.
 * Voir apps/web/SOLAR_3D_PRO2_NOTES.md. JAMAIS un devis : une fourchette.
 */
import { geodesicAreaM2, pointInPolygon, type LngLat } from './roof';
// CALX95 — retrait propre à une arête physique du contour (géométrie pure, en mètres).
import { rognerParArete } from './roofSetbackEdge';

// — Vrai panneau Canadian Solar TOPBiHiKu7 CS7N-690-720TB-AG —
export const PANEL2_LONG_M = 2.384; // grand côté (horizontal en paysage, le long de la rangée)
export const PANEL2_SHORT_M = 1.303; // petit côté (dans le sens de la pente)
export const PANEL2_THICK_M = 0.033;
export const PANEL2_WATT = 720; // 0,72 kWc par panneau

/**
 * CALX109 — LES COTES D'UN MODULE, telles que le pavage les consomme.
 * Quatre grandeurs et rien d'autre : le grand côté (le long de la rangée), le petit côté
 * (dans le sens de la pente), l'épaisseur (rendu 3D uniquement) et la puissance unitaire.
 * Toutes en MÈTRES / Wc — c'est l'unité du moteur ; le document, lui, parle en millimètres
 * (`modules[].longueurMm`…) et c'est `roofPro11/moduleSelect.ts` qui convertit, une fois.
 */
export interface Panel2Module {
  /** Grand côté (m) — horizontal en paysage, le long de la rangée. */
  longM: number;
  /** Petit côté (m) — dans le sens de la pente, celui qui pilote le pas de rangée. */
  courtM: number;
  /** Épaisseur (m). `null` = non renseignée : la scène ne l'invente pas. */
  epaisM: number | null;
  /** Puissance crête unitaire (Wc). */
  watt: number;
}

/**
 * CALX109 — LE MODULE PAR DÉFAUT DE L'ATELIER, nommé une bonne fois.
 *
 * Les quatre constantes ci-dessus décrivent le SEUL module que l'atelier savait poser
 * avant CALX109. Elles restent le repli — mais un repli EXPLICITE et NOMMÉ : tant qu'aucun
 * module n'est choisi dans le catalogue de la société (`zones[].geometry.moduleId`, CALX82),
 * c'est CE module-là qui est pavé, et l'atelier le dit. Ce n'est jamais un repli muet sur
 * lequel un pan qui désigne un autre modèle retomberait en silence.
 */
export const MODULE_ATELIER_PAR_DEFAUT: Panel2Module = {
  longM: PANEL2_LONG_M,
  courtM: PANEL2_SHORT_M,
  epaisM: PANEL2_THICK_M,
  watt: PANEL2_WATT,
};

/**
 * CALX109 câblage — LES COTES QUE LE PAVAGE APPLIQUE RÉELLEMENT.
 *
 * Les deux moteurs de pavage (`estimatorBrainV2.packConfig` toit plat,
 * `estimatorBrainV3.packFlushPlane` toit en pente) lisent leurs dimensions ICI, et nulle
 * part ailleurs : une seule règle, donc jamais deux interprétations du même module.
 *
 * OPTION ABSENTE ⇒ `MODULE_ATELIER_PAR_DEFAUT` lui-même, donc pavage IDENTIQUE octet pour
 * octet à celui d'aujourd'hui. Une cote non finie ou ≤ 0 n'est jamais « corrigée » en
 * silence par une dimension standard : elle fait retomber sur le module par défaut, NOMMÉ
 * (le refus détaillé, lui, est prononcé en amont par `moduleSelect.cotesDeModule`, qui
 * nomme le champ manquant avant même qu'un module sans cote atteigne le pavage).
 *
 * Le grand côté est TOUJOURS `longM` : un pavage se raisonne « le long de la rangée » /
 * « dans le sens de la pente », pas en longueur/largeur de fiche produit.
 */
export function cotesDePavage(module?: Panel2Module | null): Panel2Module {
  if (!module) return MODULE_ATELIER_PAR_DEFAUT;
  const exploitable = (v: unknown): v is number =>
    typeof v === 'number' && Number.isFinite(v) && v > 0;
  if (!exploitable(module.longM) || !exploitable(module.courtM) || !exploitable(module.watt)) {
    return MODULE_ATELIER_PAR_DEFAUT;
  }
  return {
    longM: Math.max(module.longM, module.courtM),
    courtM: Math.min(module.longM, module.courtM),
    epaisM: exploitable(module.epaisM) ? module.epaisM : null,
    watt: module.watt,
  };
}

// — Décisions géométriques (ajustables ici) —
export const PANEL2_TILT_DEG = 13; // inclinaison toit plat (plage densité 12–15°)
export const PERIMETER_SETBACK_M = 0.5; // retrait de rive (valeur par défaut des trois)

/**
 * PV63 — RETRAITS DE RIVE. Un seul chiffre pour tout le pourtour est un raccourci :
 * sur un toit réel, le recul n'est pas le même selon le bord.
 *  - `lateralM` : de part et d'autre des rangées (le long de leur axe) — passage de
 *    maintenance latéral ;
 *  - `extremityM` : en BOUT de rangée, dans le sens d'empilement (première et dernière
 *    rangée) — c'est là qu'on garde le chemin de circulation ;
 *  - `parapetM` : distance minimale à N'IMPORTE QUELLE rive du tracé (acrotère, garde-
 *    corps, bord de dalle) — la contrainte de sécurité, appliquée à chaque coin de panneau.
 *    Nommage aligné sur le moteur partagé (`core/calepinage/types.py Rives.acrotere_m`) :
 *    « acrotère » est le mot AFFICHÉ, `parapetM` la clé conservée côté outil (renommer la
 *    clé casserait tous les appelants existants sans rien changer pour l'utilisateur).
 *  - `jointM` (CAL76) — 4ᵉ rive, alignée sur `Rives.joint_m` du moteur : un retrait
 *    D'EXTRÉMITÉ SUPPLÉMENTAIRE (joint de dilatation / de construction en bout de
 *    rangée), qui s'AJOUTE à `extremityM` — jamais ne le remplace, exactement comme le
 *    moteur calcule `extremite_totale_m = extremite_m + joint_m`. Voir `extremityTotalM`.
 * Les trois retraits historiques valent `PERIMETER_SETBACK_M` par défaut ; `jointM` vaut
 * 0 par défaut (il n'existait pas avant CAL76) : le calepinage est alors IDENTIQUE au
 * comportement historique.
 */
export interface PerimeterSetbacks {
  lateralM: number;
  extremityM: number;
  parapetM: number;
  /** CAL76 — 4ᵉ rive « joint » : défaut 0 (aucun effet tant qu'il n'est pas saisi). */
  jointM: number;
}

/** Les trois retraits historiques à une même valeur (défaut : la marge de design) ;
 *  le joint (CAL76) démarre à 0 — il n'a jamais fait partie de ce défaut uniforme. */
export function uniformSetbacks(m: number = PERIMETER_SETBACK_M): PerimeterSetbacks {
  return { lateralM: m, extremityM: m, parapetM: m, jointM: 0 };
}

/**
 * Retraits utilisables par le calepinage. Une valeur SAISIE n'est jamais arrondie ni
 * « snappée » : on ne remplace que ce qui n'a aucun sens géométrique — non finie
 * (champ vide, texte) → la valeur de repli ; négative → 0 (pleine rive). L'interface,
 * elle, AVERTIT au lieu de rejeter la frappe. `jointM` (CAL76) replie sur 0, jamais sur
 * `fallbackM` : un document sans joint saisi doit rester identique au comportement
 * d'avant CAL76, pas hériter silencieusement du retrait de rive par défaut.
 */
export function resolveSetbacks(
  s: Partial<PerimeterSetbacks> | undefined,
  fallbackM: number = PERIMETER_SETBACK_M,
): PerimeterSetbacks {
  const one = (v: number | undefined, fallback: number): number => {
    if (typeof v !== 'number' || !Number.isFinite(v)) return fallback;
    return v < 0 ? 0 : v;
  };
  return {
    lateralM: one(s?.lateralM, fallbackM),
    extremityM: one(s?.extremityM, fallbackM),
    parapetM: one(s?.parapetM, fallbackM),
    jointM: one(s?.jointM, 0),
  };
}

/**
 * CAL76 — retrait LATÉRAL TOTAL (rive + acrotère), affiché à côté du champ pour que
 * personne n'ait à additionner à la main. Miroir exact de
 * `core/calepinage/types.py Rives.laterale_totale_m` (`laterale_m + acrotere_m`).
 */
export function lateralTotalM(s: PerimeterSetbacks): number {
  return s.lateralM + s.parapetM;
}

/**
 * CAL76 — retrait D'EXTRÉMITÉ TOTAL (rive d'extrémité + joint), affiché à côté du champ.
 * Miroir exact de `core/calepinage/types.py Rives.extremite_totale_m`
 * (`extremite_m + joint_m`) — c'est CE total, jamais `extremityM` seul, qui doit être
 * appliqué au pavage pour que le joint ait un effet réel (voir estimatorBrainV2/V3).
 */
export function extremityTotalM(s: PerimeterSetbacks): number {
  return s.extremityM + s.jointM;
}

/** PV63 — au-delà de ce retrait, on AVERTIT (sans jamais refuser) : c'est inhabituel. */
export const SETBACK_UNUSUAL_M = 3;

/**
 * PV63 — lecture d'un champ « retrait » SAISI. Règle de la maison : on n'ARRONDIT jamais
 * et on ne REJETTE jamais une frappe — on lit la valeur telle quelle et on AVERTIT quand
 * elle est douteuse. Les seuls cas où la valeur n'est pas utilisable telle quelle :
 *  - champ vide / illisible → on GARDE le retrait précédent (rien ne bouge sous les doigts) ;
 *  - valeur négative → 0 m (pleine rive), avec avertissement — un retrait négatif n'existe pas.
 * Une valeur grande mais valide (ex. 4 m) est ACCEPTÉE telle quelle, avec un simple
 * avertissement. Accepte la virgule décimale française et les espaces.
 */
export function readSetbackInput(raw: string, previousM: number): { valueM: number; warning: string | null } {
  const cleaned = String(raw ?? '').replace(/\s/g, '').replace(',', '.');
  if (cleaned === '') return { valueM: previousM, warning: 'Champ vide — le retrait précédent est conservé.' };
  const v = Number(cleaned);
  if (!Number.isFinite(v)) {
    return { valueM: previousM, warning: 'Valeur illisible — le retrait précédent est conservé.' };
  }
  if (v < 0) {
    return { valueM: 0, warning: 'Un retrait négatif n’existe pas : 0 m (pleine rive) est appliqué.' };
  }
  if (v > SETBACK_UNUSUAL_M) {
    return { valueM: v, warning: `Retrait inhabituel (${v} m) — appliqué tel quel, vérifiez la valeur.` };
  }
  return { valueM: v, warning: null };
}
export const PANEL_SIDE_GAP_M = 0.02; // jeu entre panneaux d'une rangée
export const FRONT_STRUT_M = 0.1; // hauteur du montant avant (bas) du châssis
export const SOLAR_DECLINATION_DEG = 23.44; // déclinaison au solstice
export const SHADOW_MARGIN_M = 0.05; // petite marge en plus de l'ombre calculée

const WGS84_RADIUS = 6378137;
const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * WGS84_RADIUS;
const MAX_CELLS = 200000;

export interface ProPanel {
  cx: number;
  cy: number;
}

export interface ProLayout2 {
  origin: LngLat;
  ringENU: [number, number][];
  panels: ProPanel[];
  count: number;
  /** Puissance crête (kWc) = nombre × 0,72. */
  kwc: number;
  areaM2: number;
  rowAngleRad: number;
  tiltRad: number;
  /** Azimut RÉEL visé (degrés, 0=N, 90=E, 180=S, 270=O). */
  azimuthDeg: number;
  /** Latitude du toit (degrés) — pour positionner le soleil. */
  latitudeDeg: number;
  /** Élévation solaire de design pour l'espacement (degrés, solstice d'hiver). */
  designElevDeg: number;
  /** Pas de rangée appliqué (m, centre à centre dans le sens de la pente). */
  rowPitchM: number;
  dims: {
    alongRow: number;
    slope: number;
    depthFootprint: number;
    rise: number;
    frontStrut: number;
  };
}

/** Orientation FR → azimut réel (degrés, 0=Nord, 90=Est, 180=Sud, 270=Ouest). */
export function orientationToAzimuthDeg(orientation: string): number {
  switch (orientation) {
    case 'nord':
      return 0;
    case 'est':
      return 90;
    case 'ouest':
      return 270;
    case 'sud-est':
      return 135;
    case 'sud-ouest':
      return 225;
    case 'sud':
    case 'inconnu':
    default:
      return 180; // plein sud (optimal au Maroc) par défaut
  }
}

// ═══════════ CAL86 — AFFICHER le pas inter-rangées, et NOMMER la famille de pose ═══════════
// Le pas EXISTE et alimente déjà les rangées (`rowPitchM` ci-dessous, consommé par le
// pavage) : ce qui manquait, c'est son AFFICHAGE et le nom de la famille de pose. Rien
// n'est recalculé ici — `describeRowPitch` REÇOIT le pas réellement appliqué et se
// contente de l'habiller de l'hypothèse qui l'a produit. Aucun second calcul de pas
// n'est introduit (le pavage reste la source unique, harmonisée avec le moteur par CAL167).

/** CAL86 — famille de pose d'un toit PLAT : châssis inclinés posés dans des bacs lestés
 *  (aucun perçage de l'étanchéité). C'est la famille que l'atelier pose aujourd'hui ; elle
 *  n'était simplement jamais nommée à l'écran. */
export const MOUNTING_FAMILY_BALLASTED = 'Bacs lestés inclinés';
/** CAL86 — famille de pose d'un toit EN PENTE : modules affleurants sur la couverture. */
export const MOUNTING_FAMILY_FLUSH = 'Pose affleurante sur pente';

/** CAL86 — ce qui est AFFICHÉ à propos du pas inter-rangées : le pas appliqué, la famille
 *  de pose, et l'hypothèse d'élévation solaire qui a produit ce pas. */
export interface RowPitchDisclosure {
  /** Pas RÉELLEMENT appliqué par le pavage (m, centre à centre). */
  rowPitchM: number;
  /** Famille de pose, nommée. */
  family: string;
  /** Pose affleurante (pente) : il n'y a alors PAS d'espacement solaire. */
  flush: boolean;
  /** Élévation solaire de design (°) ayant produit le pas — null en pose affleurante
   *  (aucune hypothèse solaire n'intervient : les rangées sont jointives). */
  designElevDeg: number | null;
  /** Phrase prête à afficher, hypothèse comprise. */
  label: string;
}

/**
 * CAL86 — habille le pas inter-rangées DÉJÀ calculé par le pavage. `rowPitchM` est la
 * valeur appliquée (lue du plan), `latitudeDeg` la latitude du site (source de
 * l'hypothèse d'élévation, CAL167). AUCUN pas n'est recalculé ici.
 */
export function describeRowPitch(opts: {
  rowPitchM: number;
  latitudeDeg: number;
  flush?: boolean;
  configFamily?: 'south' | 'eastwest';
}): RowPitchDisclosure {
  const flush = !!opts.flush;
  const rowPitchM = Number.isFinite(opts.rowPitchM) && opts.rowPitchM > 0 ? opts.rowPitchM : 0;
  const family = flush ? MOUNTING_FAMILY_FLUSH : MOUNTING_FAMILY_BALLASTED;
  const designElevDeg = flush ? null : designSunElevationDeg(opts.latitudeDeg);
  const pas = rowPitchM.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const ew = opts.configFamily === 'eastwest' ? ' (pas entre chevrons est-ouest)' : '';
  const label = flush
    ? `${family} — rangées jointives : pas de ${pas} m${ew}, aucun espacement anti-ombrage (la pente porte les modules).`
    : `${family} — pas entre rangées ${pas} m${ew}, calé sur une élévation solaire de ` +
      `${(designElevDeg as number).toLocaleString('fr-FR', { maximumFractionDigits: 1 })}° ` +
      `(midi au solstice d’hiver à la latitude du site, ${opts.latitudeDeg.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}°).`;
  return { rowPitchM, family, flush, designElevDeg, label };
}

/** Élévation solaire de design (midi solstice d'hiver) pour l'espacement anti-ombrage. */
export function designSunElevationDeg(latitudeDeg: number): number {
  return Math.max(8, 90 - Math.abs(latitudeDeg) - SOLAR_DECLINATION_DEG);
}

/** Solstice d'hiver de l'hémisphère NORD ≈ 21 décembre (jour 355) → pire cas d'ombrage. */
export const WINTER_SOLSTICE_DAY = 355;

/** Position du soleil renvoyée par `sunDirection`. */
export interface SunDirection {
  /** Élévation au-dessus de l'horizon (degrés ; < 0 = sous l'horizon, nuit). */
  elevationDeg: number;
  /** Azimut RÉEL (degrés, 0 = Nord, 90 = Est, 180 = Sud, 270 = Ouest). */
  azimuthDeg: number;
}

/**
 * VRAIE position du soleil pour une latitude, un jour de l'année et une heure
 * solaire locale — astronomie standard (déclinaison + angle horaire), pas un
 * soleil arbitraire. Sert à PROUVER l'espacement anti-ombrage : au midi du
 * solstice d'hiver (pire cas), l'élévation rejoint `designSunElevationDeg` —
 * donc les rangées espacées par ce même angle se dégagent visiblement.
 *
 * - `dayOfYear` : 1 (1ᵉʳ janv.) … 365 ; le solstice d'hiver nord ≈ 355.
 * - `hour` : heure solaire locale, 0–24 (midi solaire = 12).
 *
 * Déclinaison δ = −23,44° × cos(360° × (jour + 10) / 365) (modèle cosinus
 * usuel, `SOLAR_DECLINATION_DEG` = 23,44). Angle horaire H = 15° × (heure − 12).
 * sin(élév) = sin φ sin δ + cos φ cos δ cos H ; l'azimut est dérivé de
 * l'élévation, signé par le matin (Est) / l'après-midi (Ouest).
 */
export function sunDirection(latDeg: number, dayOfYear: number, hour: number): SunDirection {
  const lat = latDeg * DEG2RAD;
  const decl = -SOLAR_DECLINATION_DEG * Math.cos((2 * Math.PI * (dayOfYear + 10)) / 365) * DEG2RAD;
  const hourAngle = (hour - 12) * 15 * DEG2RAD; // 15°/h, négatif le matin
  const sinElev = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(hourAngle);
  const elev = Math.asin(Math.max(-1, Math.min(1, sinElev)));
  // Azimut mesuré depuis le Nord en tournant vers l'Est. cos(az) à partir de la
  // déclinaison, signe (Est le matin, Ouest l'après-midi) à partir de l'angle horaire.
  const cosAz = (Math.sin(decl) - Math.sin(elev) * Math.sin(lat)) / (Math.cos(elev) * Math.cos(lat) || 1e-9);
  let az = Math.acos(Math.max(-1, Math.min(1, cosAz))); // 0..π depuis le Nord
  if (hourAngle > 0) az = 2 * Math.PI - az; // après-midi → côté Ouest (>180°)
  return { elevationDeg: elev / DEG2RAD, azimuthDeg: (az / DEG2RAD + 360) % 360 };
}

function distToSegment(p: [number, number], a: [number, number], b: [number, number]): number {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

function distToBoundary(p: [number, number], ring: [number, number][]): number {
  let min = Infinity;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    min = Math.min(min, distToSegment(p, ring[j], ring[i]));
  }
  return min;
}

export interface ProLayout2Options {
  /** Inclinaison en degrés (toit plat ≈ 13 ; toit en pente villa = pente). */
  tiltDeg?: number;
  /** Pose affleurante (toit en pente) : rangées jointives, pas d'espacement solaire. */
  flush?: boolean;
  /**
   * CALX95 — retrait PROPRE à certaines arêtes du contour, en SUPPLÉMENT du retrait de
   * catégorie appliqué au pourtour entier. Table `rang du segment → mètres`, dans la forme
   * que produit `roofSetbackEdge.supplementsParArete` depuis `zones[].edges[].retraitM`
   * (CALX81) : le segment `i` va de `ring[i]` à `ring[i + 1]`. OPTIONNEL et additif —
   * absent ou vide, le calepinage est IDENTIQUE à celui d'aujourd'hui (aucune arête n'est
   * rognée, aucune valeur n'est supposée). Un segment absent de la table n'ajoute rien :
   * seul le réglage de catégorie s'applique.
   */
  retraitsParAreteM?: Readonly<Record<number, number>>;
   /**
   * CALX109 — le module RÉELLEMENT posé sur ce pan, avec ses cotes de fiche. Optionnel et
   * additif : absent ⇒ `MODULE_ATELIER_PAR_DEFAUT`, donc un pavage IDENTIQUE à celui
   * d'avant CALX109, au panneau près. Présent, ses cotes remplacent les constantes dans la
   * maille ET dans le pas de rangée (un module plus court ombrage moins loin), et sa
   * puissance remplace `PANEL2_WATT` dans le kWc.
   */
  module?: Panel2Module;
}

/**
 * Dispose les rangées de vrais panneaux 720 W. Sur toit plat, le pas de rangée est
 * calculé par la géométrie solaire (anti-ombrage) à la latitude du toit. Un panneau
 * n'est retenu que si ses 4 coins (empreinte) sont DANS le tracé ET à au moins
 * `PERIMETER_SETBACK_M` de la rive.
 *
 * CALX95 — `opts.retraitsParAreteM` rogne EN PLUS le contour le long des seules arêtes qui
 * portent un retrait SAISI (`zones[].edges[].retraitM`, CALX81) : les panneaux sont alors
 * jugés contre cet anneau posable. Option absente ou vide ⇒ anneau posable = tracé, et le
 * pavage est celui d'aujourd'hui, à l'identique.
 */
export function layoutProRows2(
  ring: LngLat[],
  orientation = 'sud',
  latitudeDeg = 33.5,
  opts: ProLayout2Options = {},
): ProLayout2 {
  const areaM2 = geodesicAreaM2(ring);
  const tiltDeg = opts.tiltDeg ?? PANEL2_TILT_DEG;
  const tiltRad = tiltDeg * DEG2RAD;
  const azimuthDeg = orientationToAzimuthDeg(orientation);
  const designElevDeg = designSunElevationDeg(latitudeDeg);

  // CALX109 — les cotes viennent du module CHOISI ; sans choix, du module par défaut de
  // l'atelier (constantes historiques), donc le pavage est inchangé au panneau près.
  const moduleP = opts.module ?? MODULE_ATELIER_PAR_DEFAUT;
  const alongRow = moduleP.longM; // grand côté, le long de la rangée (paysage)
  const slope = moduleP.courtM; // petit côté, dans le sens de la pente
  const depthFootprint = slope * Math.cos(tiltRad);
  const rise = slope * Math.sin(tiltRad);
  // Ombre projetée par une rangée au soleil de design + empreinte = pas mini.
  const shadowLen = opts.flush ? 0 : rise / Math.tan(designElevDeg * DEG2RAD);
  const rowPitchM = opts.flush ? depthFootprint : depthFootprint + shadowLen + SHADOW_MARGIN_M;
  const colPitch = alongRow + PANEL_SIDE_GAP_M;
  const dims = { alongRow, slope, depthFootprint, rise, frontStrut: FRONT_STRUT_M };

  const empty: ProLayout2 = {
    origin: ring.length ? ring[0] : [0, 0],
    ringENU: [],
    panels: [],
    count: 0,
    kwc: 0,
    areaM2,
    rowAngleRad: 0,
    tiltRad,
    azimuthDeg,
    latitudeDeg,
    designElevDeg,
    rowPitchM,
    dims,
  };
  if (!Array.isArray(ring) || ring.length < 3) return empty;

  let olng = 0;
  let olat = 0;
  for (const [lng, lat] of ring) {
    olng += lng;
    olat += lat;
  }
  olng /= ring.length;
  olat /= ring.length;
  const cosLat = Math.cos(olat * DEG2RAD);
  const toENU = ([lng, lat]: LngLat): [number, number] => [
    (lng - olng) * DEG2M * cosLat,
    (lat - olat) * DEG2M,
  ];
  const ringENU = ring.map(toENU);

  // Vecteur de visée réel depuis l'azimut (E = sin az, N = cos az).
  const azRad = azimuthDeg * DEG2RAD;
  const f: [number, number] = [Math.sin(azRad), Math.cos(azRad)];
  const s: [number, number] = f; // les rangées s'empilent vers la visée
  const u: [number, number] = [-f[1], f[0]]; // axe long des rangées
  const rowAngleRad = Math.atan2(u[1], u[0]);

  const ringUV = ringENU.map(([x, y]) => [x * u[0] + y * u[1], x * s[0] + y * s[1]] as [number, number]);
  let uMin = Infinity;
  let uMax = -Infinity;
  let vMin = Infinity;
  let vMax = -Infinity;
  for (const [uu, vv] of ringUV) {
    if (uu < uMin) uMin = uu;
    if (uu > uMax) uMax = uu;
    if (vv < vMin) vMin = vv;
    if (vv > vMax) vMax = vv;
  }

  const rows = Math.floor((vMax - vMin) / rowPitchM);
  const cols = Math.floor((uMax - uMin) / colPitch);
  if (rows <= 0 || cols <= 0 || (rows + 1) * (cols + 1) > MAX_CELLS) {
    return { ...empty, origin: [olng, olat], ringENU };
  }

  const toENUfromUV = (uu: number, vv: number): [number, number] => [
    uu * u[0] + vv * s[0],
    uu * u[1] + vv * s[1],
  ];
  // CALX95 — anneau POSABLE : le contour rogné des retraits propres à certaines arêtes,
  // EN PLUS du retrait de catégorie que `ok()` mesure ci-dessous. Sans aucune arête saisie,
  // `rognerParArete` renvoie le contour tel quel et le pavage est inchangé.
  const ringPosable = rognerParArete(ringENU, opts.retraitsParAreteM ?? {});
  // Les retraits d'arête ont mangé tout le pan : aucune surface posable — on le dit avec un
  // pavage vide plutôt qu'en repliant sur le contour entier (ce serait poser hors retrait).
  if (ringPosable.length < 3) return { ...empty, origin: [olng, olat], ringENU };
  const ok = (corners: [number, number][]): boolean =>
    corners.every((c) => pointInPolygon(c, ringPosable) && distToBoundary(c, ringPosable) >= PERIMETER_SETBACK_M);

  const panels: ProPanel[] = [];
  for (let r = 0; r < rows; r++) {
    const v0 = vMin + PERIMETER_SETBACK_M + r * rowPitchM;
    const v1 = v0 + depthFootprint;
    if (v1 > vMax - PERIMETER_SETBACK_M + 1e-6) break;
    for (let c = 0; c < cols; c++) {
      const u0 = uMin + PERIMETER_SETBACK_M + c * colPitch;
      const u1 = u0 + alongRow;
      const corners: [number, number][] = [
        toENUfromUV(u0, v0),
        toENUfromUV(u1, v0),
        toENUfromUV(u1, v1),
        toENUfromUV(u0, v1),
      ];
      if (!ok(corners)) continue;
      const center = toENUfromUV(u0 + alongRow / 2, v0 + depthFootprint / 2);
      panels.push({ cx: center[0], cy: center[1] });
    }
  }

  return {
    origin: [olng, olat],
    ringENU,
    panels,
    count: panels.length,
    // CALX109 — la puissance est celle du module POSÉ, jamais la constante de l'atelier
    // quand un autre modèle est choisi (sinon deux modèles rendraient le même kWc).
    kwc: (panels.length * moduleP.watt) / 1000,
    areaM2,
    rowAngleRad,
    tiltRad,
    azimuthDeg,
    latitudeDeg,
    designElevDeg,
    rowPitchM,
    dims,
  };
}
