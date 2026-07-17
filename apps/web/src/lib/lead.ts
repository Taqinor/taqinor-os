/**
 * Traitement serveur des leads : validation, simulation (proxy ou fallback
 * local), construction de l'enregistrement (consentement horodaté, fbclid +
 * UTM persistés), transfert CRM toléré à l'absence, CAPI fire-and-forget.
 *
 * Tout est paramétré par (env, fetchFn) pour rester testable hors Workers.
 */
import { isBillRangeId, localEstimateBand, qualifiesForCrm, type BillRangeId, type EstimateBand } from './billRange';
import { normalizeMoroccanPhone } from './phone';
import { COMMERCIAL_CATEGORY_IDS } from './commercialCategories';

// ─────────────────────────────────────────────────────────────────────────
// W317 — same-origin enforcement + honeypot, partagés par TOUS les proxies
// POST same-origin (src/pages/api/*.ts). Additif : le contrat webhook/CRM
// existant (validateLead, buildLeadRecord, forwardLead…) est INCHANGÉ ; ceci
// ajoute une vérification EN AMONT, avant tout traitement de body.
// ─────────────────────────────────────────────────────────────────────────

/**
 * `Origin`/`Sec-Fetch-Site` étaient jusqu'ici de la documentation
 * (« proxy same-origin ») jamais vérifiée en pratique : le rate-limit par IP
 * (lib/rateLimit.ts) reste best-effort par isolate et ne bloque pas un
 * cross-site direct. `Sec-Fetch-Site` (émis par tous les navigateurs
 * modernes) est le signal le plus fiable — `same-origin`/`same-site`/`none`
 * (navigation directe, ex. curl/Postman) passent ; `cross-site` est rejeté.
 * Quand `Sec-Fetch-Site` est absent (vieux navigateur, certains clients HTTP
 * hors-navigateur), on retombe sur `Origin` comparé à `request.url` — un
 * mismatch EXPLICITE est rejeté, mais l'absence totale des deux en-têtes
 * (navigation directe sans fetch, tests, outils serveur-à-serveur légitimes)
 * n'est PAS bloquée : ce garde-fou cible le cross-site FORGÉ, pas les clients
 * qui n'envoient simplement pas ces en-têtes.
 */
export function isSameOriginRequest(request: Request): boolean {
  const secFetchSite = request.headers.get('sec-fetch-site');
  if (secFetchSite) return secFetchSite !== 'cross-site';

  const origin = request.headers.get('origin');
  if (!origin) return true; // aucun signal exploitable → laissé passer (voir note ci-dessus)
  try {
    return new URL(origin).origin === new URL(request.url).origin;
  } catch {
    return false; // Origin illisible : on ne peut pas prouver l'égalité → rejeté
  }
}

/**
 * Réponse 403 uniforme pour un POST cross-site détecté. Porte à la fois
 * `errors.origin` (forme des endpoints capture-lead/simulate/preview-lead/
 * roof-*) ET `detail` (forme des endpoints proposition-*) — chaque handler
 * lit déjà l'un ou l'autre selon son propre contrat, jamais les deux à la
 * fois, donc les deux clés cohabitent sans ambiguïté pour l'appelant.
 */
export function crossSiteRejection(): Response {
  return new Response(
    JSON.stringify({ ok: false, detail: 'Requête refusée.', errors: { origin: 'Requête refusée.' } }),
    { status: 403, headers: { 'content-type': 'application/json' } },
  );
}

/**
 * Honeypot anti-bot : un champ caché (jamais rempli par un humain, CSS-masqué
 * côté formulaire) que seul un bot remplissant tous les champs remplit. Additif
 * — n'existe pas encore côté payload actuel, donc absent/vide est le cas
 * NORMAL pour un visiteur réel ; seule une valeur non vide est suspecte.
 */
export const HONEYPOT_FIELD = 'website_url';

export function isHoneypotTripped(body: unknown): boolean {
  const v = (body as Record<string, unknown> | null | undefined)?.[HONEYPOT_FIELD];
  return typeof v === 'string' && v.trim().length > 0;
}

export const ROOF_TYPES = [
  { id: 'villa', label: 'Villa' },
  { id: 'hangar', label: 'Hangar industriel' },
  { id: 'toit_plat', label: 'Toit plat' },
  { id: 'autre', label: 'Autre' },
] as const;
export type RoofTypeId = (typeof ROOF_TYPES)[number]['id'];

export const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as const;
export type UtmKey = (typeof UTM_KEYS)[number];

// ——— WJ30 : vocabulaires des champs FACULTATIFS élargis (pass-through webhook) ———
// WJ121 — 4 vrais modes au départ du parcours : la carte « Professionnel » est
// scindée en 'industriel' (usine, production) et 'commercial' (hôtel, commerce,
// services). 'professionnel' reste ACCEPTÉ ici comme alias de compatibilité
// (sessions en cours, anciens liens ; le backend webhooks.py mappe déjà
// professionnel→industriel) mais n'est plus jamais ÉMIS par le site.
export const LEAD_MODES = ['residentiel', 'professionnel', 'industriel', 'commercial', 'agricole'] as const;
export type LeadModeId = (typeof LEAD_MODES)[number];

export const RACCORDEMENTS = ['monophase', 'triphase', 'inconnu'] as const;
export type RaccordementId = (typeof RACCORDEMENTS)[number];

export const LEAD_LANGS = ['fr', 'ar'] as const;
export type LeadLangId = (typeof LEAD_LANGS)[number];

// ——— WJ31 : vocabulaires des questions de capture élargies (facultatives) ———
export const DISTRIBUTEURS = ['onee', 'lydec', 'redal', 'inconnu'] as const;
export type DistributeurId = (typeof DISTRIBUTEURS)[number];

export const OMBRAGES = ['aucun', 'partiel', 'important'] as const;
export type OmbrageId = (typeof OMBRAGES)[number];

export const FUTURE_LOADS = ['clim', 've', 'pompe'] as const;
export type FutureLoadId = (typeof FUTURE_LOADS)[number];

export const OCCUPANT_TYPES = ['proprietaire', 'locataire', 'decideur'] as const;
export type OccupantTypeId = (typeof OCCUPANT_TYPES)[number];

export const PROJECT_TIMINGS = ['maintenant', '3mois', 'renseignement'] as const;
export type ProjectTimingId = (typeof PROJECT_TIMINGS)[number];

export const FINANCING_INTENTS = ['comptant', 'financement', 'indecis'] as const;
export type FinancingIntentId = (typeof FINANCING_INTENTS)[number];

// ——— WJ51 : préférence de contact explicite (facultative, pass-through webhook) ———
// Remplace la promesse floue « pas d'appels commerciaux » par un choix nommé,
// mappé sur le champ `canal` du CRM. Facultatif : une soumission sans ce champ
// reste valide (repli implicite WhatsApp, cohérent avec whatsappOptIn coché
// par défaut).
export const CONTACT_PREFERENCES = ['whatsapp_only', 'phone_ok'] as const;
export type ContactPreferenceId = (typeof CONTACT_PREFERENCES)[number];

// ——— W353 : créneau de visite technique v1 (facultatif, STATIQUE — pas de
// dépendance calendrier, pas de paiement/dépôt en ligne — cette question reste
// une décision fondateur WG13). Un choix de MOMENT (matin/après-midi) + un
// choix de SEMAINE (cette semaine / la semaine prochaine) : une préférence
// forwardée telle quelle, jamais un vrai créneau réservé/confirmé — la visite
// reste planifiée par un humain après contact.
export const VISIT_WINDOW_PARTS = ['matin', 'apres_midi'] as const;
export type VisitWindowPartId = (typeof VISIT_WINDOW_PARTS)[number];

export const VISIT_WINDOW_WEEKS = ['cette_semaine', 'semaine_prochaine'] as const;
export type VisitWindowWeekId = (typeof VISIT_WINDOW_WEEKS)[number];

