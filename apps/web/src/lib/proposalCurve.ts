/**
 * WJ16 — Courbe « production solaire vs consommation » sur une JOURNÉE type
 * (lever → coucher du soleil), rendue en SVG PUR (aucun DOM, aucun réseau, aucune
 * dépendance). C'est le visuel le plus persuasif de la proposition : il montre la
 * cloche de production solaire (du lever au coucher) recouvrant la consommation
 * du foyer.
 *
 * DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » :
 *  - L'amplitude de la cloche est CALÉE sur la production journalière moyenne RÉELLE
 *    (`prod_kwh` annuel backend / 365) quand elle est fournie : l'axe porte alors
 *    des kWh réels.
 *  - Sans production annuelle, on dessine une cloche NORMALISÉE clairement libellée
 *    « profil — année type » (forme illustrative, AUCUN chiffre d'axe) — le visuel
 *    le plus persuasif ne disparaît jamais, mais ne ment pas non plus.
 *  - WJ119 — la forme horaire de consommation N'EST PLUS une double-gaussienne
 *    générique : elle porte une silhouette marocaine soirée-dominante, avec des
 *    variantes été/Ramadan et des profils dédiés par MODE (industriel équipes,
 *    commercial, agricole pompage). Reste un PROFIL, jamais une donnée chiffrée
 *    inventée.
 *  - CJ1 (21/08/2026) — LE GRAPHE DEVIENT VRAI. Le backend sert désormais un
 *    bloc additif `courbes_journalieres` (apps/ventes/courbes_journalieres.py) :
 *    forme de production PVGIS par saison (24 parts, heure locale, somme 1),
 *    énergie `kwh_jour` et PUISSANCE de pointe `pic_kw` du devis, et le niveau
 *    RÉEL de consommation par saison (moyenne des factures du lead). Trois
 *    conséquences ici :
 *      (a) la cloche sin² n'est plus dessinée quand une forme PVGIS est servie ;
 *      (b) le repère de pointe est libellé en **kW** — c'est une PUISSANCE ;
 *          l'ancien « pic ≈ 14,3 kWh » confondait énergie et puissance ;
 *      (c) la silhouette de consommation est mise à l'échelle du VRAI kWh/jour
 *          du client, donc les deux courbes partagent enfin un axe réel — c'est
 *          ce qui rend la phrase « ajusté à votre facture » exacte.
 *    Bloc absent (le cas fréquent) ⇒ RIEN ne change : repli byte-identique sur
 *    la cloche sin² + `prod_kwh/365` et la silhouette normalisée.
 *  - CJ1 — les silhouettes résidentielles sont désormais TROIS (présent/absent/
 *    partiel en journée, dayProfiles.ts) au lieu de l'unique `BASELINE_SHAPE` :
 *    le visiteur choisit la sienne, le serveur en propose une par défaut.
 *
 * Mouvement : l'animation (tracé de la courbe + soleil qui se lève) est gérée 100 %
 * en CSS dans la page et GATÉE derrière `prefers-reduced-motion: no-preference` —
 * ce module n'émet que la géométrie statique (zéro CLS, lisible sans JS ni motion).
 */
import {
  OCCUPANCY_SHAPES,
  SEASON_INLINE,
  type OccupancyId,
  type RamadanWindow,
  type SeasonId,
  type ServedProduction,
} from './dayProfiles';

/** Heures représentées (5 h → 21 h), pas horaire. */
const HOUR_START = 5;
const HOUR_END = 21;
const HOURS = HOUR_END - HOUR_START; // 16

/**
 * Profil de production solaire normalisé (cloche centrée midi solaire ≈ 13 h).
 * Valeur ∈ [0,1] par heure ; 0 avant le lever / après le coucher. Forme standard
 * (sinus carré sur la fenêtre de jour), pas une donnée mesurée.
 */
export function solarProfile(hour: number): number {
  const sunrise = 6.5;
  const sunset = 19.5;
  if (hour <= sunrise || hour >= sunset) return 0;
  const t = (hour - sunrise) / (sunset - sunrise); // 0..1
  const s = Math.sin(Math.PI * t);
  return s * s; // cloche douce, pic à midi solaire
}

// ════════════════════════════════════════════════════════════════════════════
// WJ119 — Silhouette de consommation RÉELLEMENT marocaine, par MODE (résidentiel/
// industriel/commercial/agricole) + variante (normale/été/Ramadan). Chaque forme
// est un tableau de 24 poids (heure 0-23), jamais une donnée chiffrée : normalisée
// à son propre maximum (∈ [0,1]) juste avant l'échantillonnage, exactement comme
// l'ancienne double-gaussienne qu'elle remplace.
// ════════════════════════════════════════════════════════════════════════════

