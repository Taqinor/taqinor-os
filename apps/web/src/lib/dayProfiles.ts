/**
 * CJ1 — « Sur une journée » : les briques PURES de la courbe journalière RÉELLE.
 *
 * Ce module ne dessine rien. Il porte les quatre pièces que le graphe journalier
 * de `/proposition/<token>` n'avait pas et qui l'empêchaient d'être vrai :
 *
 *  1. `SeasonId` + `seasonForDate` — les MÊMES saisons que le serveur
 *     (`apps/parametres/pvgis_profils.py` : `MOIS_PAR_SAISON` — hiver = DJF,
 *     mi-saison = MAM + SON, été = JJA). La saison par défaut est celle de la
 *     date du jour, jamais un choix arbitraire.
 *  2. Les TROIS silhouettes d'occupation résidentielles (présent / absent /
 *     partiel) qui remplacent l'unique `BASELINE_SHAPE` : elles ne sont plus une
 *     forme moyenne « pour tout le monde », le visiteur choisit la sienne.
 *     Chaque heure porte sa PROVENANCE en commentaire ([A]/[S]/[i], voir plus
 *     bas) — aucune n'est un chiffre inventé sans étiquette.
 *  3. `ramadanWindow` — les heures de Ramadan CALCULÉES par date (table des
 *     plages grégoriennes + coucher/lever de soleil NOAA au point GPS du
 *     chantier), plus jamais les « 3h-5h suhoor / 19h iftar » codés en dur qui
 *     n'étaient vrais que pour un Ramadan d'été.
 *  4. `parseDailyCurves` — lecture DÉFENSIVE du bloc backend additif
 *     `courbes_journalieres` (`apps/ventes/courbes_journalieres.py`). Bloc
 *     absent ⇒ `null` ⇒ la page garde EXACTEMENT son rendu d'avant.
 *
 * DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » : ce module ne fabrique aucun niveau. Les
 * kWh/jour et les kW de pointe viennent tous du serveur (factures réelles du
 * lead + productible PVGIS × kWc du devis) ; ici on ne porte que des FORMES
 * (poids relatifs) et de la GÉOMÉTRIE solaire (astronomie, pas une mesure).
 */

// ════════════════════════════════════════════════════════════════════════════
// 1. SAISONS — mêmes bornes que le serveur, jamais une seconde définition
// ════════════════════════════════════════════════════════════════════════════

/** Les trois saisons servies par le backend (`pvgis_profils.SAISONS`). */
export type SeasonId = 'hiver' | 'mi_saison' | 'ete';

export const SEASON_IDS: readonly SeasonId[] = ['hiver', 'mi_saison', 'ete'];

/**
 * Mois (1-12) de chaque saison — COPIE EXACTE de `MOIS_PAR_SAISON`
 * (`backend/django_core/apps/parametres/pvgis_profils.py`) : hiver = décembre à
 * février, été = juin à août, mi-saison = tout le reste. Une divergence ici
 * ferait lire à la page une saison que le serveur n'a pas moyennée.
 */
const SEASON_MONTHS: Record<SeasonId, readonly number[]> = {
  hiver: [12, 1, 2],
  mi_saison: [3, 4, 5, 9, 10, 11],
  ete: [6, 7, 8],
};

/**
 * Saison d'une date. Les accesseurs sont en UTC VOLONTAIREMENT : la page est
 * rendue côté serveur (fuseau de la plateforme) puis rejouée côté client
 * (fuseau du visiteur) — lire le mois en heure locale ferait diverger les deux
 * à quelques heures d'une frontière de mois. Le décalage possible (≤ 1 h sur
 * 3 mois de saison) est sans effet sur la courbe affichée.
 */
export function seasonForDate(date: Date): SeasonId {
  const time = date instanceof Date ? date.getTime() : Number.NaN;
  if (!Number.isFinite(time)) return 'mi_saison';
  const month = date.getUTCMonth() + 1;
  for (const id of SEASON_IDS) {
    if (SEASON_MONTHS[id].includes(month)) return id;
  }
  return 'mi_saison';
}

/** Libellés de saison (FR/EN/AR) — utilisés par les puces ET par le repère d'axe. */
export const SEASON_LABELS: Record<SeasonId, { fr: string; en: string; ar: string }> = {
  hiver: { fr: 'Hiver', en: 'Winter', ar: 'الشتاء' },
  mi_saison: { fr: 'Mi-saison', en: 'Shoulder season', ar: 'بين الفصلين' },
  ete: { fr: 'Été', en: 'Summer', ar: 'الصيف' },
};