// ——— WJ68 : mode PROFESSIONNEL — vocabulaires FACULTATIFS, additifs. Le
// formulaire résidentiel-shaped ne bloque aucun visiteur C&I ; ces trois
// signaux (raison sociale, type de site, nombre de sites) partent au webhook
// SEULEMENT si renseignés — jamais un nouveau champ obligatoire. ———
export const FACILITY_TYPES = ['bureau', 'entrepot', 'usine', 'commerce', 'agricole', 'autre'] as const;
export type FacilityTypeId = (typeof FACILITY_TYPES)[number];

export const SITE_COUNTS = ['1', '2-5', '6+'] as const;
export type SiteCountId = (typeof SITE_COUNTS)[number];

// ——— QX parcours 3 profils : vocabulaires FACULTATIFS pro & agricole (additifs,
// jamais bloquants — même discipline que WJ30/WJ31). `tensionRaccordement`
// (BT/MT, tension de livraison pro) est DISTINCT du `raccordement` existant
// (monophasé/triphasé, résidentiel) — les deux champs cohabitent. ———
export const TENSION_RACCORDEMENTS = ['bt', 'mt'] as const;
export type TensionRaccordementId = (typeof TENSION_RACCORDEMENTS)[number];

export const ACTIVITY_PROFILES = ['day', 'day_evening', 'continuous'] as const;
export type ActivityProfileId = (typeof ACTIVITY_PROFILES)[number];

export const SURFACE_TYPES = ['bac_acier', 'terrasse', 'ombriere', 'terrain'] as const;
export type SurfaceTypeId = (typeof SURFACE_TYPES)[number];

export const WATER_SOURCES = ['puits', 'forage', 'bassin', 'riviere'] as const;
export type WaterSourceId = (typeof WATER_SOURCES)[number];

export const IRRIGATIONS = ['goutte', 'aspersion', 'gravitaire'] as const;
export type IrrigationId = (typeof IRRIGATIONS)[number];

export const POMPES_ACTUELLES = ['aucune', 'diesel', 'butane', 'electrique'] as const;
export type PompeActuelleId = (typeof POMPES_ACTUELLES)[number];

// ——— WJ122 : mode COMMERCIAL — vocabulaires FACULTATIFS additifs (même
// discipline que WJ30/WJ31 : validés un à un, écartés si malformés, jamais
// bloquants). `categorieCommerciale` + les réponses par catégorie miroir de
// COMMERCIAL_CATEGORY_QUESTIONS (lib/commercialCategories.ts) et de la liste
// blanche webhook QX51 (SOURCE: backend/django_core/apps/crm/webhooks.py
// `_extract_web_questionnaire`). ———
export const CUISSON_MODES = ['electrique', 'gaz'] as const;
export type CuissonModeId = (typeof CUISSON_MODES)[number];

export const HORAIRES_MODES = ['midi', 'soir', 'continu'] as const;
export type HoraireModeId = (typeof HORAIRES_MODES)[number];

// ——— WJ123 : mode INDUSTRIEL v2 — pattern d'équipes. SOURCE: webhooks.py
// `_extract_web_questionnaire` (enum `equipes` = 1x8/2x8/3x8/continu, `weekend`
// est un booléen SÉPARÉ, jamais une 5e valeur combinée). ———
export const EQUIPES_MODES = ['1x8', '2x8', '3x8', 'continu'] as const;
export type EquipeModeId = (typeof EQUIPES_MODES)[number];

// ——— WJ124 : mode AGRICOLE — région (8 zones agronomiques FAO). SOURCE:
// backend/django_core/apps/ventes/quote_engine/agricole/agronomy.py ET0_MONTHLY. ———
export const REGIONS_AGRICOLES = [
  'souss-massa', 'doukkala', 'tadla', 'saiss', 'oriental',
  'draa-tafilalet', 'gharb-loukkos', 'haouz',
] as const;
export type RegionAgricoleId = (typeof REGIONS_AGRICOLES)[number];

/**
 * Plafond de facture mensuelle saisissable (MAD) PAR MODE — les modes C&I
 * (industriel/commercial, et l'alias hérité professionnel) montent à 1 M MAD,
 * résidentiel/agricole gardent le plafond historique 200 000. WJ121 :
 * industriel ET commercial reprennent le plafond professionnel existant —
 * jamais un nouveau chiffre métier inventé. Constante partagée écran/serveur
 * (une seule source).
 */
export const MAX_BILL_BY_MODE: Record<LeadModeId, number> = {
  residentiel: 200_000,
  professionnel: 1_000_000,
  industriel: 1_000_000,
  commercial: 1_000_000,
  agricole: 200_000,
};

/**
 * Instantané de l'ESTIMATION AFFICHÉE au visiteur au moment de la soumission
 * (pour que le CRM voie exactement les chiffres promis) — clés en LISTE
 * BLANCHE stricte, tout le reste est écarté (jamais un objet arbitraire
 * forwardé au webhook).
 */
export interface EstimateShown {
  kwc?: number;
  prodKwh?: number;
  ecoMadMonthLow?: number;
  ecoMadMonthHigh?: number;
  ecoMadYearLow?: number;
  ecoMadYearHigh?: number;
  paybackLabel?: string;
  tauxAutoconso?: number;
  tauxCouverture?: number;
  pompeCv?: number;
  champKwc?: number;
  m3Jour?: number;
  // WJ124 — bassin de stockage suggéré (m³) : besoin journalier de pointe (1×),
  // borne basse de la fourchette 1-3× montrée au client.
  bassinM3?: number;
}
const ESTIMATE_SHOWN_NUMERIC_KEYS = [
  'kwc', 'prodKwh', 'ecoMadMonthLow', 'ecoMadMonthHigh', 'ecoMadYearLow',
  'ecoMadYearHigh', 'tauxAutoconso', 'tauxCouverture', 'pompeCv', 'champKwc', 'm3Jour',
  'bassinM3',
] as const;

/**
 * Bornes GPS ≈ Maroc (Tanger ~35,9 N → Lagouira ~20,8 N ; Atlantique ~-17,2 O →
 * frontière est ~-1,0). Garde-fou anti-garbage : un repère hors bornes est
 * ÉCARTÉ silencieusement — le lead passe sans lui, jamais bloqué.
 */
export const MOROCCO_GPS_BOUNDS = { latMin: 20, latMax: 37, lngMin: -18, lngMax: 0 } as const;

export function isMoroccoLat(lat: number): boolean {
  return Number.isFinite(lat) && lat >= MOROCCO_GPS_BOUNDS.latMin && lat <= MOROCCO_GPS_BOUNDS.latMax;
}
export function isMoroccoLng(lng: number): boolean {
  return Number.isFinite(lng) && lng >= MOROCCO_GPS_BOUNDS.lngMin && lng <= MOROCCO_GPS_BOUNDS.lngMax;
}

export interface LeadEnv {
  SIMULATOR_API_URL?: string;
  LEAD_WEBHOOK_URL?: string;
  /** Secret partagé avec le récepteur taqinor-os (X-Webhook-Secret). */
  LEAD_WEBHOOK_SECRET?: string;
  CAPI_URL?: string;
  WHATSAPP_NUMBER?: string;
}