/** Les 4 marchés reconnus par le générateur de devis (residentiel par défaut). */
export type ProposalCurveMode = 'residentiel' | 'industriel' | 'commercial' | 'agricole';

/** Variante saisonnière/religieuse — n'a de sens que pour résidentiel/commercial. */
export type ProposalCurveVariant = 'normal' | 'ete' | 'ramadan';

/** Régime d'équipes d'un site industriel — 1x8 par défaut (aucun champ backend
 *  ne le porte encore aujourd'hui, cf. resolveProposalCurveMode). */
export type IndustrialShift = '1x8' | '2x8' | '3x8';

export interface ConsumptionShapeOptions {
  mode?: ProposalCurveMode;
  variant?: ProposalCurveVariant;
  industrialShift?: IndustrialShift;
  /**
   * CJ1 — silhouette d'occupation RÉSIDENTIELLE choisie (présent / absent /
   * partiel en journée). Ignorée hors résidentiel : une usine ou un forage
   * n'a pas d'« occupation du logement ». Absente ⇒ `presence_partielle`, le
   * milieu honnête des trois (dayProfiles.occupancyFromFlag).
   */
  occupancy?: OccupancyId;
  /**
   * CJ1 — fenêtre de Ramadan CALCULÉE par date + coordonnées du chantier
   * (dayProfiles.ramadanWindow). Seules les deux heures comptent ici, donc le
   * type est volontairement MINIMAL : le script client peut passer les deux
   * nombres sérialisés sans reconstruire un `RamadanWindow` complet, et un
   * `RamadanWindow` reste accepté tel quel. `null`/absente ⇒ repli documenté
   * `RAMADAN_FALLBACK_WINDOW`, jamais une heure présentée comme calculée.
   */
  ramadan?: Pick<RamadanWindow, 'imsakHour' | 'iftarHour'> | null;
}

/**
 * WJ119 — Normalise le champ backend `ProposalQuote.inst_type` (valeurs
 * OBSERVÉES aujourd'hui : "Résidentielle" / "Industrielle / Commerciale" /
 * "Agricole" — builder.py `inst_type = {...}.get(mode, "Résidentielle")") ou une
 * future clé machine minuscule (residentiel/industriel/commercial/agricole/
 * professionnel — ce dernier étant le nom interne du mode "industriel" côté
 * simulateur, mon-toit.astro MODE_LABEL) en l'un des 4 modes de courbe reconnus.
 * Absent/inconnu → 'residentiel' (repli honnête, jamais un mode fabriqué). Le
 * backend NE DISTINGUE PAS ENCORE industriel de commercial (une seule catégorie
 * combinée "Industrielle / Commerciale" — la table d'archétypes par catégorie
 * QX44 n'est pas construite) : le combiné retombe sur 'industriel', son mode
 * interne réel, tant qu'aucun champ ne permet de séparer les deux.
 */
export function resolveProposalCurveMode(instType: string | null | undefined): ProposalCurveMode {
  const s = (instType ?? '').trim().toLowerCase();
  if (!s) return 'residentiel';
  if (s.includes('agricole') || s.includes('pompage')) return 'agricole';
  if (s.includes('commercial') && !s.includes('industriel')) return 'commercial';
  if (s.includes('industriel') || s.includes('professionnel')) return 'industriel';
  return 'residentiel';
}

/** Normalise une forme brute (poids quelconques ≥ 0) à son propre maximum (∈ [0,1]). */
function normalizeShape(shape: readonly number[]): number[] {
  let max = 0;
  for (const w of shape) if (Number.isFinite(w) && w > max) max = w;
  if (max <= 0) return shape.map(() => 0);
  return shape.map((w) => (Number.isFinite(w) && w > 0 ? w / max : 0));
}

/** Échantillonne une forme normalisée de 24 poids (heure 0-23) à une heure
 *  QUELCONQUE (interpolation linéaire entre les deux heures entières voisines,
 *  circulaire — minuit suit 23 h). */
function sampleShape(shape: readonly number[], hour: number): number {
  const h = ((hour % 24) + 24) % 24;
  const h0 = Math.floor(h);
  const h1 = (h0 + 1) % 24;
  const frac = h - h0;
  const v0 = shape[h0] ?? 0;
  const v1 = shape[h1] ?? 0;
  return v0 + (v1 - v0) * frac;
}