/** Même mot, en minuscules, pour une incise dans une phrase (« … (été) »). */
export const SEASON_INLINE: Record<SeasonId, { fr: string; en: string; ar: string }> = {
  hiver: { fr: 'hiver', en: 'winter', ar: 'الشتاء' },
  mi_saison: { fr: 'mi-saison', en: 'shoulder season', ar: 'بين الفصلين' },
  ete: { fr: 'été', en: 'summer', ar: 'الصيف' },
};

// ════════════════════════════════════════════════════════════════════════════
// 2. OCCUPATION — trois silhouettes résidentielles au lieu d'une moyenne
// ════════════════════════════════════════════════════════════════════════════

/**
 * Qui est à la maison en journée. Le backend ne sert que deux drapeaux
 * (`presence_jour` / `absence_jour`, `courbes_journalieres._occupation`) ; la
 * page en propose TROIS au visiteur — le troisième (`presence_partielle`,
 * télétravail/mi-temps) n'est jamais un défaut serveur, c'est un choix humain.
 */
export type OccupancyId = 'presence_jour' | 'absence_jour' | 'presence_partielle';

export const OCCUPANCY_IDS: readonly OccupancyId[] = [
  'presence_jour',
  'absence_jour',
  'presence_partielle',
];

export const OCCUPANCY_LABELS: Record<OccupancyId, { fr: string; en: string; ar: string }> = {
  presence_jour: { fr: 'Présent en journée', en: 'Home during the day', ar: 'حاضر خلال النهار' },
  absence_jour: { fr: 'Absent en journée', en: 'Away during the day', ar: 'غائب خلال النهار' },
  presence_partielle: { fr: 'Présence partielle', en: 'Partly home', ar: 'حضور جزئي' },
};

/**
 * PROVENANCE DES POIDS HORAIRES (recherche du 21/08/2026) — chaque heure des
 * trois vecteurs ci-dessous porte l'une de ces étiquettes :
 *
 *  [A] FAIT MAROCAIN SOURCÉ. La fenêtre de pointe nationale est publiée : le
 *      tarif bi-horaire ONEE place les heures de pointe à 18h-23h en été et
 *      17h-22h en hiver (one.org.ma, grille tarifaire) ; le record historique
 *      d'appel de puissance du réseau marocain a été atteint le 25/07/2019 à
 *      21h45 (presse économique — Le Desk / Boursenews). La domination du soir
 *      n'est donc PAS une hypothèse : c'est la forme du réseau marocain.
 *  [S] MOTIF DE CLUSTERING SOURCÉ, MAGNITUDE ESTIMÉE. La séparation
 *      « présent / absent / partiel » et l'allure de chaque groupe viennent de
 *      la littérature de clustering de courbes de charge résidentielles
 *      (étude sur données Dubaï, ScienceDirect S377877882300333X ; arXiv
 *      2102.11027 ; IOPscience ade3fa) : creux diurne marqué pour les foyers
 *      absents, plateau diurne pour les foyers présents. Les VALEURS exactes
 *      sont nos estimations calées sur ces allures.
 *  [i] INTERPOLATION entre deux heures étiquetées ci-dessus (transition douce,
 *      aucune donnée propre).
 *
 * Ce sont des POIDS DE FORME, pas des kWh. Le NIVEAU vient toujours du serveur
 * (`consommation[saison].kwh_jour`, moyenne des factures réelles du lead) : ce
 * module ne connaît aucune énergie.
 *
 * CJ2b (21/08/2026) — LE REPLI, plus la seule source. Le backend peut désormais
 * servir sa PROPRE forme horaire par saison (`consommation[saison].forme`,
 * `consommation_forme_source`) — une silhouette calculée depuis la présence
 * réelle du foyer, pas cette estimation résidentielle générique. Quand elle est
 * servie et VALIDE (24 nombres finis ≥ 0, somme > 0 — `parseDailyCurves` ne
 * laisse jamais passer autre chose), `proposalCurve.rawConsumptionShape` la
 * PRÉFÈRE ; ces trois vecteurs ne sont plus lus que comme repli, byte-identique
 * au rendu d'avant quand rien n'est servi. Le contenu ci-dessous reste
 * INCHANGÉ : il est pincé mot pour mot par
 * `test_etude_horaire.py::test_les_trois_silhouettes_sont_identiques_au_typescript`.
 */