export interface ValidatedLead {
  fullName: string;
  phoneE164: string;
  whatsappOptIn: boolean;
  // — WJ97 : `city`/`roofType`/`billRange` restent REQUIS pour toute soumission
  //   /devis/mon-toit (le seul appelant historique construit toujours les
  //   trois) ; ils deviennent absents UNIQUEMENT pour le chemin `quickCallback`
  //   ci-dessous (rappel rapide /contact — nom + téléphone seulement, aucune
  //   facture/toiture connue à ce stade). Marqués `?:` pour permettre cette
  //   absence honnête, jamais une valeur fabriquée à leur place.
  city?: string;
  roofType?: RoofTypeId;
  billRange?: BillRangeId;
  consent: true;
  // — WJ97 : demande de rappel RAPIDE depuis /contact (nom + téléphone
  //   seulement, AUCUNE facture/toiture connue à ce stade) — présent et `true`
  //   UNIQUEMENT pour ce chemin allégé (cf. `quickCallback` dans validateLead
  //   ci-dessous). Absent pour toute soumission /devis/mon-toit existante —
  //   contrat de fil inchangé octet pour octet pour elles.
  quickCallback?: true;
  fbclid: string | null;
  utm: Partial<Record<UtmKey, string>>;
  // — WJ30 : champs FACULTATIFS élargis. Présents UNIQUEMENT si la valeur reçue
  //   est valide : un champ facultatif malformé est ÉCARTÉ (jamais bloquant), et
  //   un champ absent reste absent — le contrat de fil existant est inchangé
  //   octet pour octet pour les soumissions d'aujourd'hui.
  email?: string;
  factureHiver?: number;
  factureEte?: number | null;
  eteDifferente?: boolean;
  billKwh?: number;
  raccordement?: RaccordementId;
  adresse?: string;
  mode?: LeadModeId;
  langue_preferee?: LeadLangId;
  roofPoint?: { lat: number; lng: number };
  gpsLat?: number;
  gpsLng?: number;
  roofOutline?: Array<[number, number]>;
  // — WJ31 : questions de capture « best-in-world », toutes FACULTATIVES, même
  //   discipline que WJ30 (validées une à une, écartées si malformées, jamais
  //   bloquantes — la soumission reste possible en sautant tout ceci).
  distributeur?: DistributeurId;
  roofAgeYears?: number;
  ombrage?: OmbrageId;
  futureLoads?: FutureLoadId[];
  batteryInterest?: boolean;
  occupantType?: OccupantTypeId;
  projectTiming?: ProjectTimingId;
  financingIntent?: FinancingIntentId;
  /** Le client a pris une photo compteur/facture EN LOCAL (jamais uploadée : pas
   *  d'endpoint d'upload aujourd'hui — cf. PLAN2 QK6 OCR). Signal booléen SEUL :
   *  aucune donnée binaire ne quitte le navigateur. */
  hasMeterPhoto?: boolean;
  // — WJ51 : préférence de contact explicite (facultative — mappée sur `canal` CRM).
  contactPreference?: ContactPreferenceId;
  // — W353 : préférence de créneau de visite technique (facultative, STATIQUE —
  //   jamais une réservation confirmée). Les deux moitiés sont indépendantes :
  //   l'une peut être présente sans l'autre.
  visitWindowPart?: VisitWindowPartId;
  visitWindowWeek?: VisitWindowWeekId;
  // — WJ52 : référence courte générée CÔTÉ CLIENT (aucune garantie d'unicité
  //   globale — un simple artefact affiché au visiteur + échoé au webhook pour
  //   corréler une conversation WhatsApp ; jamais utilisée comme clé d'unicité
  //   serveur). Bornée en longueur/format pour rester un artefact honnête.
  clientRef?: string;
  // — WJ64 : diaspora — présent et `true` UNIQUEMENT quand `phoneE164` est un
  //   E.164 étranger (indicatif ≠ 212, cf. lib/phone.ts). Absent pour un numéro
  //   marocain (contrat de fil inchangé pour la quasi-totalité des leads). La
  //   logique 1 000 MAD (qualifiesForCrm) ne lit jamais ce champ.
  phoneIsForeign?: boolean;
  // — WJ66 : jeton d'idempotence généré CÔTÉ NAVIGATEUR à l'ouverture de la
  //   session de saisie (pas un identifiant serveur, aucune garantie
  //   d'unicité globale — sert de signal de dédoublonnage best-effort côté
  //   CRM, jamais une clé bloquante ici). Facultatif, borné, jamais bloquant.
  idempotencyKey?: string;
  // — WJ68 : mode PROFESSIONNEL — champs facultatifs, additifs, jamais
  //   bloquants (raison sociale, type de site, nombre de sites).
  raisonSociale?: string;
  facilityType?: FacilityTypeId;
  siteCount?: SiteCountId;
  // — WJ92 : identifiant de déduplication CAPI par soumission (echoé au CRM ET
  //   au CAPI — pas de la PII). Le hash e-mail `em` est calculé dans fireCapi
  //   au moment de l'envoi (jamais stocké sur le lead).
  eventId?: string;
  // — QX parcours 3 profils : champs FACULTATIFS pro & agricole, même
  //   discipline WJ30 (validés un à un, écartés si malformés, jamais
  //   bloquants ; absents ⇒ contrat de fil inchangé octet pour octet).
  // Professionnel :
  tensionRaccordement?: TensionRaccordementId;
  puissanceKva?: number;
  activityProfile?: ActivityProfileId;
  surfaceType?: SurfaceTypeId;
  surfaceM2?: number;
  hasGenerator?: boolean;
  proMonthlyKwh?: number;
  proMonthlyMad?: number;
  // Agricole (pompage) :
  waterSource?: WaterSourceId;
  profondeurM?: number;
  hmtM?: number;
  debitM3h?: number;
  besoinM3j?: number;
  heuresPompage?: number;
  irrigation?: IrrigationId;
  culture?: string;
  surfaceHa?: number;
  pompeActuelle?: PompeActuelleId;
  pompeCvActuelle?: number;
  fuelSpendMad?: number;
  // — WJ124 : région agronomique (8 zones FAO) — pilote le moteur eau agricole
  //   (agronomy.ts) quand le débit/HMT n'est pas connu. Même discipline WJ30.
  regionAgricole?: RegionAgricoleId;
  // — WJ122 : mode COMMERCIAL — catégorie + réponses par catégorie (facultatives,
  //   validées une à une, écartées si malformées, jamais bloquantes). Les clés
  //   camelCase correspondent EXACTEMENT à la liste blanche webhook QX51.
  categorieCommerciale?: (typeof COMMERCIAL_CATEGORY_IDS)[number];
  chambres?: number;
  occupationPct?: number;
  chambresFroides?: number;
  effectif?: number;
  lits?: number;
  surfaceVenteM2?: number;
  volumeM3?: number;
  /** Température de consigne (froid) — peut être NÉGATIVE (ex. -18 °C). */
  temperatureConsigne?: number;
  cuisson?: CuissonModeId;
  four?: CuissonModeId;
  chauffe?: CuissonModeId;
  horaires?: HoraireModeId;
  cuissonNocturne?: boolean;
  piscine?: boolean;
  blanchisserie?: boolean;
  internat?: boolean;
  fermetureEstivale?: boolean;
  saisonnaliteRecolte?: boolean;
  gardeNuit?: boolean;
  clim?: boolean;
  // — WJ123 : mode INDUSTRIEL v2 — profil de charge affiné (facultatif, additif).
  equipes?: EquipeModeId;
  weekend?: boolean;
  cosPhiConnu?: number;
  groupeKva?: number;
  dieselDhMois?: number;
  surfaceToitureM2?: number;
  ombriere?: boolean;
  terrain?: boolean;
  // Instantané de l'estimation affichée (liste blanche stricte — cf. EstimateShown).
  estimateShown?: EstimateShown;
}

export type ValidationResult =
  | { ok: true; lead: ValidatedLead }
  | { ok: false; errors: Record<string, string> };

function cleanStr(v: unknown, max = 200): string {
  return typeof v === 'string' ? v.trim().slice(0, max) : '';
}

// ——— WJ30 : nettoyeurs des champs FACULTATIFS (rejettent le garbage, ne bloquent jamais) ———

/** Plafonds de bon sens anti-garbage (jamais affichés — validation serveur only). */
const MAX_BILL_MAD = 1_000_000;
const MAX_KWH = 10_000_000;