/**
 * WJ119/CJ1 — été/intérieur : +50 % sur la fenêtre de climatisation.
 *
 * La fenêtre était 13h-18h ; elle court désormais de 13h à 21h INCLUS. Raison
 * sourcée : les guides d'usage de la climatisation (et la fenêtre de pointe
 * ONEE elle-même, 18h-23h en été — one.org.ma) situent le pic de sollicitation
 * des splits l'après-midi ET en début de soirée, quand l'inertie du bâtiment
 * restitue la chaleur de la journée. S'arrêter à 18h coupait exactement la
 * moitié du phénomène. Le MULTIPLICATEUR (×1.5) reste une ESTIMATION, à
 * confirmer avec des factures d'été réelles (APPLIANCES_NOTES.md).
 *
 * C'est un MODIFICATEUR ORTHOGONAL : il s'applique à la silhouette de base
 * choisie (occupation), il ne la remplace pas. Il n'a de sens que pour la
 * saison « été » — mais il reste une PUCE que le visiteur clique, jamais un
 * effet appliqué d'office : la page ne décide pas à sa place s'il climatise.
 */
const SUMMER_BOOST_HOURS: readonly number[] = [13, 14, 15, 16, 17, 18, 19, 20, 21];
const SUMMER_BOOST_MULT = 1.5;

/**
 * WJ119/CJ1 — Ramadan : journée de jeûne −35 %, bosse suhoor ×2.5 sur les 2 h
 * qui précèdent l'imsak, pic iftar ×1.8 sur l'heure de la rupture du jeûne.
 * Les MAGNITUDES sont inchangées (ordres de grandeur documentés, jamais des
 * mesures) ; ce qui change, c'est que les HEURES ne sont plus codées en dur.
 *
 * Avant : « jour 6h-18h, suhoor 3h-5h, iftar 19h ». Ces heures n'étaient vraies
 * que pour un Ramadan d'ÉTÉ — or le Ramadan recule de ~11 jours par an et se
 * tient en hiver jusqu'en 2033. Un iftar figé à 19 h se trompait de plus d'une
 * heure. Elles viennent maintenant de `dayProfiles.ramadanWindow` (coucher du
 * soleil NOAA au point GPS du chantier, à la date réelle du mois).
 */
const RAMADAN_DAY_FACTOR = 0.65;
const RAMADAN_SUHOOR_MULT = 2.5;
const RAMADAN_IFTAR_MULT = 1.8;
/** Nombre d'heures de bosse suhoor, juste avant l'imsak (repas avant l'aube). */
const RAMADAN_SUHOOR_HOURS = 2;

/**
 * Repli quand la date sort de la table des plages (après 2033) : les valeurs
 * MÉDIANES d'un Ramadan à Casablanca (imsak ≈ 5h30, iftar ≈ 18h30, heure de
 * Ramadan UTC+0). La forme reste alors plausible, et la page N'AFFICHE AUCUNE
 * heure sur la puce — on ne présente jamais un repli comme un calcul.
 */
export const RAMADAN_FALLBACK_WINDOW: Readonly<{ imsakHour: number; iftarHour: number }> = {
  imsakHour: 5.5,
  iftarHour: 18.5,
};

/** Applique la modulation Ramadan (heures RÉELLES) à une forme de base. */
function applyRamadan(
  out: number[],
  win: { imsakHour: number; iftarHour: number },
): void {
  const wrap = (h: number) => ((h % 24) + 24) % 24;
  const imsak = Math.min(23.999, Math.max(0, win.imsakHour));
  const iftar = Math.min(23.999, Math.max(0, win.iftarHour));
  const iftarHour = Math.floor(iftar);
  // Heures ENTIÈREMENT dans le jeûne : de la 1re heure pleine après l'imsak
  // jusqu'à l'heure d'iftar EXCLUE (celle-là, c'est le repas, pas le jeûne).
  for (let h = Math.ceil(imsak); h < iftarHour; h++) out[wrap(h)] *= RAMADAN_DAY_FACTOR;
  // Suhoor : les 2 h qui précèdent l'imsak (repas avant l'aube).
  const suhoorStart = Math.floor(imsak) - RAMADAN_SUHOOR_HOURS;
  for (let i = 0; i < RAMADAN_SUHOOR_HOURS; i++) out[wrap(suhoorStart + i)] *= RAMADAN_SUHOOR_MULT;
  out[iftarHour] *= RAMADAN_IFTAR_MULT;
}

/** Applique la variante été/Ramadan à une forme de base (résidentiel ou
 *  commercial) ; 'normal' renvoie la forme telle quelle. */
function applySeasonalVariant(
  base: readonly number[],
  variant: ProposalCurveVariant,
  ramadan?: Pick<RamadanWindow, 'imsakHour' | 'iftarHour'> | null,
): number[] {
  const out = base.slice();
  if (variant === 'ete') {
    for (const h of SUMMER_BOOST_HOURS) out[h] *= SUMMER_BOOST_MULT;
  } else if (variant === 'ramadan') {
    applyRamadan(out, ramadan ?? RAMADAN_FALLBACK_WINDOW);
  }
  return out;
}