export const OCCUPANCY_SHAPES: Record<OccupancyId, readonly number[]> = {
  // « Présent en journée » — retraités, foyers mono-actifs, villa occupée.
  // Plateau diurne réel (midi marqué : cuisine + climatisation), pointe du soir
  // conservée mais MOINS creusée que chez un foyer absent.
  presence_jour: [
    // 0h    1h    2h    3h    4h    5h   — nuit, socle froid + veille        [S]
    0.4, 0.4, 0.4, 0.4, 0.4, 0.4,
    // 6h [i]  7h [S]  8h [S]  9h [S] 10h [S] 11h [i]
    0.5, 0.8, 1.0, 1.0, 1.1, 1.1,
    // 12h [S] 13h [S] 14h [S] — repas de midi + clim, le foyer est là
    1.35, 1.35, 1.35,
    // 15h [i] 16h [i] 17h [A] — retombée d'après-midi, entrée de pointe ONEE
    1.0, 1.0, 1.0,
    // 18h [A] 19h [A] 20h [A] 21h [A] — fenêtre de pointe nationale 18h-23h
    1.2, 1.5, 1.8, 1.7,
    // 22h [A] 23h [i]
    1.2, 0.7,
  ],
  // « Absent en journée » — actifs partis au travail. Creux diurne profond,
  // pointe du soir la PLUS marquée des trois (tout se concentre après 18h).
  absence_jour: [
    // 0h-5h — nuit                                                            [S]
    0.4, 0.4, 0.4, 0.4, 0.4, 0.4,
    // 6h [i]  7h [S] — pointe du matin (douche, petit-déjeuner, départ)
    0.7, 1.6,
    // 8h [i]
    1.0,
    // 9h-16h [S] — logement vide : frigo + veille, rien d'autre
    0.45, 0.45, 0.45, 0.45, 0.45, 0.45, 0.45, 0.45,
    // 17h [A] 18h [A] 19h [A] 20h [A] 21h [A] — retour + fenêtre de pointe ONEE
    0.9, 1.4, 1.9, 2.4, 2.3,
    // 22h [A] 23h [i]
    1.5, 0.9,
  ],
  // « Présence partielle » — télétravail, mi-temps, foyer mixte. Entre les deux :
  // un plateau diurne bas mais réel, une pointe du soir franche.
  presence_partielle: [
    // 0h-5h — nuit                                                            [S]
    0.4, 0.4, 0.4, 0.4, 0.4, 0.4,
    // 6h [i]  7h [S]  8h [i]
    0.5, 0.9, 1.0,
    // 9h-11h [S] — bureau à la maison : socle + informatique
    0.95, 0.95, 0.95,
    // 12h [S] 13h [S] — pause déjeuner
    1.1, 1.1,
    // 14h-16h [S]
    0.9, 0.9, 0.9,
    // 17h [A] 18h [A] 19h [A] 20h [A] 21h [A] — fenêtre de pointe ONEE
    1.1, 1.5, 1.9, 2.2, 2.0,
    // 22h [A] 23h [i]
    1.3, 0.8,
  ],
};

/**
 * Occupation par défaut à partir du drapeau serveur. Sans réponse du lead au
 * script d'appel, le backend ne connaît que `presence_jour` / `absence_jour`
 * (décision fondateur 21/08/2026 : la clientèle résidentielle réelle de
 * TAQINOR est majoritairement présente en journée, d'où `presence_jour` par
 * défaut en résidentiel — c'est une OBSERVATION DE TERRAIN, pas une
 * statistique nationale, et `occupation_source` le dit).
 *
 * L4 (extension fondateur, 21/08/2026) — quand le commercial a posé la
 * question au téléphone (`crm.Lead.occupation_jour`), le backend sert
 * désormais AUSSI `presence_partielle` directement (source
 * `lead_occupation_jour:partiel`) : ce n'est plus seulement un choix
 * VISITEUR côté page, la réponse RÉELLE du client peut la servir en premier.
 *
 * Drapeau absent (bloc `courbes_journalieres` non servi) ⇒ `presence_partielle` :
 * le milieu honnête des trois, et la silhouette la plus proche de l'ancienne
 * `BASELINE_SHAPE` — la page ne change donc pas d'allure quand rien n'est servi.
 */
export function occupancyFromFlag(flag: string | null | undefined): OccupancyId {
  const s = String(flag ?? '').trim().toLowerCase();
  if (s === 'presence_jour') return 'presence_jour';
  if (s === 'absence_jour') return 'absence_jour';
  if (s === 'presence_partielle') return 'presence_partielle';
  return 'presence_partielle';
}

// ════════════════════════════════════════════════════════════════════════════
// 3. RAMADAN — heures CALCULÉES par date, plus jamais codées en dur
// ════════════════════════════════════════════════════════════════════════════

/**
 * Plages grégoriennes du mois de Ramadan, 2025 → 2033 (hégire 1446 → 1455).
 * Ce sont des ESTIMATIONS ASTRONOMIQUES publiées, relevées le 21/08/2026 sur
 * aladhan.com (`aladhan.com/ramadan-calendar/<année>` et le calendrier
 * hijri-grégorien 9/1455) et recoupées avec sajda.com : le Maroc confirme le
 * premier jour par OBSERVATION LUNAIRE (annonce du ministère des Habous la
 * veille), donc chaque borne peut bouger de ±1 jour. Cette incertitude est
 * SANS EFFET ici : la table ne sert qu'à choisir un jour REPRÉSENTATIF pour
 * calculer le coucher du soleil, et le coucher ne bouge que de ~1 minute par
 * jour à cette saison.
 *
 * Le mois recule d'environ 11 jours par an dans le calendrier grégorien : il
 * tombe donc DEUX fois dans certaines années grégoriennes (2030 : janvier ET
 * décembre). Les plages sont stockées à plat, triées, bornes incluses.
 */