/** E-mail facultatif — garde-fou minimal (pas une RFC complète), borné à 254. */
function cleanOptionalEmail(v: unknown): string | null {
  if (typeof v !== 'string') return null;
  const s = v.trim().slice(0, 254);
  return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s) ? s : null;
}

/** Nombre fini > 0 borné, sinon null (factures/kWh : jamais négatif ni absurde). */
function cleanPositiveNumber(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n > 0 && n <= max ? n : null;
}

/**
 * WJ122 — nombre fini borné [min, max] AUTORISANT le négatif et le zéro (la
 * température de consigne d'un froid peut valoir -18 °C, ou 0). Écarté (null)
 * hors bornes ou non numérique — jamais deviné.
 */
function cleanBoundedSignedNumber(v: unknown, min: number, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= min && n <= max ? n : null;
}

/** Valeur d'une liste fermée, sinon null (on ne devine pas). */
function cleanEnum<T extends string>(v: unknown, allowed: readonly T[]): T | null {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : null;
}

/** {lat,lng} fini DANS les bornes ≈ Maroc, ou null. */
function cleanRoofPoint(v: unknown): { lat: number; lng: number } | null {
  if (!v || typeof v !== 'object') return null;
  const o = v as { lat?: unknown; lng?: unknown };
  const lat = Number(o.lat);
  const lng = Number(o.lng);
  if (!isMoroccoLat(lat) || !isMoroccoLng(lng)) return null;
  return { lat, lng };
}

/** Entier fini borné [0, max] (âge de toit en années), sinon null. */
function cleanBoundedInt(v: unknown, max: number): number | null {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= max ? Math.round(n) : null;
}

/** Liste de puces d'une liste fermée : garde uniquement les valeurs connues,
 *  déduplique, borne à la taille du vocabulaire. Jamais bloquant : les entrées
 *  inconnues sont juste écartées silencieusement. Tableau vide ⇒ absent. */
function cleanEnumList<T extends string>(v: unknown, allowed: readonly T[]): T[] {
  if (!Array.isArray(v)) return [];
  const set = new Set<T>();
  for (const item of v) {
    if (typeof item === 'string' && (allowed as readonly string[]).includes(item)) set.add(item as T);
  }
  return Array.from(set).slice(0, allowed.length);
}

/**
 * QX — instantané d'estimation en LISTE BLANCHE stricte : seules les clés
 * numériques connues (finies, [0, 1e9]) et `paybackLabel` (chaîne bornée)
 * passent ; tout le reste est écarté. Objet vide/malformé ⇒ null (absent).
 */
function cleanEstimateShown(v: unknown): EstimateShown | null {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return null;
  const o = v as Record<string, unknown>;
  const out: EstimateShown = {};
  for (const key of ESTIMATE_SHOWN_NUMERIC_KEYS) {
    const n = Number(o[key]);
    if (o[key] != null && o[key] !== '' && Number.isFinite(n) && n >= 0 && n <= 1e9) out[key] = n;
  }
  const paybackLabel = cleanStr(o.paybackLabel, 60);
  if (paybackLabel) out.paybackLabel = paybackLabel;
  return Object.keys(out).length > 0 ? out : null;
}

/** [[lat,lng],…] (≥ 3 paires finies dans les bornes ≈ Maroc), borné à 200 sommets, ou []. */
function cleanRoofOutline(v: unknown): Array<[number, number]> {
  if (!Array.isArray(v)) return [];
  const out: Array<[number, number]> = [];
  for (const p of v.slice(0, 200)) {
    if (!Array.isArray(p) || p.length < 2) continue;
    const lat = Number(p[0]);
    const lng = Number(p[1]);
    if (isMoroccoLat(lat) && isMoroccoLng(lng)) out.push([lat, lng]);
  }
  return out.length >= 3 ? out : [];
}

/**
 * WJ30 — champs FACULTATIFS élargis : chacun est validé individuellement et
 * ÉCARTÉ s'il est malformé. Ne produit JAMAIS d'erreur : un lead qui passait
 * hier passe toujours, avec ou sans ces champs.
 */