/** WJ119 — Profil industriel par régime d'équipes. Poids plats : 1 = poste actif,
 *  `INDUSTRIAL_STANDBY_WEIGHT` = veille/éclairage de sécurité hors poste (jamais
 *  zéro : un site industriel garde toujours un socle hors production). Aucun champ
 *  backend ne porte le régime aujourd'hui → repli 1x8 (ESTIMATION documentée). */
const INDUSTRIAL_STANDBY_WEIGHT = 0.15;

function industrialShape(shift: IndustrialShift): number[] {
  if (shift === '3x8') return new Array(24).fill(1); // continu, trois équipes qui se relaient
  const out = new Array(24).fill(INDUSTRIAL_STANDBY_WEIGHT);
  // 1x8 : poste de jour unique (8h-16h) ; 2x8 : plateau 06h-22h (deux équipes).
  const [start, end] = shift === '2x8' ? [6, 22] : [8, 16];
  for (let h = start; h < end; h++) out[h] = 1;
  return out;
}

/** WJ119 — Archétype commercial GÉNÉRIQUE (horaires commerce courants 9h-19h) —
 *  UNE seule forme, pas de table par catégorie (QX44 pas encore construite) :
 *  ESTIMATION honnête, jamais présentée comme mesurée. */
const COMMERCIAL_OPEN_HOUR = 9;
const COMMERCIAL_CLOSE_HOUR = 19;
const COMMERCIAL_OFFHOURS_WEIGHT = 0.1;

function commercialShape(): number[] {
  const out = new Array(24).fill(COMMERCIAL_OFFHOURS_WEIGHT);
  for (let h = COMMERCIAL_OPEN_HOUR; h < COMMERCIAL_CLOSE_HOUR; h++) out[h] = 1;
  return out;
}

/** WJ119 — Fenêtre de pompage agricole = heures de JOUR (le pompage solaire
 *  tourne SUR le soleil, sans onduleur ni batterie — CLAUDE.md) : plate le jour,
 *  NULLE la nuit (aucune énergie stockée pour pomper après le coucher). */
const AGRICOLE_PUMP_START_HOUR = 7;
const AGRICOLE_PUMP_END_HOUR = 19;

function agricoleShape(): number[] {
  const out = new Array(24).fill(0);
  for (let h = AGRICOLE_PUMP_START_HOUR; h < AGRICOLE_PUMP_END_HOUR; h++) out[h] = 1;
  return out;
}

/** Construit la forme BRUTE (non normalisée) du mode/variante/régime demandé. */
function rawConsumptionShape(options: ConsumptionShapeOptions): number[] {
  const mode = options.mode ?? 'residentiel';
  const variant = options.variant ?? 'normal';
  const ramadan = options.ramadan ?? null;
  switch (mode) {
    case 'industriel':
      return industrialShape(options.industrialShift ?? '1x8');
    case 'commercial':
      // Été/Ramadan restent pertinents pour un commerce (clim, horaires resserrés
      // pendant le jeûne) — même modulation que le résidentiel, appliquée à
      // l'archétype commercial plutôt qu'à une silhouette de logement.
      return applySeasonalVariant(commercialShape(), variant, ramadan);
    case 'agricole':
      return agricoleShape();
    case 'residentiel':
    default:
      // CJ1 — la BASE résidentielle est la silhouette d'OCCUPATION choisie
      // (présent / absent / partiel en journée, dayProfiles.OCCUPANCY_SHAPES),
      // et non plus l'unique BASELINE_SHAPE moyenne. Été et Ramadan restent des
      // MODIFICATEURS ORTHOGONAUX appliqués par-dessus cette base.
      return applySeasonalVariant(
        OCCUPANCY_SHAPES[options.occupancy ?? 'presence_partielle'],
        variant,
        ramadan,
      );
  }
}

/**
 * Profil de consommation normalisé (0-23h, interpolé pour une heure quelconque).
 * Résidentiel/normal (repli par défaut) = silhouette marocaine soirée-dominante
 * (BASELINE_SHAPE, applianceConsumption.ts — pic 19h-21h ≈26 % de l'énergie),
 * jamais une double-gaussienne générique. Valeur ∈ [0,1], jamais un chiffre
 * affiché — ce n'est qu'une FORME, illustrative par construction (WJ119).
 */
export function consumptionProfile(hour: number, options: ConsumptionShapeOptions = {}): number {
  const shape = normalizeShape(rawConsumptionShape(options));
  return sampleShape(shape, hour);
}