export interface RamadanRange {
  /** Année hégirienne du mois (1446 = Ramadan de 2025). */
  hijri: number;
  /** Premier jour (AAAA-MM-JJ, estimation astronomique ±1 jour). */
  start: string;
  /** Dernier jour (AAAA-MM-JJ, estimation astronomique ±1 jour). */
  end: string;
}

export const RAMADAN_RANGES: readonly RamadanRange[] = [
  { hijri: 1446, start: '2025-03-01', end: '2025-03-29' },
  { hijri: 1447, start: '2026-02-18', end: '2026-03-19' },
  { hijri: 1448, start: '2027-02-08', end: '2027-03-08' },
  { hijri: 1449, start: '2028-01-28', end: '2028-02-25' },
  { hijri: 1450, start: '2029-01-16', end: '2029-02-13' },
  { hijri: 1451, start: '2030-01-05', end: '2030-02-03' },
  { hijri: 1452, start: '2030-12-26', end: '2031-01-23' },
  { hijri: 1453, start: '2031-12-15', end: '2032-01-13' },
  { hijri: 1454, start: '2032-12-04', end: '2033-01-01' },
  { hijri: 1455, start: '2033-11-23', end: '2033-12-22' },
];

/** Coordonnées de repli — Casablanca (chantier sans GPS ni ville reconnue). */
export const DEFAULT_LAT = 33.57;
export const DEFAULT_LON = -7.59;

/**
 * FUSEAU RETENU POUR LE RAMADAN : UTC+0.
 *
 * Le Maroc vit à UTC+1 toute l'année SAUF pendant le Ramadan, où il repasse à
 * UTC+0. C'est exactement ce qu'affirme la note servie par le backend
 * (`courbes_journalieres.NOTE_HORAIRE` — notre source de vérité dans ce dépôt :
 * « Pendant le Ramadan, le Maroc repasse à UTC+0 : la courbe se décale alors
 * d'une heure plus tôt »), et ce que documente « Time in Morocco »
 * (en.wikipedia.org). L'iftar que le client connaît — celui de son
 * calendrier, de la sirène et de la télévision — est donc une heure UTC+0.
 * C'est celle-là qu'on calcule et qu'on affiche.
 *
 * CE QUE ÇA IMPLIQUE, ET QU'ON DIT : la FORME de production servie par le
 * serveur, elle, reste en heure civile ordinaire (UTC+1) — le backend ne
 * modélise pas le décalage Ramadan, il le DIT. La page affiche donc la note
 * horaire du serveur à côté de la puce Ramadan plutôt que de bricoler un
 * décalage d'une heure sur une courbe qu'elle n'a pas produite.
 */
export const RAMADAN_TZ_OFFSET_HOURS = 0;

/** L'approximation du fajr retenue : lever du soleil MOINS 80 minutes. */
export const FAJR_BEFORE_SUNRISE_MIN = 80;

export interface RamadanWindow {
  /** Fin du suhoor / imsak (heure décimale, fuseau `RAMADAN_TZ_OFFSET_HOURS`). */
  imsakHour: number;
  /** Iftar = coucher du soleil (heure décimale, même fuseau). */
  iftarHour: number;
  /** Jour de référence effectivement calculé (AAAA-MM-JJ). */
  referenceDate: string;
  /** Année hégirienne de la plage retenue. */
  hijri: number;
  /** Vrai quand la date fournie tombe DANS le Ramadan (sinon jour médian). */
  inRamadan: boolean;
}