function validateOptionalFields(b: Record<string, unknown>): Partial<ValidatedLead> {
  const opt: Partial<ValidatedLead> = {};

  const email = cleanOptionalEmail(b.email);
  if (email) opt.email = email;

  const factureHiver = cleanPositiveNumber(b.factureHiver, MAX_BILL_MAD);
  if (factureHiver != null) opt.factureHiver = factureHiver;

  // Été ≠ hiver : une seule pièce d'info (le toggle) avec sa valeur d'été.
  // Été non différent ⇒ factureEte forcé à null (jamais une valeur résiduelle).
  if (typeof b.eteDifferente === 'boolean') {
    opt.eteDifferente = b.eteDifferente;
    opt.factureEte = b.eteDifferente ? cleanPositiveNumber(b.factureEte, MAX_BILL_MAD) : null;
  }

  const billKwh = cleanPositiveNumber(b.billKwh, MAX_KWH);
  if (billKwh != null) opt.billKwh = billKwh;

  const raccordement = cleanEnum(b.raccordement, RACCORDEMENTS);
  if (raccordement) opt.raccordement = raccordement;

  const adresse = cleanStr(b.adresse, 200);
  if (adresse) opt.adresse = adresse;

  const mode = cleanEnum(b.mode, LEAD_MODES);
  if (mode) opt.mode = mode;

  const langue = cleanEnum(b.langue_preferee ?? b.langue, LEAD_LANGS);
  if (langue) opt.langue_preferee = langue;

  const roofPoint = cleanRoofPoint(b.roofPoint);
  if (roofPoint) {
    opt.roofPoint = roofPoint;
    // Le repère validé PRIME sur les champs gps* bruts.
    opt.gpsLat = roofPoint.lat;
    opt.gpsLng = roofPoint.lng;
  } else {
    const gpsLat = Number(b.gpsLat);
    const gpsLng = Number(b.gpsLng);
    if (b.gpsLat != null && isMoroccoLat(gpsLat)) opt.gpsLat = gpsLat;
    if (b.gpsLng != null && isMoroccoLng(gpsLng)) opt.gpsLng = gpsLng;
  }

  const roofOutline = cleanRoofOutline(b.roofOutline);
  if (roofOutline.length >= 3) opt.roofOutline = roofOutline;

  // ——— WJ31 : questions de capture élargies (facultatives) ———
  const distributeur = cleanEnum(b.distributeur, DISTRIBUTEURS);
  if (distributeur) opt.distributeur = distributeur;

  const roofAgeYears = cleanBoundedInt(b.roofAgeYears, 100);
  if (roofAgeYears != null) opt.roofAgeYears = roofAgeYears;

  const ombrage = cleanEnum(b.ombrage, OMBRAGES);
  if (ombrage) opt.ombrage = ombrage;

  const futureLoads = cleanEnumList(b.futureLoads, FUTURE_LOADS);
  if (futureLoads.length > 0) opt.futureLoads = futureLoads;

  if (typeof b.batteryInterest === 'boolean') opt.batteryInterest = b.batteryInterest;

  const occupantType = cleanEnum(b.occupantType, OCCUPANT_TYPES);
  if (occupantType) opt.occupantType = occupantType;

  const projectTiming = cleanEnum(b.projectTiming, PROJECT_TIMINGS);
  if (projectTiming) opt.projectTiming = projectTiming;

  const financingIntent = cleanEnum(b.financingIntent, FINANCING_INTENTS);
  if (financingIntent) opt.financingIntent = financingIntent;

  if (typeof b.hasMeterPhoto === 'boolean') opt.hasMeterPhoto = b.hasMeterPhoto;

  // ——— WJ51 : préférence de contact explicite (facultative) ———
  const contactPreference = cleanEnum(b.contactPreference, CONTACT_PREFERENCES);
  if (contactPreference) opt.contactPreference = contactPreference;

  // ——— W353 : créneau de visite technique (facultatif, STATIQUE) ———
  const visitWindowPart = cleanEnum(b.visitWindowPart, VISIT_WINDOW_PARTS);
  if (visitWindowPart) opt.visitWindowPart = visitWindowPart;

  const visitWindowWeek = cleanEnum(b.visitWindowWeek, VISIT_WINDOW_WEEKS);
  if (visitWindowWeek) opt.visitWindowWeek = visitWindowWeek;

  // ——— WJ52 : référence courte générée côté client (facultative, jamais bloquante) ———
  const clientRef = cleanStr(b.clientRef, 24);
  // Anti-garbage minimal : lettres/chiffres/tirets seulement (le format généré
  // par buildClientRef() plus bas) — une valeur malformée est simplement écartée.
  if (clientRef && /^[A-Z0-9-]{4,24}$/i.test(clientRef)) opt.clientRef = clientRef;

  // ——— WJ66 : jeton d'idempotence généré côté navigateur (facultatif, jamais
  // bloquant). Même discipline anti-garbage que clientRef : alphanumérique +
  // tiret/underscore, borné — une valeur malformée est simplement écartée
  // (jamais une clé d'unicité serveur, un simple signal de dédoublonnage CRM). ———
  const idempotencyKey = cleanStr(b.idempotencyKey, 64);
  if (idempotencyKey && /^[A-Za-z0-9_-]{8,64}$/.test(idempotencyKey)) opt.idempotencyKey = idempotencyKey;

  // ——— WJ68 : mode PROFESSIONNEL — facultatif, additif, jamais bloquant ———
  const raisonSociale = cleanStr(b.raisonSociale, 150);
  if (raisonSociale) opt.raisonSociale = raisonSociale;

  const facilityType = cleanEnum(b.facilityType, FACILITY_TYPES);
  if (facilityType) opt.facilityType = facilityType;

  const siteCount = cleanEnum(b.siteCount, SITE_COUNTS);
  if (siteCount) opt.siteCount = siteCount;

  // ——— WJ92 : identifiant de déduplication CAPI par soumission (facultatif,
  // généré côté navigateur — même discipline anti-garbage qu'idempotencyKey).
  // Distinct d'idempotencyKey (WJ66, sémantique CRM) : eventId est le champ de
  // corrélation attendu par la spec Meta CAPI (`event_id`), échoé tel quel sur
  // le lead ET sur l'appel fireCapi ci-dessous pour permettre la déduplication
  // pixel-navigateur ↔ serveur côté Meta. ———
  const eventId = cleanStr(b.eventId, 64);
  if (eventId && /^[A-Za-z0-9_-]{8,64}$/.test(eventId)) opt.eventId = eventId;

  // ——— QX parcours 3 profils : champs pro & agricole (facultatifs, bornés,
  // écartés en silence si malformés — jamais bloquants). ———
  // Professionnel :
  const tensionRaccordement = cleanEnum(b.tensionRaccordement, TENSION_RACCORDEMENTS);
  if (tensionRaccordement) opt.tensionRaccordement = tensionRaccordement;

  const puissanceKva = cleanPositiveNumber(b.puissanceKva, 10_000);
  if (puissanceKva != null) opt.puissanceKva = puissanceKva;

  const activityProfile = cleanEnum(b.activityProfile, ACTIVITY_PROFILES);
  if (activityProfile) opt.activityProfile = activityProfile;

  const surfaceType = cleanEnum(b.surfaceType, SURFACE_TYPES);
  if (surfaceType) opt.surfaceType = surfaceType;

  const surfaceM2 = cleanPositiveNumber(b.surfaceM2, 1_000_000);
  if (surfaceM2 != null) opt.surfaceM2 = surfaceM2;

  if (typeof b.hasGenerator === 'boolean') opt.hasGenerator = b.hasGenerator;

  const proMonthlyKwh = cleanPositiveNumber(b.proMonthlyKwh, MAX_KWH);
  if (proMonthlyKwh != null) opt.proMonthlyKwh = proMonthlyKwh;

  const proMonthlyMad = cleanPositiveNumber(b.proMonthlyMad, MAX_BILL_MAD);
  if (proMonthlyMad != null) opt.proMonthlyMad = proMonthlyMad;

  // Agricole (pompage) :
  const waterSource = cleanEnum(b.waterSource, WATER_SOURCES);
  if (waterSource) opt.waterSource = waterSource;

  const profondeurM = cleanPositiveNumber(b.profondeurM, 1_000);
  if (profondeurM != null) opt.profondeurM = profondeurM;

  const hmtM = cleanPositiveNumber(b.hmtM, 1_000);
  if (hmtM != null) opt.hmtM = hmtM;

  const debitM3h = cleanPositiveNumber(b.debitM3h, 1_000);
  if (debitM3h != null) opt.debitM3h = debitM3h;

  const besoinM3j = cleanPositiveNumber(b.besoinM3j, 100_000);
  if (besoinM3j != null) opt.besoinM3j = besoinM3j;

  const heuresPompage = cleanPositiveNumber(b.heuresPompage, 24);
  if (heuresPompage != null) opt.heuresPompage = heuresPompage;

  const irrigation = cleanEnum(b.irrigation, IRRIGATIONS);
  if (irrigation) opt.irrigation = irrigation;

  const culture = cleanStr(b.culture, 60);
  if (culture) opt.culture = culture;

  const surfaceHa = cleanPositiveNumber(b.surfaceHa, 100_000);
  if (surfaceHa != null) opt.surfaceHa = surfaceHa;

  const pompeActuelle = cleanEnum(b.pompeActuelle, POMPES_ACTUELLES);
  if (pompeActuelle) opt.pompeActuelle = pompeActuelle;

  const pompeCvActuelle = cleanPositiveNumber(b.pompeCvActuelle, 1_000);
  if (pompeCvActuelle != null) opt.pompeCvActuelle = pompeCvActuelle;

  const fuelSpendMad = cleanPositiveNumber(b.fuelSpendMad, MAX_BILL_MAD);
  if (fuelSpendMad != null) opt.fuelSpendMad = fuelSpendMad;

  // ——— WJ124 : région agronomique (agricole) ———
  const regionAgricole = cleanEnum(b.regionAgricole, REGIONS_AGRICOLES);
  if (regionAgricole) opt.regionAgricole = regionAgricole;

  // ——— WJ122 : mode COMMERCIAL — catégorie + réponses (facultatives, écartées
  // si malformées, jamais bloquantes ; bornes miroir de la liste blanche webhook). ———
  const categorieCommerciale = cleanEnum(b.categorieCommerciale, COMMERCIAL_CATEGORY_IDS);
  if (categorieCommerciale) opt.categorieCommerciale = categorieCommerciale;

  const chambres = cleanPositiveNumber(b.chambres, 100_000);
  if (chambres != null) opt.chambres = chambres;

  const occupationPct = cleanPositiveNumber(b.occupationPct, 100);
  if (occupationPct != null) opt.occupationPct = occupationPct;

  const chambresFroides = cleanPositiveNumber(b.chambresFroides, 10_000);
  if (chambresFroides != null) opt.chambresFroides = chambresFroides;

  const effectif = cleanPositiveNumber(b.effectif, 1_000_000);
  if (effectif != null) opt.effectif = effectif;

  const lits = cleanPositiveNumber(b.lits, 100_000);
  if (lits != null) opt.lits = lits;

  const surfaceVenteM2 = cleanPositiveNumber(b.surfaceVenteM2, 1_000_000);
  if (surfaceVenteM2 != null) opt.surfaceVenteM2 = surfaceVenteM2;

  const volumeM3 = cleanPositiveNumber(b.volumeM3, 10_000_000);
  if (volumeM3 != null) opt.volumeM3 = volumeM3;

  const temperatureConsigne = cleanBoundedSignedNumber(b.temperatureConsigne, -60, 60);
  if (temperatureConsigne != null) opt.temperatureConsigne = temperatureConsigne;

  const cuisson = cleanEnum(b.cuisson, CUISSON_MODES);
  if (cuisson) opt.cuisson = cuisson;

  const four = cleanEnum(b.four, CUISSON_MODES);
  if (four) opt.four = four;

  const chauffe = cleanEnum(b.chauffe, CUISSON_MODES);
  if (chauffe) opt.chauffe = chauffe;

  const horaires = cleanEnum(b.horaires, HORAIRES_MODES);
  if (horaires) opt.horaires = horaires;

  if (typeof b.cuissonNocturne === 'boolean') opt.cuissonNocturne = b.cuissonNocturne;
  if (typeof b.piscine === 'boolean') opt.piscine = b.piscine;
  if (typeof b.blanchisserie === 'boolean') opt.blanchisserie = b.blanchisserie;
  if (typeof b.internat === 'boolean') opt.internat = b.internat;
  if (typeof b.fermetureEstivale === 'boolean') opt.fermetureEstivale = b.fermetureEstivale;
  if (typeof b.saisonnaliteRecolte === 'boolean') opt.saisonnaliteRecolte = b.saisonnaliteRecolte;
  if (typeof b.gardeNuit === 'boolean') opt.gardeNuit = b.gardeNuit;
  if (typeof b.clim === 'boolean') opt.clim = b.clim;

  // ——— WJ123 : mode INDUSTRIEL v2 — profil de charge affiné ———
  const equipes = cleanEnum(b.equipes, EQUIPES_MODES);
  if (equipes) opt.equipes = equipes;

  if (typeof b.weekend === 'boolean') opt.weekend = b.weekend;

  const cosPhiConnu = cleanPositiveNumber(b.cosPhiConnu, 1);
  if (cosPhiConnu != null) opt.cosPhiConnu = cosPhiConnu;

  const groupeKva = cleanPositiveNumber(b.groupeKva, 1_000_000);
  if (groupeKva != null) opt.groupeKva = groupeKva;

  const dieselDhMois = cleanPositiveNumber(b.dieselDhMois, MAX_BILL_MAD);
  if (dieselDhMois != null) opt.dieselDhMois = dieselDhMois;

  const surfaceToitureM2 = cleanPositiveNumber(b.surfaceToitureM2, 1_000_000);
  if (surfaceToitureM2 != null) opt.surfaceToitureM2 = surfaceToitureM2;

  if (typeof b.ombriere === 'boolean') opt.ombriere = b.ombriere;
  if (typeof b.terrain === 'boolean') opt.terrain = b.terrain;

  const estimateShown = cleanEstimateShown(b.estimateShown);
  if (estimateShown) opt.estimateShown = estimateShown;

  return opt;
}