/**
 * PACT-battery (2026-08-15) — Construit un tableau d'heures (0..hours-1) de
 * `consumptionProfile`, prêt à être injecté dans `simulateBattery`
 * (batterySim.ts). SEULE fonction qui échantillonne la silhouette pour le
 * simulateur batterie : le calcul SERVEUR initial (page, variante 'normal')
 * ET le recalcul CLIENT (au changement d'onglet Standard/Été/Ramadan pendant
 * que le calque batterie est actif) passent tous les deux par elle — aucune
 * divergence possible entre les deux passes, aucun chiffre inventé.
 */
export function consumptionShapeHours(hours: number, options: ConsumptionShapeOptions = {}): number[] {
  return Array.from({ length: Math.max(0, hours) }, (_, h) => consumptionProfile(h, options));
}

/** Normalise une forme brute à une SOMME de 1 (parts du jour) — la convention
 *  du serveur pour `production[saison].forme`. Somme nulle → tout à zéro. */
function normalizeToSum1(shape: readonly number[]): number[] {
  let sum = 0;
  for (const w of shape) if (Number.isFinite(w) && w > 0) sum += w;
  if (sum <= 0) return shape.map(() => 0);
  return shape.map((w) => (Number.isFinite(w) && w > 0 ? w / sum : 0));
}

/**
 * CJ1 — Silhouette de consommation en ÉNERGIE RÉELLE : 24 valeurs en kWh dont
 * la somme vaut EXACTEMENT `dailyKwh` (le `consommation[saison].kwh_jour` servi
 * par le backend, moyenne des factures réelles du lead).
 *
 * C'est la fonction qui rend la phrase « ajusté à votre facture » exacte : la
 * FORME reste notre estimation étiquetée, le NIVEAU est celui du client. Une
 * valeur horaire en kWh sur une heure vaut aussi la PUISSANCE MOYENNE de cette
 * heure en kW — c'est ce qui permet de partager un seul axe avec la production.
 *
 * `dailyKwh` ≤ 0 ou non fini ⇒ tableau de zéros (on n'invente aucun niveau).
 */
export function consumptionKwhShape(
  dailyKwh: number,
  options: ConsumptionShapeOptions = {},
): number[] {
  const total = Number.isFinite(dailyKwh) && dailyKwh > 0 ? dailyKwh : 0;
  if (total <= 0) return new Array(24).fill(0);
  return normalizeToSum1(rawConsumptionShape(options)).map((part) => part * total);
}