/** `AAAA-MM-JJ` → millisecondes UTC (minuit), ou `NaN`. */
function isoToUtcMs(iso: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return NaN;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

/** Millisecondes UTC → `AAAA-MM-JJ`. */
function utcMsToIso(ms: number): string {
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}

/**
 * La plage de Ramadan à retenir pour une date : celle qui la CONTIENT, sinon la
 * PROCHAINE à venir (le visiteur peut cliquer « Ramadan » en plein mois d'août —
 * on lui montre alors le Ramadan qui arrive, jour médian). Au-delà de la table
 * (après 2033), `null` : on préfère ne rien affirmer.
 */
export function ramadanRangeFor(date: Date): { range: RamadanRange; inRamadan: boolean } | null {
  const t = date instanceof Date ? date.getTime() : Number.NaN;
  if (!Number.isFinite(t)) return null;
  for (const range of RAMADAN_RANGES) {
    const start = isoToUtcMs(range.start);
    const end = isoToUtcMs(range.end) + 24 * 3600 * 1000 - 1; // borne de fin incluse
    if (t >= start && t <= end) return { range, inRamadan: true };
    if (t < start) return { range, inRamadan: false };
  }
  return null;
}

/** Jour julien à 12 h TU du jour civil donné (algorithme grégorien standard). */
function julianDayNoon(year: number, month: number, day: number): number {
  let y = year;
  let m = month;
  if (m <= 2) {
    y -= 1;
    m += 12;
  }
  const a = Math.floor(y / 100);
  const b = 2 - a + Math.floor(a / 4);
  return Math.floor(365.25 * (y + 4716)) + Math.floor(30.6001 * (m + 1)) + day + b - 1524.5 + 0.5;
}

const DEG = Math.PI / 180;
const mod360 = (x: number) => ((x % 360) + 360) % 360;

export interface SunTimes {
  /** Lever, en MINUTES depuis minuit dans le fuseau demandé. */
  sunriseMin: number;
  /** Coucher, en MINUTES depuis minuit dans le fuseau demandé. */
  sunsetMin: number;
}

/**
 * Lever et coucher du soleil — algorithme NOAA (« NOAA Solar Calculator »,
 * gml.noaa.gov/grad/solcalc/, la même chaîne équation-du-temps + déclinaison
 * que la feuille de calcul de référence). Zénith 90,833° = centre du disque
 * + réfraction atmosphérique moyenne, convention NOAA du lever/coucher.
 *
 * C'est de l'ASTRONOMIE, pas une mesure : reproductible, sans réseau, précis à
 * la minute près pour nos latitudes. `lon` est positif vers l'EST (le Maroc est
 * donc négatif), `tzOffsetHours` le décalage du fuseau d'affichage.
 * Nuit/jour polaire (jamais au Maroc) ⇒ `null`.
 */
export function sunTimes(
  date: Date,
  lat: number,
  lon: number,
  tzOffsetHours: number,
): SunTimes | null {
  const time = date instanceof Date ? date.getTime() : Number.NaN;
  if (!Number.isFinite(time) || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const jd = julianDayNoon(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
  const t = (jd - 2451545) / 36525;

  const l0 = mod360(280.46646 + t * (36000.76983 + t * 0.0003032));
  const m = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const c =
    Math.sin(m * DEG) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
    Math.sin(2 * m * DEG) * (0.019993 - 0.000101 * t) +
    Math.sin(3 * m * DEG) * 0.000289;
  const trueLong = l0 + c;
  const omega = 125.04 - 1934.136 * t;
  const lambda = trueLong - 0.00569 - 0.00478 * Math.sin(omega * DEG);
  const seconds = 21.448 - t * (46.815 + t * (0.00059 - t * 0.001813));
  const eps0 = 23 + (26 + seconds / 60) / 60;
  const eps = eps0 + 0.00256 * Math.cos(omega * DEG);
  const decl = Math.asin(Math.sin(eps * DEG) * Math.sin(lambda * DEG)) / DEG;

  const yTan = Math.tan((eps * DEG) / 2) ** 2;
  const eqTime =
    (4 *
      (yTan * Math.sin(2 * l0 * DEG) -
        2 * e * Math.sin(m * DEG) +
        4 * e * yTan * Math.sin(m * DEG) * Math.cos(2 * l0 * DEG) -
        0.5 * yTan * yTan * Math.sin(4 * l0 * DEG) -
        1.25 * e * e * Math.sin(2 * m * DEG))) /
    DEG;

  const zenith = 90.833;
  const cosH =
    Math.cos(zenith * DEG) / (Math.cos(lat * DEG) * Math.cos(decl * DEG)) -
    Math.tan(lat * DEG) * Math.tan(decl * DEG);
  if (cosH > 1 || cosH < -1) return null; // jamais au Maroc — nuit/jour polaire
  const hourAngle = Math.acos(cosH) / DEG;

  const solarNoonMin = 720 - 4 * lon - eqTime + tzOffsetHours * 60;
  return {
    sunriseMin: solarNoonMin - 4 * hourAngle,
    sunsetMin: solarNoonMin + 4 * hourAngle,
  };
}

/**
 * Fenêtre de Ramadan (imsak + iftar) pour une date et un point GPS.
 *
 *  - IFTAR = coucher du soleil NOAA, exact (c'est la définition).
 *  - IMSAK/FAJR = lever du soleil MOINS 80 minutes — APPROXIMATION assumée. Le
 *    fajr vrai est l'aube astronomique (dépression solaire de 18° pour la
 *    convention de la Ligue islamique mondiale, 19° pour d'autres) ; l'écart
 *    lever↔aube varie de ~70 à ~95 min sous nos latitudes selon la saison. On
 *    retient 80 min, valeur médiane, et on l'ÉTIQUETTE : la puce n'affiche que
 *    l'iftar (calculé exactement), jamais un imsak présenté comme certain.
 *
 * Hors table (après 2033) ⇒ `null` : l'appelant retombe alors sur sa fenêtre de
 * repli documentée, sans jamais afficher d'heure.
 */
export function ramadanWindow(
  date: Date,
  lat: number = DEFAULT_LAT,
  lon: number = DEFAULT_LON,
): RamadanWindow | null {
  const found = ramadanRangeFor(date);
  if (!found) return null;
  const { range, inRamadan } = found;
  const startMs = isoToUtcMs(range.start);
  const endMs = isoToUtcMs(range.end);
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return null;
  // Dans le Ramadan → le jour même ; hors Ramadan → le jour MÉDIAN de la plage
  // (représentatif du mois, plutôt qu'un premier jour ou un dernier extrême).
  const refMs = inRamadan ? date.getTime() : startMs + (endMs - startMs) / 2;
  const refDay = new Date(Math.floor(refMs / 86400000) * 86400000);
  const sun = sunTimes(
    refDay,
    Number.isFinite(lat) ? lat : DEFAULT_LAT,
    Number.isFinite(lon) ? lon : DEFAULT_LON,
    RAMADAN_TZ_OFFSET_HOURS,
  );
  if (!sun) return null;
  return {
    imsakHour: (sun.sunriseMin - FAJR_BEFORE_SUNRISE_MIN) / 60,
    iftarHour: sun.sunsetMin / 60,
    referenceDate: utcMsToIso(refDay.getTime()),
    hijri: range.hijri,
    inRamadan,
  };
}

/** Heure décimale → libellé lisible. Format 24 h PARTOUT (le Maroc lit l'heure
 *  en 24 h dans les trois langues du site) ; seul le séparateur change : « 18h31 »
 *  en français, « 18:31 » en anglais et en arabe. */
export function formatHourLabel(hour: number, lang: 'fr' | 'en' | 'ar' = 'fr'): string {
  const safe = Number.isFinite(hour) ? Math.max(0, Math.min(23.9999, hour)) : 0;
  const totalMin = Math.round(safe * 60);
  const h = Math.floor(totalMin / 60);
  const min = totalMin % 60;
  const mm = String(min).padStart(2, '0');
  return lang === 'fr' ? `${h}h${mm}` : `${h}:${mm}`;
}

// ════════════════════════════════════════════════════════════════════════════
// 4. LECTURE DÉFENSIVE DU BLOC BACKEND `courbes_journalieres`
// ════════════════════════════════════════════════════════════════════════════

/** Production servie pour UNE saison (forme 24 h + niveaux réels). */
export interface ServedProduction {
  /** 24 parts en HEURE LOCALE (UTC+1), somme = 1. */
  forme: number[];
  /** Énergie du jour moyen de la saison (kWh). */
  kwhJour: number;
  /** PUISSANCE moyenne de l'heure de pointe (kW — jamais des kWh). */
  picKw: number;
  source: string;
}

/**
 * Consommation servie pour UNE saison. `kwhJour` est le NIVEAU (moyenne des
 * factures réelles du lead) — servi depuis CJ1.
 *
 * CJ2b (21/08/2026) — `forme` est la FORME horaire, désormais servable elle
 * aussi : 24 parts en HEURE LOCALE (UTC+1), somme = 1, EXACTEMENT la même
 * convention que `ServedProduction.forme`. Optionnelle : un backend qui ne sert
 * que le niveau (le cas fréquent avant CJ2b) laisse `forme` absente, et
 * `proposalCurve.rawConsumptionShape` retombe alors sur la silhouette
 * d'occupation locale (`OCCUPANCY_SHAPES`), byte-identique au rendu d'avant.
 */
export interface ServedConsumption {
  kwhJour: number;
  forme?: number[];
}

/** Options de batterie réellement portées par le devis. */
export type BatteryOptionId = 'sans' | 'avec';

/**
 * L4 (21/08/2026) — une couche d'équipement composable (script d'appel du
 * commercial : piscine/VE/clim, `apps/ventes/courbes_journalieres.py
 * _equipements`). `kw` (piscine/clim) est une puissance RÉELLE saisie par le
 * commercial ; `kwhJour` (ve) est l'énergie de recharge ajoutée, dérivée du
 * km/semaine réel × la conversion ADEME. `heures` = la fenêtre SOURCÉE où la
 * couche s'applique ; `saisons` = les saisons concernées, `null` = toutes.
 * Piscine/clim REDISTRIBUENT (le total du jour ne bouge pas) ; ve AJOUTE (la
 * seule charge absente des factures passées — voir le module backend).
 */
export interface EquipmentLayer {
  kw?: number;
  kwhJour?: number;
  heures: number[];
  saisons: SeasonId[] | null;
  mode: 'redistribution' | 'addition';
  source: string;
}

export type EquipmentLayerId = 'piscine' | 'clim' | 've';
export type EquipmentLayers = Partial<Record<EquipmentLayerId, EquipmentLayer>>;

export interface DailyCurves {
  noteHoraire: string;
  occupation: OccupancyId | null;
  occupationSource: string;
  production: Partial<Record<SeasonId, ServedProduction>>;
  consommation: Partial<Record<SeasonId, ServedConsumption>>;
  /**
   * CJ2b — provenance de la forme de consommation SERVIE (ex.
   * `"silhouette_occupation:presence_jour"`), quand au moins une saison en
   * porte une. Chaîne vide quand aucune saison ne sert de `forme` — jamais un
   * texte inventé pour habiller un repli local.
   */
  consommationFormeSource: string;
  options: BatteryOptionId[];
  /** Capacité TOTALE de stockage au devis (kWh) — `batterie_kwh_total`. */
  batterieKwh: number | null;
  /** L4 — couches d'équipement (script d'appel), `{}` quand aucune active. */
  equipements: EquipmentLayers;
}

function positiveNumber(v: unknown): number | null {
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) && n > 0 ? n : null;
}

/**
 * Normalise le bloc additif `courbes_journalieres`. Clé ABSENTE (le cas le plus
 * fréquent : devis sans factures réelles ou sans kWc) ⇒ `null` ⇒ la page garde
 * EXACTEMENT son rendu d'avant. Toute sous-clé peut manquer indépendamment
 * (décision fondateur Q6 : on omet, on n'approxime pas) — chaque saison est
 * validée séparément et une saison illisible est simplement absente.
 */
export function parseDailyCurves(raw: unknown): DailyCurves | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null;
  const src = raw as Record<string, unknown>;

  const production: Partial<Record<SeasonId, ServedProduction>> = {};
  const prodSrc = src.production;
  if (prodSrc && typeof prodSrc === 'object') {
    for (const season of SEASON_IDS) {
      const entry = (prodSrc as Record<string, unknown>)[season];
      if (!entry || typeof entry !== 'object') continue;
      const e = entry as Record<string, unknown>;
      const forme = Array.isArray(e.forme) ? e.forme.map((v) => Number(v)) : null;
      const kwhJour = positiveNumber(e.kwh_jour);
      const picKw = positiveNumber(e.pic_kw);
      if (!forme || forme.length !== 24 || forme.some((v) => !Number.isFinite(v) || v < 0)) continue;
      // Une forme entièrement nulle ne dit rien : on l'écarte plutôt que de
      // dessiner une ligne plate qui ressemblerait à une production nulle.
      if (forme.reduce((a, b) => a + b, 0) <= 0) continue;
      if (kwhJour === null || picKw === null) continue;
      production[season] = {
        forme,
        kwhJour,
        picKw,
        source: typeof e.source === 'string' ? e.source : '',
      };
    }
  }

  const consommation: Partial<Record<SeasonId, ServedConsumption>> = {};
  const consSrc = src.consommation;
  if (consSrc && typeof consSrc === 'object') {
    for (const season of SEASON_IDS) {
      const entry = (consSrc as Record<string, unknown>)[season];
      if (!entry || typeof entry !== 'object') continue;
      const e = entry as Record<string, unknown>;
      const kwhJour = positiveNumber(e.kwh_jour);
      if (kwhJour === null) continue;
      // CJ2b — même discipline de validation que la forme de PRODUCTION :
      // exactement 24 nombres finis ≥ 0, somme > 0, sinon on écarte la forme
      // plutôt que de dessiner une silhouette à moitié lue. Le NIVEAU (kwhJour,
      // déjà validé ci-dessus) reste servi même quand la forme est illisible.
      const formeRaw = Array.isArray(e.forme) ? e.forme.map((v) => Number(v)) : null;
      const formeValid =
        !!formeRaw && formeRaw.length === 24 && formeRaw.every((v) => Number.isFinite(v) && v >= 0)
        && formeRaw.reduce((a, b) => a + b, 0) > 0;
      consommation[season] = formeValid ? { kwhJour, forme: formeRaw! } : { kwhJour };
    }
  }

  const rawOptions = Array.isArray(src.options) ? src.options : [];
  const options = (['sans', 'avec'] as const).filter((o) => rawOptions.includes(o));

  // L4 — lecture DÉFENSIVE d'``equipements`` : une couche illisible (mode
  // inconnu, heures vides, grandeur non finie) est simplement écartée, jamais
  // approximée. `heures` est filtré aux entiers 0-23 valides uniquement.
  const equipements: EquipmentLayers = {};
  const equipSrc = src.equipements;
  if (equipSrc && typeof equipSrc === 'object') {
    for (const key of ['piscine', 'clim', 've'] as const) {
      const entry = (equipSrc as Record<string, unknown>)[key];
      if (!entry || typeof entry !== 'object') continue;
      const e = entry as Record<string, unknown>;
      const mode = e.mode === 'redistribution' || e.mode === 'addition' ? e.mode : null;
      if (!mode) continue;
      const heuresRaw = Array.isArray(e.heures) ? e.heures.map((h) => Number(h)) : [];
      const heures = heuresRaw.filter((h) => Number.isInteger(h) && h >= 0 && h <= 23);
      if (heures.length === 0) continue;
      const saisonsRaw = Array.isArray(e.saisons) ? e.saisons : null;
      const saisons = saisonsRaw ? SEASON_IDS.filter((s) => saisonsRaw.includes(s)) : null;
      const kw = mode === 'redistribution' ? positiveNumber(e.kw) : null;
      const kwhJour = mode === 'addition' ? positiveNumber(e.kwh_jour) : null;
      if (mode === 'redistribution' && kw === null) continue;
      if (mode === 'addition' && kwhJour === null) continue;
      equipements[key] = {
        ...(kw !== null ? { kw } : {}),
        ...(kwhJour !== null ? { kwhJour } : {}),
        heures,
        saisons,
        mode,
        source: typeof e.source === 'string' ? e.source : '',
      };
    }
  }

  const occupationRaw = typeof src.occupation === 'string' ? src.occupation : '';
  return {
    noteHoraire: typeof src.note_horaire === 'string' ? src.note_horaire : '',
    // `null` (et non un défaut) quand le serveur ne dit rien : c'est la page qui
    // choisit alors son repli, en le sachant.
    occupation: occupationRaw ? occupancyFromFlag(occupationRaw) : null,
    occupationSource: typeof src.occupation_source === 'string' ? src.occupation_source : '',
    production,
    consommation,
    consommationFormeSource: typeof src.consommation_forme_source === 'string'
      ? src.consommation_forme_source
      : '',
    options,
    batterieKwh: positiveNumber(src.batterie_kwh),
    equipements,
  };
}

/** L4 — libellés FR/EN/AR des couches d'équipement, pour la légende sobre de
 *  la courbe (« profil ajusté : piscine, climatisation »). */
export const EQUIPMENT_LAYER_LABELS: Record<EquipmentLayerId, { fr: string; en: string; ar: string }> = {
  piscine: { fr: 'piscine', en: 'pool', ar: 'المسبح' },
  clim: { fr: 'climatisation', en: 'air conditioning', ar: 'التكييف' },
  ve: { fr: 'véhicule électrique', en: 'electric vehicle', ar: 'السيارة الكهربائية' },
};

/** Couches d'équipement actives pour UNE saison (filtre `saisons`, `null` = toutes). */
export function activeEquipmentLayers(
  equipements: EquipmentLayers | null | undefined,
  season: SeasonId | null | undefined,
): EquipmentLayerId[] {
  if (!equipements) return [];
  return (['piscine', 'clim', 've'] as const).filter((id) => {
    const layer = equipements[id];
    if (!layer) return false;
    return !season || !layer.saisons || layer.saisons.includes(season);
  });
}

/**
 * L4 — légende SOBRE de la courbe quand au moins une couche d'équipement
 * s'applique à la saison affichée (« profil ajusté : piscine, climatisation »).
 * Chaîne vide quand rien n'est actif — la page n'affiche alors RIEN de neuf.
 */
export function equipmentLegendLabel(
  equipements: EquipmentLayers | null | undefined,
  season: SeasonId | null | undefined,
  lang: 'fr' | 'en' | 'ar' = 'fr',
): string {
  const actifs = activeEquipmentLayers(equipements, season);
  if (actifs.length === 0) return '';
  const noms = actifs.map((id) => EQUIPMENT_LAYER_LABELS[id][lang]).join(lang === 'ar' ? '، ' : ', ');
  const prefix = { fr: 'profil ajusté : ', en: 'adjusted profile: ', ar: 'نمط معدَّل: ' }[lang];
  return `${prefix}${noms}`;
}

/** Les saisons réellement servies (production OU consommation), dans l'ordre. */
export function servedSeasons(curves: DailyCurves | null | undefined): SeasonId[] {
  if (!curves) return [];
  return SEASON_IDS.filter((s) => !!curves.production[s] || !!curves.consommation[s]);
}