export function validateLead(body: unknown): ValidationResult {
  const b = (body ?? {}) as Record<string, unknown>;
  const errors: Record<string, string> = {};

  const fullName = cleanStr(b.fullName);
  // WB33 — durcissement additif : un nom fait uniquement d'emojis/symboles
  // (ex. « 😀😀 ») passait le seuil de longueur ≥ 2 sans jamais contenir de
  // lettre. On exige ICI au moins UNE lettre (tout alphabet — \p{L} couvre le
  // latin ET l'arabe), même garde-fou que mon-toit.astro côté client.
  if (fullName.length < 2 || !/\p{L}/u.test(fullName)) errors.fullName = 'Nom complet requis';

  const phone = normalizeMoroccanPhone(cleanStr(b.phone, 30));
  if (!phone.ok) errors.phone = phone.error ?? 'Numéro invalide';

  // — WJ97 : chemin RAPPEL RAPIDE (/contact « Demander un rappel ») — nom +
  //   téléphone SEULEMENT, aucune ville/toiture/facture connue à ce stade. Ce
  //   flag n'existe QUE sur ce nouveau chemin ; toute soumission existante
  //   (mon-toit) ne l'envoie jamais et retombe donc exactement sur les mêmes
  //   3 champs requis qu'avant — contrat inchangé octet pour octet pour elles.
  const quickCallback = b.quickCallback === true;

  const city = cleanStr(b.city, 100);
  if (!quickCallback && city.length < 2) errors.city = 'Ville / commune requise';

  const roofType = cleanStr(b.roofType, 20);
  if (!quickCallback && !ROOF_TYPES.some((r) => r.id === roofType)) errors.roofType = 'Type de toiture requis';

  // — QX : la tranche de facture reste REQUISE en résidentiel et dans les
  //   modes C&I (industriel/commercial, alias hérité professionnel — WJ121)
  //   mais devient FACULTATIVE en mode agricole (un projet pompage se
  //   dimensionne sur HMT × débit, pas sur une facture d'électricité — on ne
  //   force jamais une tranche fabriquée). Une tranche fournie ET valide est
  //   conservée ; malformée, elle est écartée comme tout champ facultatif.
  const mode = cleanEnum(b.mode, LEAD_MODES);
  const billRangeOptional = quickCallback || mode === 'agricole';
  const billRange = cleanStr(b.billRange, 20);
  if (!billRangeOptional && !isBillRangeId(billRange)) errors.billRange = 'Tranche de facture requise';

  if (b.consent !== true) errors.consent = 'Le consentement est requis pour être recontacté';

  if (Object.keys(errors).length > 0) return { ok: false, errors };

  const utm: Partial<Record<UtmKey, string>> = {};
  for (const k of UTM_KEYS) {
    const v = cleanStr(b[k], 300);
    if (v) utm[k] = v;
  }
  const fbclid = cleanStr(b.fbclid, 500) || null;

  return {
    ok: true,
    lead: {
      fullName,
      phoneE164: phone.e164!,
      // WJ64 — additif : présent uniquement pour un E.164 étranger (jamais
      // pour un numéro marocain — la clé n'existe simplement pas alors, comme
      // pour tout champ facultatif WJ30/WJ31 ci-dessous).
      ...(phone.phoneIsForeign ? { phoneIsForeign: true as const } : {}),
      whatsappOptIn: b.whatsappOptIn === true,
      // WJ97 — honnête : sur le chemin rappel rapide, ces trois champs restent
      // ABSENTS (jamais une valeur fabriquée) plutôt que forcés à une chaîne
      // vide/enum arbitraire. QX — en mode agricole, billRange n'est inclus
      // que s'il est présent ET valide (facultatif, jamais fabriqué).
      ...(quickCallback
        ? {}
        : {
            city,
            roofType: roofType as RoofTypeId,
            ...(isBillRangeId(billRange) ? { billRange: billRange as BillRangeId } : {}),
          }),
      ...(quickCallback ? { quickCallback: true as const } : {}),
      consent: true,
      fbclid,
      utm,
      // WJ30 — le webhook reçoit désormais TOUT ce que la capture a collecté
      // (facture exacte, GPS, contour, mode, raccordement, e-mail, langue…) :
      // champs facultatifs, validés un à un, écartés si malformés, jamais bloquants.
      ...validateOptionalFields(b),
    },
  };
}

/**
 * Bande kWc + ROI : proxy vers SIMULATOR_API_URL si configurée (timeout 5 s),
 * sinon estimation locale. Le navigateur n'appelle JAMAIS l'API directement.
 */