function esc(s: string): string {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** WJ80 — Langue courante de la page, thread à travers étiquettes + annotations. */
export type CurveLang = 'fr' | 'en' | 'ar';

export interface CurveBox {
  width: number;
  height: number;
  padLeft: number;
  padRight: number;
  padTop: number;
  padBottom: number;
}

export const DEFAULT_CURVE_BOX: CurveBox = {
  width: 360,
  height: 170,
  padLeft: 10,
  padRight: 10,
  padTop: 16,
  padBottom: 24,
};

/** Construit le `d` d'un path lissé (polyligne) à partir de points normalisés. */
function pathFromProfile(
  profile: (h: number) => number,
  box: CurveBox,
  close: boolean,
): { d: string; points: Array<{ x: number; y: number }> } {
  const plotW = box.width - box.padLeft - box.padRight;
  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;
  const steps = HOURS * 2; // demi-heures pour un tracé fluide
  const points: Array<{ x: number; y: number }> = [];
  for (let i = 0; i <= steps; i++) {
    const hour = HOUR_START + (i / steps) * HOURS;
    const v = Math.max(0, Math.min(1, profile(hour)));
    const x = box.padLeft + (i / steps) * plotW;
    const y = baseY - v * plotH;
    points.push({ x, y });
  }
  let d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(' ');
  if (close) {
    const last = points[points.length - 1];
    const first = points[0];
    d += ` L${last.x.toFixed(2)} ${baseY.toFixed(2)} L${first.x.toFixed(2)} ${baseY.toFixed(2)} Z`;
  }
  return { d, points };
}

export interface DailyCurve {
  /** SVG inline complet (string). */
  svg: string;
  /**
   * Vrai quand le repère d'axe porte des chiffres RÉELS (forme de production
   * servie, ou à défaut production annuelle backend) ; faux → mode « année
   * type » (forme illustrative, aucun chiffre d'axe).
   */
  hasRealScale: boolean;
  /**
   * CJ1 — vrai quand la courbe de PRODUCTION est la forme horaire PVGIS servie
   * par le backend pour la saison affichée (et non la cloche sin² de repli).
   */
  hasServedShape: boolean;
  /**
   * CJ1 — vrai quand la silhouette de CONSOMMATION est mise à l'échelle du
   * kWh/jour RÉEL du client (`consommation[saison].kwh_jour`) sur le MÊME axe
   * que la production. C'est la seule condition dans laquelle la page a le
   * droit d'écrire « calé sur vos factures ».
   */
  hasRealConsScale: boolean;
}

/** Nombre court (1 décimale), virgule/point décimal selon la langue. */
function fmtNumber(n: number, lang: CurveLang = 'fr'): string {
  const v = Number.isFinite(n) && n > 0 ? n : 0;
  const rounded = (Math.round(v * 10) / 10).toString();
  // WJ80 — FR/AR gardent la virgule décimale (convention déjà utilisée
  // ailleurs sur la page en arabe) ; EN utilise le point décimal.
  return lang === 'en' ? rounded : rounded.replace('.', ',');
}

/** Format kWh court (ÉNERGIE). */
function fmtKwh(n: number, lang: CurveLang = 'fr'): string {
  return `${fmtNumber(n, lang)} kWh`;
}

/**
 * CJ1 — Format kW court (PUISSANCE). Le repère de pointe l'utilise DÉSORMAIS
 * partout : un « pic » est une puissance, jamais une énergie. L'ancien libellé
 * « pic ≈ 14,3 kWh » — y compris sur le chemin de repli sans donnée servie —
 * était une faute d'unité pure et simple.
 */
function fmtKw(n: number, lang: CurveLang = 'fr'): string {
  return `${fmtNumber(n, lang)} kW`;
}

/** WJ80 — Libellés horaires (lever/midi/coucher) FR/EN/AR. */
const HOUR_TICK_LABELS: Record<CurveLang, { sunrise: string; noon: string; sunset: string }> = {
  fr: { sunrise: 'lever', noon: 'midi', sunset: 'coucher' },
  en: { sunrise: 'sunrise', noon: 'noon', sunset: 'sunset' },
  ar: { sunrise: 'الشروق', noon: 'الظهر', sunset: 'الغروب' },
};

/** WJ80 — Texte du repère d'échelle (pic + moyenne journalière ou repli « année type »).
 *  CJ1 — `perDay` sert la ligne saisonnière « 48,2 kWh/jour (été) » quand le
 *  backend a servi la saison ; `dailyAvg` reste la ligne du repli annuel. */
const SCALE_LABELS: Record<
  CurveLang,
  { peak: string; dailyAvg: string; typicalYear: string; perDay: string }
> = {
  fr: { peak: 'pic ≈', dailyAvg: '/ jour en moyenne', typicalYear: 'profil — année type', perDay: '/jour' },
  en: { peak: 'peak ≈', dailyAvg: '/ day on average', typicalYear: 'profile — typical year', perDay: '/day' },
  ar: { peak: 'الذروة ≈', dailyAvg: '/ يومياً في المتوسط', typicalYear: 'نمط — سنة نموذجية', perDay: '/يوم' },
};

/**
 * CJ1 — Ce que le SERVEUR a servi pour la saison AFFICHÉE. Tout est optionnel :
 * chaque morceau manquant fait retomber ce module sur son comportement d'avant,
 * jamais sur une approximation (décision fondateur Q6 : on omet).
 */
export interface ServedCurveScale {
  /** Forme + niveaux de production PVGIS de la saison affichée. */
  production?: ServedProduction | null;
  /** kWh/jour RÉEL de consommation de la saison affichée (factures du lead). */
  consumptionKwhJour?: number | null;
  /** Saison affichée — pour l'incise « (été) » du repère d'axe. */
  season?: SeasonId | null;
}

/**
 * WJ16 — Construit le SVG de la courbe journalière production-vs-consommation.
 * `annualProdKwh` (backend `prod_kwh`) cale l'amplitude réelle ; absent/nul →
 * mode « année type » (forme normalisée, libellée). Aucune transition n'est
 * intégrée au SVG : l'animation vit dans la page, gatée reduced-motion.
 *
 * WJ80 — `lang` sélectionne les étiquettes horaires + le repère d'échelle
 * (FR/EN/AR) ; les tailles de police (7,5→8 → 9→9,5) sont relevées pour rester
 * lisibles sur petit écran, et le groupe de repère porte des `data-*` (déjà
 * formatés) qu'un petit script de la page lit au TAP (le survol/`<title>` est
 * invisible au tactile).
 *
 * WJ119 — `consumptionOptions` sélectionne le MODE (residentiel/industriel/
 * commercial/agricole) et la variante (normal/été/Ramadan) de la silhouette de
 * consommation — repli residentiel/normal, rétro-compatible : un appelant qui
 * n'en fournit pas obtient le profil marocain par défaut, jamais l'ancienne
 * double-gaussienne.
 *
 * CJ1 — `served` porte ce que le backend a servi POUR LA SAISON AFFICHÉE. Absent
 * (le cas fréquent) ⇒ tout le rendu est byte-identique à celui d'avant. Présent ⇒
 * la production est la forme PVGIS servie, la consommation est calée sur le
 * kWh/jour réel du client, et les deux partagent un axe en kW.
 */
export function renderYearCurve(
  annualProdKwh: number | null | undefined,
  box: CurveBox = DEFAULT_CURVE_BOX,
  lang: CurveLang = 'fr',
  consumptionOptions: ConsumptionShapeOptions = {},
  served: ServedCurveScale | null = null,
): DailyCurve {
  const annual = typeof annualProdKwh === 'number' && Number.isFinite(annualProdKwh) && annualProdKwh > 0
    ? annualProdKwh : null;

  // ── CJ1 — L'AXE RÉEL, quand le serveur a servi la saison ─────────────────
  // `forme` somme à 1 : `kwhJour × forme[h]` est donc l'énergie de l'heure h en
  // kWh, c'est-à-dire aussi la PUISSANCE MOYENNE de cette heure en kW. La
  // consommation est mise à la même échelle (consumptionKwhShape), donc les
  // deux courbes partagent UN SEUL axe, en kW. `picKw` vient du serveur : on ne
  // le recalcule pas, on cale le dessin dessus (aucune divergence possible
  // entre l'étiquette et la hauteur du trait).
  const prod = served?.production ?? null;
  const hasServedShape = !!prod && Array.isArray(prod.forme) && prod.forme.length === 24 && prod.picKw > 0;
  const consKwhJour =
    typeof served?.consumptionKwhJour === 'number' && Number.isFinite(served.consumptionKwhJour)
      && served.consumptionKwhJour > 0
      ? served.consumptionKwhJour
      : null;
  // La consommation ne prend une échelle RÉELLE que s'il existe un axe réel à
  // partager (production servie). Un vrai chiffre posé sur un axe illustratif
  // serait plus trompeur qu'une forme honnête : dans ce cas on garde la
  // silhouette normalisée d'avant.
  const hasRealConsScale = hasServedShape && consKwhJour !== null;
  const consKwh = hasRealConsScale ? consumptionKwhShape(consKwhJour!, consumptionOptions) : null;

  let solarAt: (h: number) => number;
  let consAt: (h: number) => number;
  if (hasServedShape) {
    const prodKwhAt = (h: number) => prod!.kwhJour * sampleShape(prod!.forme, h);
    const consKwhAt = consKwh ? (h: number) => sampleShape(consKwh, h) : null;
    // Sommet de l'axe : le pic SERVI, relevé si la consommation le dépasse
    // (un foyer très consommateur doit rester dans le cadre, pas être coupé).
    let axisMax = prod!.picKw;
    if (consKwhAt) {
      for (let h = 0; h < 24; h++) axisMax = Math.max(axisMax, consKwhAt(h));
    }
    const denom = axisMax > 0 ? axisMax : 1;
    solarAt = (h) => prodKwhAt(h) / denom;
    consAt = consKwhAt
      ? (h) => consKwhAt(h) / denom
      : (h) => consumptionProfile(h, consumptionOptions);
  } else {
    solarAt = solarProfile;
    consAt = (h) => consumptionProfile(h, consumptionOptions);
  }
  const hasRealScale = hasServedShape || annual !== null;

  const solar = pathFromProfile(solarAt, box, true);
  const cons = pathFromProfile(consAt, box, false);

  const plotH = box.height - box.padTop - box.padBottom;
  const baseY = box.padTop + plotH;

  // Étiquettes horaires (lever / midi / coucher) — repères de lecture neutres.
  const plotW = box.width - box.padLeft - box.padRight;
  const tickHours = [6, 13, 20] as const;
  const tickLabels = HOUR_TICK_LABELS[lang];
  const tickTexts = [tickLabels.sunrise, tickLabels.noon, tickLabels.sunset];
  const ticks = tickHours
    .map((h, i) => {
      const x = box.padLeft + ((h - HOUR_START) / HOURS) * plotW;
      return `<text x="${x.toFixed(2)}" y="${(box.height - 8).toFixed(2)}" text-anchor="middle" font-size="9" fill="var(--color-lune-faint, #8d96b4)">${esc(tickTexts[i])}</text>`;
    })
    .join('');

  const scale = SCALE_LABELS[lang];
  // Repère d'axe Y. Le PIC est TOUJOURS libellé en kW (c'est une puissance) —
  // sur le chemin servi comme sur le repli annuel.
  let scaleLabel = '';
  if (hasRealScale) {
    let peakFmt: string;
    let avgFmt: string;
    if (hasServedShape) {
      // Chemin servi : les DEUX chiffres viennent du backend, aucun n'est dérivé
      // ici (pic_kw = kwh_jour × max(forme), calculé côté serveur).
      peakFmt = fmtKw(prod!.picKw, lang);
      const seasonId = served?.season ?? null;
      const inline = seasonId ? ` (${SEASON_INLINE[seasonId][lang]})` : '';
      avgFmt = `${fmtKwh(prod!.kwhJour, lang)}${scale.perDay}${inline}`;
    } else {
      // Repli inchangé : moyenne journalière = annuel / 365, et le pic vaut env.
      // dailyAvg / surface-sous-la-cloche (≈ 4,6 h équivalent pleine puissance).
      // C'est une PUISSANCE moyenne d'heure de pointe — d'où « kW », pas « kWh ».
      const dailyAvg = annual! / 365;
      peakFmt = fmtKw(dailyAvg / 4.6, lang);
      avgFmt = `${fmtKwh(dailyAvg, lang)} ${scale.dailyAvg}`;
    }
    scaleLabel =
      `<g data-curve-scale data-peak="${esc(`${scale.peak} ${peakFmt}`)}" data-avg="${esc(avgFmt)}" tabindex="0" role="button" aria-label="${esc(scale.peak)} ${esc(peakFmt)}, ${esc(avgFmt)}">` +
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 8).toFixed(2)}" font-size="9" fill="var(--color-brass-300, #f3cc66)">${esc(scale.peak)} ${esc(peakFmt)}</text>` +
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 19).toFixed(2)}" font-size="8.5" fill="var(--color-lune-faint, #8d96b4)">${esc(avgFmt)}</text>` +
      `</g>`;
  } else {
    scaleLabel =
      `<text x="${(box.padLeft + 2).toFixed(2)}" y="${(box.padTop + 8).toFixed(2)}" font-size="9" fill="var(--color-lune-faint, #8d96b4)">${esc(scale.typicalYear)}</text>`;
  }

  const baseline = `<line x1="${box.padLeft}" y1="${baseY.toFixed(2)}" x2="${(box.width - box.padRight).toFixed(2)}" y2="${baseY.toFixed(2)}" stroke="var(--color-white, #fff)" stroke-opacity="0.12" stroke-width="1"/>`;

  // Soleil décoratif (animé en CSS via la classe .curve-sun, statique sinon).
  const sunX = box.padLeft + plotW * ((13 - HOUR_START) / HOURS);
  const sunY = box.padTop + plotH * 0.18;
  const sun = `<circle class="curve-sun" cx="${sunX.toFixed(2)}" cy="${sunY.toFixed(2)}" r="6" fill="var(--color-brass-300, #f3cc66)" fill-opacity="0.9"/>`;

  // Longueur de tracé pour l'animation de dessin (dasharray en CSS).
  const descByLang: Record<CurveLang, string> = {
    fr: 'Production solaire estimée sur une journée type comparée à la consommation du foyer.',
    en: "Estimated solar production over a typical day compared to the household's consumption.",
    ar: 'الإنتاج الشمسي المقدّر خلال يوم نموذجي مقارنة باستهلاك المنزل.',
  };
  const titleByLang: Record<CurveLang, string> = {
    fr: 'Production vs consommation — journée type',
    en: 'Production vs consumption — typical day',
    ar: 'الإنتاج مقابل الاستهلاك — يوم نموذجي',
  };
  const desc = descByLang[lang];

  const svg =
    `<svg class="daily-curve" viewBox="0 0 ${box.width} ${box.height}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" role="img" xmlns="http://www.w3.org/2000/svg">` +
    `<title>${esc(titleByLang[lang])}</title><desc>${esc(desc)}</desc>` +
    `<defs><linearGradient id="solarFill" x1="0" y1="0" x2="0" y2="1">` +
    `<stop offset="0%" stop-color="var(--color-brass-400, #e8b54a)" stop-opacity="0.42"/>` +
    `<stop offset="100%" stop-color="var(--color-brass-400, #e8b54a)" stop-opacity="0.04"/>` +
    `</linearGradient></defs>` +
    baseline +
    sun +
    `<path class="curve-solar-fill" d="${solar.d}" fill="url(#solarFill)" stroke="none"/>` +
    `<path class="curve-solar-line" d="${solar.d.replace(/ L[\d.]+ [\d.]+ L[\d.]+ [\d.]+ Z$/, '')}" fill="none" stroke="var(--color-brass-400, #e8b54a)" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>` +
    `<path class="curve-cons-line" d="${cons.d}" fill="none" stroke="var(--color-azur-300, #7fb4e8)" stroke-width="2" stroke-dasharray="4 3" stroke-linejoin="round" stroke-linecap="round"/>` +
    ticks +
    scaleLabel +
    `</svg>`;

  return { svg, hasRealScale, hasServedShape, hasRealConsScale };
}