export async function runSimulation(
  lead: ValidatedLead,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<EstimateBand> {
  // WJ97 — un rappel rapide n'a pas de `billRange` : aucune fourchette kWc/ROI
  // à estimer (on ne fabrique jamais un chiffre sans facture connue) — bande
  // vide, honnête, jamais un devis local basé sur une hypothèse.
  if (!lead.billRange) {
    return { kwcMin: 0, kwcMax: 0, kwcLabel: '', paybackLabel: '', source: 'local' };
  }
  const fallback = localEstimateBand(lead.billRange);
  const url = env.SIMULATOR_API_URL?.trim();
  if (!url) return fallback;
  try {
    const res = await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ billRange: lead.billRange, roofType: lead.roofType, city: lead.city }),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return fallback;
    const data = (await res.json()) as Partial<EstimateBand>;
    if (typeof data.kwcLabel !== 'string' || typeof data.paybackLabel !== 'string') return fallback;
    return {
      kwcMin: typeof data.kwcMin === 'number' ? data.kwcMin : fallback.kwcMin,
      kwcMax: typeof data.kwcMax === 'number' ? data.kwcMax : fallback.kwcMax,
      kwcLabel: data.kwcLabel,
      paybackLabel: data.paybackLabel,
      source: 'simulator',
    };
  } catch {
    return fallback;
  }
}

export interface LeadRecord extends ValidatedLead {
  consentTimestamp: string; // ISO 8601 — horodatage serveur du consentement
  qualified: boolean; // false => ne doit jamais atteindre le CRM
  band: EstimateBand;
  page: string | null;
  submittedAt: string;
}

export function buildLeadRecord(
  lead: ValidatedLead,
  band: EstimateBand,
  now: Date,
  page: string | null = null,
): LeadRecord {
  const iso = now.toISOString();
  return {
    ...lead,
    consentTimestamp: iso,
    submittedAt: iso,
    // WJ97 — un rappel rapide n'a pas de `billRange` connu (aucun seuil de
    // facture à appliquer) : un visiteur qui demande EXPLICITEMENT à être
    // rappelé par téléphone est par nature un lead qualifié, jamais filtré
    // sous un seuil qu'on n'a même pas mesuré.
    // QX — un lead AGRICOLE (pompage) est TOUJOURS qualifié : le projet se
    // dimensionne sur HMT × débit (haute valeur), jamais gaté sur une facture
    // d'électricité qu'il n'a parfois même pas.
    qualified:
      lead.quickCallback === true || lead.mode === 'agricole'
        ? true
        : qualifiesForCrm(lead.billRange!),
    band,
    page,
  };
}

/**
 * WJ52 — référence client courte, générée CÔTÉ NAVIGATEUR juste avant l'envoi
 * (aucun appel serveur, aucune garantie d'unicité globale — c'est un artefact
 * pour combler le vide post-soumission, pas une clé d'unicité). Format
 * `TQ-XXXX` (4 caractères alphanumériques majuscules, alphabet sans 0/O/1/I
 * pour éviter toute confusion à l'oral/à l'écrit sur WhatsApp). Le préfixe
 * `TQ-` (Taqinor) + le format sont bornés par le regex de validation côté
 * `validateOptionalFields` ci-dessus (`^[A-Z0-9-]{4,24}$`).
 */
const CLIENT_REF_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
export function buildClientRef(rand: () => number = Math.random): string {
  let code = '';
  for (let i = 0; i < 4; i++) {
    code += CLIENT_REF_ALPHABET[Math.floor(rand() * CLIENT_REF_ALPHABET.length)];
  }
  return `TQ-${code}`;
}

/**
 * WJ66 — jeton d'idempotence, généré CÔTÉ NAVIGATEUR une seule fois par session
 * de saisie (comme `clientRef`, PAS un identifiant serveur). But : donner au
 * CRM un signal de DÉDOUBLONNAGE quand une même soumission est renvoyée (retry
 * réseau, double-clic, bouton « précédent » puis re-soumission) — le CRM-side
 * dedupe reste un suivi PLAN2 (hors périmètre ici), ce jeton n'est qu'un champ
 * additif transmis tel quel. Format alphanumérique 32 caractères (assez
 * d'entropie pour une clé de dédup best-effort, jamais une garantie
 * d'unicité globale) — borné par le regex de validation côté
 * `validateOptionalFields` (`^[A-Za-z0-9_-]{8,64}$`).
 */
const IDEMPOTENCY_KEY_ALPHABET = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
export function buildIdempotencyKey(rand: () => number = Math.random): string {
  let key = '';
  for (let i = 0; i < 32; i++) {
    key += IDEMPOTENCY_KEY_ALPHABET[Math.floor(rand() * IDEMPOTENCY_KEY_ALPHABET.length)];
  }
  return key;
}

/**
 * Identifiant court, NON réversible, dérivé du téléphone E.164 — pour corréler
 * deux lignes de log d'un même lead SANS jamais journaliser le numéro. FNV-1a
 * 32 bits (suffisant pour une corrélation de logs, pas pour de la sécurité) ;
 * pur, synchrone, aucune dépendance, fonctionne hors Workers (tests).
 */
export function leadLogId(phoneE164: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < phoneE164.length; i++) {
    h ^= phoneE164.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

/**
 * Vue d'un lead SÛRE pour les logs (ERR32) : aucune PII (nom, téléphone, ville,
 * e-mail, consentement) ne doit atterrir dans les logs Cloudflare. On ne
 * journalise que des diagnostics non identifiants — un id corrélable haché, des
 * indicateurs/longueurs, et des champs de campagne déjà publics (UTM/fbclid
 * sont des paramètres d'URL, pas de la PII). Le payload PII complet n'est
 * JAMAIS sérialisé pour les logs.
 */
export function redactLeadForLog(record: LeadRecord): Record<string, unknown> {
  return {
    id: leadLogId(record.phoneE164),
    qualified: record.qualified,
    billRange: record.billRange,
    roofType: record.roofType,
    whatsappOptIn: record.whatsappOptIn,
    hasName: record.fullName.length > 0,
    // WJ97 — `city` est absent sur le chemin rappel rapide (jamais un `.length`
    // sur `undefined`).
    hasCity: (record.city?.length ?? 0) > 0,
    bandSource: record.band.source,
    kwcLabel: record.band.kwcLabel,
    fbclid: record.fbclid ? 'present' : 'absent',
    utmKeys: Object.keys(record.utm).sort(),
    submittedAt: record.submittedAt,
    page: record.page,
    enrichment: 'enrichment' in record ? 'present' : 'absent',
  };
}

/**
 * WJ66 — VISIBILITÉ DE PANNE DE LIVRAISON. `forwardLead` tolère déjà l'absence
 * de configuration et les pannes réseau EN SILENCE (jamais levé, jamais
 * bloquant pour le visiteur) — mais un webhook CRM en panne prolongée ne
 * remontait nulle part : chaque visiteur voyait quand même « enregistré »
 * pendant que ses leads qualifiés n'atteignaient jamais le CRM, potentiellement
 * pendant des jours, sans qu'aucune alerte ne se déclenche.
 *
 * Compteur EN MÉMOIRE (même idiome que `rateLimit.ts` : Map au niveau du
 * module, best-effort, borné à l'isolat Worker courant — pas un quota/état
 * global durable, cf. limitation documentée dans rateLimit.ts). On ne compte
 * QUE les échecs de livraison d'un lead QUALIFIÉ avec un webhook CONFIGURÉ
 * (`webhook-status-*` / `webhook-error-*`) : jamais `below-threshold` ni
 * `no-webhook-configured`, qui sont des états normaux, pas des pannes.
 * Un succès réinitialise le compteur (la panne n'est plus active).
 */
const FORWARD_LEAD_ALERT_THRESHOLD = 3;
let consecutiveForwardFailures = 0;

/** Réinitialise le compteur de pannes (tests uniquement). */
export function resetForwardLeadFailureStreak(): void {
  consecutiveForwardFailures = 0;
}

/**
 * Enregistre le résultat d'un `forwardLead` et indique si le seuil d'alerte
 * est atteint (>= FORWARD_LEAD_ALERT_THRESHOLD échecs consécutifs). Pur
 * vis-à-vis de l'appelant : ne lève jamais, ne bloque jamais — un simple
 * indicateur pour décider de journaliser une ligne d'ALERTE plus visible.
 */
export function trackForwardLeadOutcome(delivered: boolean, reason?: string): { shouldAlert: boolean; streak: number } {
  if (delivered) {
    consecutiveForwardFailures = 0;
    return { shouldAlert: false, streak: 0 };
  }
  // Les états normaux (pas de panne) ne comptent jamais comme un échec de livraison.
  if (reason === 'below-threshold' || reason === 'no-webhook-configured') {
    return { shouldAlert: false, streak: consecutiveForwardFailures };
  }
  consecutiveForwardFailures += 1;
  return {
    shouldAlert: consecutiveForwardFailures >= FORWARD_LEAD_ALERT_THRESHOLD,
    streak: consecutiveForwardFailures,
  };
}

/**
 * Transfert CRM (LEAD_WEBHOOK_URL). Tolère l'absence de configuration et les
 * pannes : ne lève jamais, retourne l'état de livraison pour le log.
 */
export async function forwardLead(
  record: LeadRecord,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<{ delivered: boolean; reason?: string }> {
  if (!record.qualified) return { delivered: false, reason: 'below-threshold' };
  const url = env.LEAD_WEBHOOK_URL?.trim();
  if (!url) return { delivered: false, reason: 'no-webhook-configured' };
  try {
    // Secret statique attendu par le récepteur taqinor-os
    // (apps/crm/webhooks.py, en-tête X-Webhook-Secret). Sans secret
    // configuré, le récepteur refuse tout : les deux vont ensemble.
    //
    // ERR110 — RISQUE DE REJEU (documenté, PAS corrigé ici). Le protocole de
    // fil est un secret partagé STATIQUE (x-webhook-secret), sans signature
    // HMAC, ni horodatage signé, ni nonce. Un attaquant qui capture une requête
    // valide (TLS terminé chez un proxy, fuite de logs côté récepteur, etc.)
    // peut la REJOUER tant que le secret ne tourne pas. Durcir cela (HMAC sur
    // corps+timestamp, fenêtre anti-rejeu, nonce) EXIGE une modification
    // COORDONNÉE du récepteur (apps/crm/webhooks.py) : c'est un suivi côté
    // récepteur, HORS PÉRIMÈTRE de ce correctif côté site. On NE CHANGE PAS le
    // contrat de fil ici.
    //
    // Atténuation additive non cassante : on joint un en-tête x-webhook-timestamp
    // (ISO 8601) que le récepteur actuel IGNORE sans danger. Quand le récepteur
    // saura le vérifier (suivi coordonné), il pourra rejeter les requêtes trop
    // anciennes sans rien casser pour les clients existants.
    const headers: Record<string, string> = {
      'content-type': 'application/json',
      'x-webhook-timestamp': new Date().toISOString(),
    };
    const secret = env.LEAD_WEBHOOK_SECRET?.trim();
    if (secret) headers['x-webhook-secret'] = secret;
    const res = await fetchFn(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(record),
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) return { delivered: false, reason: `webhook-status-${res.status}` };
    return { delivered: true };
  } catch (e) {
    return { delivered: false, reason: `webhook-error-${e instanceof Error ? e.name : 'unknown'}` };
  }
}

/**
 * SHA-256 hex (minuscule) via Web Crypto — aucune dépendance, disponible dans
 * les Workers ET sous Node ≥ 18 (globalThis.crypto.subtle), donc testable.
 */
async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Hash SHA-256 du téléphone selon la spec Meta « Advanced Matching » : chiffres
 * uniquement, indicatif pays inclus, sans « + », espaces ni symboles. Notre
 * `phoneE164` est déjà au format +212XXXXXXXXX → on retire tout non-chiffre.
 */
export async function hashPhoneForCapi(phoneE164: string): Promise<string> {
  const digits = phoneE164.replace(/\D+/g, '');
  return sha256Hex(digits);
}

/**
 * Hash SHA-256 de la ville selon la spec Meta : minuscules, sans espace ni
 * ponctuation, trim (a–z et lettres accentuées conservées : Meta normalise
 * surtout la casse/les espaces ; on retire espaces et ponctuation latine).
 */
export async function hashCityForCapi(city: string): Promise<string> {
  const normalized = city
    .trim()
    .toLowerCase()
    .replace(/[\s\p{P}]+/gu, '');
  return sha256Hex(normalized);
}

/**
 * WJ92 — Hash SHA-256 de l'e-mail selon la spec Meta « Advanced Matching » :
 * minuscules, trim, aucune autre normalisation (Meta ne dé-ponctue PAS
 * l'e-mail comme la ville — seuls casse/espaces varient légitimement).
 */
export async function hashEmailForCapi(email: string): Promise<string> {
  const normalized = email.trim().toLowerCase();
  return sha256Hex(normalized);
}

/**
 * Meta Conversions API (CAPI_URL) — fire-and-forget. Le service vit dans
 * taqinor-os et peut ne pas être déployé : l'absence est tolérée en silence.
 * Uniquement pour les leads qualifiés (signal publicitaire propre).
 *
 * ERR111 — la PII de correspondance avancée (téléphone, ville) est HACHÉE en
 * SHA-256 AVANT de quitter apps/web. Le relais CAPI vit dans taqinor-os, n'est
 * pas inspectable depuis ce dépôt et « peut ne pas être déployé » : on ne peut
 * donc pas SUPPOSER qu'il hache. La spec Meta EXIGE des paramètres clients
 * hachés (SHA-256, normalisés) ; on hache donc à la source. Les champs sortent
 * sous `ph`/`ct` (noms de la spec Meta « user_data », déjà hachés) ; on n'envoie
 * PLUS jamais `phoneE164`/`city` en clair vers le relais.
 *
 * WJ92 — MATCH QUALITY : deux leviers additifs, aucun n'est bloquant ni ne
 * change le contrat existant :
 *  - `em` (e-mail haché SHA-256, spec Meta) — présent SEULEMENT quand le lead
 *    a capturé un e-mail (WJ30, facultatif) ; absent sinon, comme aujourd'hui.
 *  - `event_id` — identifiant de DÉDUPLICATION par soumission. Priorité au
 *    jeton généré côté navigateur (`record.eventId`, WJ92 côté lead.ts/mon-toit)
 *    pour permettre une dédup pixel-navigateur ↔ serveur ; à défaut, un id
 *    dérivé STABLE et NON réversible du même lead (leadLogId + submittedAt)
 *    garantit qu'un `event_id` est TOUJOURS présent même sans jeton client.
 */
export async function fireCapi(
  record: LeadRecord,
  env: LeadEnv,
  fetchFn: typeof fetch = fetch,
): Promise<{ sent: boolean }> {
  if (!record.qualified) return { sent: false };
  const url = env.CAPI_URL?.trim();
  if (!url) return { sent: false };
  try {
    const [ph, ct, em] = await Promise.all([
      hashPhoneForCapi(record.phoneE164),
      // WJ97 — `city` est absent sur le chemin rappel rapide : pas de hash de
      // correspondance ville dans ce cas (jamais une ville fabriquée).
      record.city ? hashCityForCapi(record.city) : Promise.resolve(undefined),
      record.email ? hashEmailForCapi(record.email) : Promise.resolve(undefined),
    ]);
    const eventId = record.eventId || `${leadLogId(record.phoneE164)}-${record.submittedAt}`;
    await fetchFn(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        event: 'Lead',
        event_id: eventId,
        fbclid: record.fbclid,
        utm: record.utm,
        // PII hachée SHA-256 (jamais en clair) — noms `ph`/`ct`/`em` de la spec Meta.
        ph,
        ...(ct ? { ct } : {}),
        ...(em ? { em } : {}),
        billRange: record.billRange,
        timestamp: record.submittedAt,
        page: record.page,
      }),
      signal: AbortSignal.timeout(5000),
    });
    return { sent: true };
  } catch {
    return { sent: false };
  }
}
