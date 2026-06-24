/**
 * W116 / W117 — Logique PURE de la proposition client en ligne.
 *
 * La page /proposition/[token] et le proxy /api/proposition-accept appellent
 * UNIQUEMENT des fonctions de ce module pour tout ce qui n'est pas du DOM :
 * formatage monétaire, choix d'option, mise en forme de la requête d'acceptation,
 * décision « quel état afficher ». Tout est testé sous vitest (aucun DOM, aucun
 * réseau) — les fonctions sont volontairement déterministes et sans effet de bord.
 *
 * Le navigateur du client n'appelle JAMAIS le backend en direct : la page lit la
 * proposition côté serveur (frontmatter Astro), et la signature passe par le
 * proxy same-origin. Le backend ne renvoie jamais de prix d'achat / marge — on ne
 * lit donc que les champs publics du contrat vérifié.
 */

/** Une ligne d'équipement telle que renvoyée par le backend (champs publics). */
export interface ProposalItem {
  designation: string;
  quantite: number;
  prix_unit_ht: number;
  prix_unit_ttc: number;
  remise: number;
  marque: string;
  taux_tva: number;
}

/** Un palier de TVA agrégé (taux → montant). */
export interface TvaParTaux {
  taux: number;
  base?: number;
  montant: number;
}

/** Le bloc de totaux d'une option (sans ou avec batterie). */
export interface ProposalTotaux {
  ht_brut: number;
  remise: number;
  ht_net: number;
  tva: number;
  tva_par_taux?: TvaParTaux[];
  ttc: number;
}

/** Le devis complet (sous-objet `quote` du contrat). */
export interface ProposalQuote {
  ref: string;
  date: string;
  client_name: string;
  client_addr?: string;
  client_phone?: string;
  inst_type?: string;
  puissance_kwc?: number;
  nb_panneaux?: number;
  watt_par_panneau?: number;
  prod_kwh?: number;
  total_sans?: number;
  total_avec?: number;
  eco_s_ann?: number;
  eco_a_ann?: number;
  /** Économie cumulée sur la durée (champ backend `eco_a_cumul`, MAD). */
  eco_a_cumul?: number;
  roi_s?: number | string;
  roi_a?: number | string;
  /** Date limite de validité (peut aussi voyager au niveau racine du contrat). */
  date_validite?: string | null;
  scenario?: string;
  recommended?: OptionKey | string;
  sans_items?: ProposalItem[];
  avec_items?: ProposalItem[];
  totaux_sans?: ProposalTotaux;
  totaux_avec?: ProposalTotaux;
  display_total?: number;
  nb_options?: number;
  roof_image_key?: string;
  etude?: Record<string, unknown>;
}

/** Totaux d'options agrégés au niveau racine du contrat. */
export interface OptionTotals {
  sans_batterie: number;
  avec_batterie: number;
  display_total: number;
  nb_options: number;
}

/** Réponse complète de GET /api/django/ventes/proposal/<token>/. */
export interface ProposalResponse {
  reference: string;
  date: string;
  client_name: string;
  statut: string;
  quote: ProposalQuote;
  roof_image_url: string | null;
  /**
   * Production solaire estimée, kWh/mois (12 valeurs, index 0 = janvier). Peut
   * être absent ou `[]` — le graphe se masque alors gracieusement (P2).
   */
  monthly_production?: number[];
  /**
   * Consommation électrique du client, kWh/mois (12 valeurs). Peut être absent
   * ou `[]` — la comparaison se réduit alors à la production seule (P2).
   */
  monthly_consumption?: number[];
  option_totals: OptionTotals;
  accepted: boolean;
  accepte_par_nom?: string | null;
  date_acceptation?: string | null;
  /**
   * Date limite de validité du devis (échéance d'offre). Le backend PEUT
   * l'exposer (champ `Devis.date_validite`, format ISO `YYYY-MM-DD` ou FR
   * `JJ/MM/AAAA`). Absent → la page affiche une fenêtre de validité « par
   * défaut » clairement libellée (jamais un compte-à-rebours qui se réinitialise).
   * Le champ peut aussi voyager dans `quote.date_validite`.
   */
  date_validite?: string | null;
}

export type OptionKey = 'sans_batterie' | 'avec_batterie';

/**
 * Format monétaire marocain : `12 500 MAD` (espace fine de milliers, devise
 * après le nombre). Identique à lib/format.formatMAD ; dupliqué ici pour garder
 * ce module autonome et sûr à importer côté navigateur sans dépendances.
 */
export function formatMAD(amount: number | null | undefined): string {
  const n = typeof amount === 'number' && Number.isFinite(amount) ? amount : 0;
  const rounded = Math.round(n);
  const sign = rounded < 0 ? '-' : '';
  const digits = Math.abs(rounded).toString();
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${sign}${grouped} MAD`;
}

/**
 * Format nombre marocain SANS devise (ex. production en kWh, panneaux) :
 * `8 640` — séparateur de milliers espace. `decimals` arrondit (défaut 0).
 */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  const n = typeof value === 'number' && Number.isFinite(value) ? value : 0;
  const factor = 10 ** decimals;
  const rounded = Math.round(n * factor) / factor;
  const sign = rounded < 0 ? '-' : '';
  const abs = Math.abs(rounded);
  const intPart = Math.trunc(abs).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  if (decimals <= 0) return `${sign}${intPart}`;
  const frac = (abs - Math.trunc(abs)).toFixed(decimals).slice(2).replace(/0+$/, '');
  return frac ? `${sign}${intPart},${frac}` : `${sign}${intPart}`;
}

/** Pourcentage lisible : `30 %` (espace avant le signe, virgule décimale). */
export function formatPercent(value: number | null | undefined, decimals = 0): string {
  return `${formatNumber(value, decimals)} %`;
}

/**
 * Affiche une durée de retour sur investissement. Le backend peut renvoyer un
 * nombre (années) ou une chaîne déjà formatée — on respecte les deux.
 */
export function formatPayback(roi: number | string | null | undefined): string | null {
  if (roi === null || roi === undefined || roi === '') return null;
  if (typeof roi === 'number') {
    if (!Number.isFinite(roi) || roi <= 0) return null;
    return `${formatNumber(roi, 1)} ans`;
  }
  const trimmed = String(roi).trim();
  return trimmed.length ? trimmed : null;
}

/**
 * Nombre d'options réel : on fait confiance à `option_totals.nb_options` quand il
 * est présent (1 ou 2), sinon on retombe sur la présence des deux blocs de totaux.
 */
export function optionCount(p: ProposalResponse): number {
  const n = p.option_totals?.nb_options;
  if (n === 1 || n === 2) return n;
  const hasSans = !!p.quote?.totaux_sans;
  const hasAvec = !!p.quote?.totaux_avec;
  if (hasSans && hasAvec) return 2;
  return 1;
}

/** Vrai si la proposition propose deux options (sans batterie vs avec batterie). */
export function hasTwoOptions(p: ProposalResponse): boolean {
  return optionCount(p) === 2;
}

/** L'option recommandée, normalisée. Défaut : `avec_batterie` si présente, sinon `sans_batterie`. */
export function recommendedOption(p: ProposalResponse): OptionKey {
  const r = p.quote?.recommended;
  if (r === 'sans_batterie' || r === 'avec_batterie') return r;
  return p.quote?.totaux_avec ? 'avec_batterie' : 'sans_batterie';
}

/** TTC d'une option donnée (lecture défensive). */
export function optionTtc(p: ProposalResponse, opt: OptionKey): number {
  const t = opt === 'avec_batterie' ? p.quote?.totaux_avec : p.quote?.totaux_sans;
  if (t && Number.isFinite(t.ttc)) return t.ttc;
  return opt === 'avec_batterie' ? p.option_totals?.avec_batterie ?? 0 : p.option_totals?.sans_batterie ?? 0;
}

/** Étiquette FR courte d'une option. */
export function optionLabel(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie';
}

/** Lignes d'équipement d'une option (toujours un tableau). */
export function optionItems(p: ProposalResponse, opt: OptionKey): ProposalItem[] {
  const items = opt === 'avec_batterie' ? p.quote?.avec_items : p.quote?.sans_items;
  return Array.isArray(items) ? items : [];
}

/** Totaux d'une option (peut être absent pour une option non proposée). */
export function optionTotaux(p: ProposalResponse, opt: OptionKey): ProposalTotaux | null {
  const t = opt === 'avec_batterie' ? p.quote?.totaux_avec : p.quote?.totaux_sans;
  return t ?? null;
}

/**
 * L'option « par défaut » à pré-sélectionner dans le formulaire de signature :
 * la recommandée si deux options, sinon la seule disponible.
 */
export function defaultSelectedOption(p: ProposalResponse): OptionKey {
  if (hasTwoOptions(p)) return recommendedOption(p);
  return p.quote?.totaux_avec && !p.quote?.totaux_sans ? 'avec_batterie' : 'sans_batterie';
}

/** Vrai si la proposition est déjà acceptée (signée) — affiche l'état confirmé. */
export function isAccepted(p: ProposalResponse): boolean {
  return p.accepted === true || p.statut === 'accepte';
}

// ── Formulaire de signature : validation + mise en forme de la requête ───────

export interface SignFormState {
  nom: string;
  option: OptionKey | null;
}

export interface SignValidation {
  valid: boolean;
  /** Message FR à afficher quand invalide (null si valide). */
  error: string | null;
}

/**
 * Validation du formulaire de signature côté client (le backend revalide).
 * - nom non vide,
 * - option choisie OBLIGATOIRE quand il y a deux options.
 */
export function validateSign(form: SignFormState, twoOptions: boolean): SignValidation {
  const nom = (form.nom ?? '').trim();
  if (!nom) return { valid: false, error: 'Veuillez saisir votre nom complet.' };
  if (twoOptions && form.option !== 'sans_batterie' && form.option !== 'avec_batterie') {
    return { valid: false, error: 'Veuillez choisir une option avant de signer.' };
  }
  return { valid: true, error: null };
}

export interface AcceptRequestBody {
  nom: string;
  option?: OptionKey;
}

/**
 * Met en forme le corps envoyé au proxy /api/proposition-accept (qui le relaie
 * tel quel au backend). `option` n'est inclus que lorsqu'il y a deux options —
 * conforme au contrat (option REQUISE si nb_options===2, ignorée sinon).
 */
export function buildAcceptBody(form: SignFormState, twoOptions: boolean): AcceptRequestBody {
  const body: AcceptRequestBody = { nom: (form.nom ?? '').trim() };
  if (twoOptions && (form.option === 'sans_batterie' || form.option === 'avec_batterie')) {
    body.option = form.option;
  }
  return body;
}

/**
 * Construit l'URL backend de l'endpoint d'acceptation à partir d'une base API et
 * d'un token. Utilisé côté serveur par le proxy. Encode le token (path segment).
 */
export function acceptEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/accept/`;
}

/** Construit l'URL backend de lecture de la proposition (frontmatter Astro). */
export function proposalEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/`;
}

/**
 * URL publique du DEVIS PDF premium (même token) : le bouton « Télécharger le
 * devis » pointe directement vers le backend (nouvel onglet). Le lien est public
 * et tokenisé — pas d'auth, pas de prix d'achat (le backend ne les rend jamais).
 */
export function proposalPdfEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/pdf/`;
}

/**
 * Lecture défensive d'un tableau mensuel (production/consommation) : renvoie
 * exactement 12 valeurs finies ≥ 0 si l'entrée est un tableau de 12 éléments avec
 * au moins une valeur > 0, sinon `null` (tableau vide, taille ≠ 12, ou tout zéro).
 * Le graphe (proposalChart) refait ce nettoyage, mais l'exposer ici permet à la
 * page de décider d'AFFICHER ou non le bloc graphe sans dupliquer la règle.
 */
export function monthlySeries(arr: number[] | undefined | null): number[] | null {
  if (!Array.isArray(arr) || arr.length !== 12) return null;
  let any = false;
  const out = arr.map((v) => {
    const n = typeof v === 'number' && Number.isFinite(v) && v > 0 ? v : 0;
    if (n > 0) any = true;
    return n;
  });
  return any ? out : null;
}

/**
 * Vrai si la proposition porte AU MOINS une série de production exploitable —
 * condition d'affichage du bloc graphe (P2). Sans production, on n'affiche rien
 * (une conso « solo » ne raconte aucune histoire sur cette page).
 */
export function hasProductionSeries(p: ProposalResponse): boolean {
  return monthlySeries(p.monthly_production) !== null;
}

/**
 * Normalise une réponse d'acceptation backend (succès OU erreur) en un objet
 * stable que le client peut afficher. On reflète le `detail` backend tel quel
 * pour les 400/409/404 ; un succès porte la référence + le nom du signataire.
 */
export interface AcceptResult {
  ok: boolean;
  status: number;
  detail: string;
  reference?: string;
  accepte_par_nom?: string;
}

export function normalizeAcceptResponse(status: number, payload: unknown): AcceptResult {
  const body = (payload ?? {}) as Record<string, unknown>;
  const detail = typeof body.detail === 'string' && body.detail.trim() ? body.detail.trim() : '';
  if (status >= 200 && status < 300) {
    return {
      ok: true,
      status,
      detail: detail || 'Devis accepté.',
      reference: typeof body.reference === 'string' ? body.reference : undefined,
      accepte_par_nom: typeof body.accepte_par_nom === 'string' ? body.accepte_par_nom : undefined,
    };
  }
  // Messages FR de repli par code, si le backend n'a pas fourni de `detail`.
  const fallback =
    status === 404
      ? 'Ce lien de proposition est introuvable ou a expiré.'
      : status === 409
        ? 'Ce devis a déjà été traité.'
        : status === 400
          ? 'La demande est invalide. Vérifiez votre saisie.'
          : 'Une erreur est survenue. Veuillez réessayer.';
  return { ok: false, status, detail: detail || fallback };
}

// ════════════════════════════════════════════════════════════════════════════
// WJ9–WJ16 — élévation « best-in-world » de la proposition client.
//
// DISCIPLINE « ZÉRO CHIFFRE INVENTÉ » : chaque fonction ci-dessous ne produit un
// nombre que (a) lu directement du payload backend, ou (b) calculé par une règle
// documentée à partir de valeurs PRÉSENTES dans le payload, ou (c) une fourchette
// CLAIREMENT libellée « indicative / à confirmer ». Quand aucune source honnête
// n'existe, on renvoie `null` et la page affiche un repli libellé — jamais une
// valeur fabriquée. Économies en autoconsommation (loi 82-21) : aucune promesse
// de revente/injection du surplus.
// ════════════════════════════════════════════════════════════════════════════

// ── Constantes physiques / financières documentées ──────────────────────────

/**
 * WJ9 — Horizon d'analyse des économies cumulées : 25 ans. C'est la garantie de
 * performance standard d'un panneau photovoltaïque (≈ 25 ans à ~80–85 % de
 * puissance) — durée de vie économique conventionnelle de l'installation, pas un
 * chiffre marketing.
 */
export const SAVINGS_HORIZON_YEARS = 25;

/**
 * WJ9 — Dérive annuelle de la facture d'électricité (« coût de ne rien faire »).
 * Hypothèse PRUDENTE et libellée : 0 % par défaut (économies à tarif constant).
 * Le calcul de cumul reste honnête même sans inflation tarifaire. Toute hausse
 * réelle ne ferait qu'augmenter l'économie — on ne la promet donc pas.
 */
export const BILL_INFLATION_RATE = 0;

/**
 * WJ14 — Facteur d'émission du réseau électrique marocain (ONEE), en kg de CO₂
 * évité par kWh solaire autoconsommé. Le mix marocain reste fortement carboné
 * (charbon majoritaire) ; 0,81 kg CO₂/kWh est l'ordre de grandeur publié pour le
 * facteur d'émission moyen du réseau. Constante AFFICHÉE à l'écran.
 */
export const CO2_KG_PER_KWH = 0.81;

/**
 * WJ14 — Équivalent « arbres » : un arbre mûr absorbe ≈ 22 kg de CO₂ par an
 * (ordre de grandeur communément retenu). Constante AFFICHÉE à l'écran.
 */
export const CO2_KG_PER_TREE_YEAR = 22;

/**
 * WJ10 — Taux annuel INDICATIF d'un éco-prêt vert au Maroc (TAEG approximatif).
 * Aucune offre n'est contractuelle ici : la mensualité affichée est une simple
 * illustration « à confirmer » auprès de la banque. Fourchette ~7–9 %.
 */
export const GREEN_LOAN_RATE_LOW = 0.07;
export const GREEN_LOAN_RATE_HIGH = 0.09;

/** WJ10 — Durée INDICATIVE d'un éco-prêt vert (mois). 7 ans. */
export const GREEN_LOAN_MONTHS = 84;

// ── WJ15 · Fenêtre de validité honnête ───────────────────────────────────────

export interface ValidityWindow {
  /** Date d'échéance affichable (libellé FR « JJ mois AAAA »), ou null. */
  label: string | null;
  /** Vrai quand la date vient RÉELLEMENT du backend (sinon repli libellé). */
  fromBackend: boolean;
  /** Vrai si l'échéance est déjà passée (offre expirée). */
  expired: boolean;
}

const MONTHS_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/**
 * Parse une date backend en `Date` UTC midi (robuste aux fuseaux). Accepte ISO
 * `YYYY-MM-DD` et FR `JJ/MM/AAAA`. Renvoie `null` si non parsable.
 */
export function parseBackendDate(raw: string | null | undefined): Date | null {
  if (!raw || typeof raw !== 'string') return null;
  const s = raw.trim();
  let y = 0, m = 0, d = 0;
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  const fr = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(s);
  if (iso) {
    y = +iso[1]; m = +iso[2]; d = +iso[3];
  } else if (fr) {
    d = +fr[1]; m = +fr[2]; y = +fr[3];
  } else {
    return null;
  }
  if (m < 1 || m > 12 || d < 1 || d > 31) return null;
  const dt = new Date(Date.UTC(y, m - 1, d, 12, 0, 0));
  if (Number.isNaN(dt.getTime())) return null;
  return dt;
}

/** Formate une `Date` en « 15 juillet 2026 » (FR). */
export function formatFrenchDate(dt: Date): string {
  return `${dt.getUTCDate()} ${MONTHS_FR[dt.getUTCMonth()]} ${dt.getUTCFullYear()}`;
}

/**
 * WJ15 — Résout la fenêtre de validité du devis SANS jamais inventer une date.
 *  - Si le backend fournit `date_validite` (racine ou `quote`), on l'affiche
 *    telle quelle (`fromBackend: true`), en signalant si elle est déjà passée.
 *  - Sinon, repli HONNÊTE : `label = null` + `fromBackend: false` → la page
 *    affiche une mention libellée (« sous réserve de validité ») et NON un
 *    compte-à-rebours. `now` est injectable pour les tests (déterminisme).
 */
export function resolveValidity(
  p: Pick<ProposalResponse, 'date_validite' | 'quote'>,
  now: Date = new Date(),
): ValidityWindow {
  const raw = p.date_validite ?? p.quote?.date_validite ?? null;
  const dt = parseBackendDate(raw);
  if (!dt) return { label: null, fromBackend: false, expired: false };
  const expired = dt.getTime() < now.getTime();
  return { label: formatFrenchDate(dt), fromBackend: true, expired };
}

// ── WJ9 · Argent dans le temps (cumul 25 ans + cadrage mensuel) ──────────────

export interface SavingsHeadline {
  /** Économie annuelle (MAD/an) — backend `eco_*_ann`. */
  annual: number | null;
  /** Économie cumulée sur l'horizon (MAD) — backend `eco_a_cumul` sinon calcul. */
  cumulative: number | null;
  /** Horizon retenu (ans). */
  years: number;
  /** Économie mensuelle équivalente (MAD/mois) ≈ annuel / 12. */
  monthly: number | null;
  /** Retour sur investissement (déjà formaté). */
  payback: string | null;
  /** Vrai si le cumul vient directement du backend (sinon calculé). */
  cumulativeFromBackend: boolean;
}

/**
 * WJ9 — Construit le bandeau « money over time » de l'option recommandée.
 *  - `annual` : économie annuelle backend.
 *  - `cumulative` : `eco_a_cumul` backend s'il existe ; sinon calculé à partir de
 *    l'annuel × horizon (avec dérive `BILL_INFLATION_RATE`, 0 % par défaut). On
 *    NE calcule jamais sans annuel présent.
 *  - `monthly` : annuel / 12 (simple cadrage de lecture, pas un nouveau chiffre).
 */
export function savingsHeadline(
  p: ProposalResponse,
  opt: OptionKey,
  years: number = SAVINGS_HORIZON_YEARS,
): SavingsHeadline {
  const annualRaw = opt === 'avec_batterie' ? p.quote?.eco_a_ann : p.quote?.eco_s_ann;
  const annual = typeof annualRaw === 'number' && Number.isFinite(annualRaw) && annualRaw > 0
    ? annualRaw : null;
  const paybackRaw = opt === 'avec_batterie' ? p.quote?.roi_a : p.quote?.roi_s;

  const backendCumul = p.quote?.eco_a_cumul;
  let cumulative: number | null = null;
  let cumulativeFromBackend = false;
  if (typeof backendCumul === 'number' && Number.isFinite(backendCumul) && backendCumul > 0) {
    cumulative = backendCumul;
    cumulativeFromBackend = true;
  } else if (annual !== null && years > 0) {
    // Série géométrique honnête : Σ annuel·(1+i)^k, k=0..years-1.
    const i = BILL_INFLATION_RATE;
    cumulative = i === 0
      ? annual * years
      : Math.round((annual * (Math.pow(1 + i, years) - 1)) / i);
  }

  return {
    annual,
    cumulative,
    years,
    monthly: annual !== null ? Math.round(annual / 12) : null,
    payback: formatPayback(paybackRaw),
    cumulativeFromBackend,
  };
}

// ── WJ14 · Impact environnemental humain (CO₂ ≈ arbres) ──────────────────────

export interface EnvironmentalImpact {
  /** kg de CO₂ évités par an (production × facteur réseau). */
  co2KgPerYear: number;
  /** Tonnes de CO₂ évitées par an (arrondi 1 décimale). */
  co2TonnesPerYear: number;
  /** Équivalent en arbres « plantés » (absorption annuelle). */
  trees: number;
  /** Constantes affichées pour la transparence. */
  kgPerKwh: number;
  kgPerTreeYear: number;
}

/**
 * WJ14 — Calcule l'impact environnemental À PARTIR de la production annuelle
 * backend (`prod_kwh`). Renvoie `null` si la production est absente/nulle (aucun
 * chiffre inventé). Les constantes sont retournées pour être affichées à côté.
 */
export function environmentalImpact(
  prodKwh: number | null | undefined,
  kgPerKwh: number = CO2_KG_PER_KWH,
  kgPerTreeYear: number = CO2_KG_PER_TREE_YEAR,
): EnvironmentalImpact | null {
  const prod = typeof prodKwh === 'number' && Number.isFinite(prodKwh) && prodKwh > 0 ? prodKwh : null;
  if (prod === null) return null;
  const co2KgPerYear = prod * kgPerKwh;
  return {
    co2KgPerYear: Math.round(co2KgPerYear),
    co2TonnesPerYear: Math.round((co2KgPerYear / 1000) * 10) / 10,
    trees: Math.round(co2KgPerYear / kgPerTreeYear),
    kgPerKwh,
    kgPerTreeYear,
  };
}

// ── WJ10 · Comparatif de financement (cash vs éco-prêt indicatif) ────────────

export interface FinancingComparison {
  /** Prix comptant TTC (backend). */
  cash: number;
  /** Mensualité indicative basse (taux bas), MAD/mois. */
  monthlyLow: number;
  /** Mensualité indicative haute (taux haut), MAD/mois. */
  monthlyHigh: number;
  /** Durée indicative (mois). */
  months: number;
  /**
   * Facture mensuelle actuelle estimée (backend `factures_mensuelles` moyenne),
   * pour l'accroche « mensualité < votre facture ». null si indisponible.
   */
  currentBillMonthly: number | null;
  /** Vrai si la mensualité basse est strictement < facture actuelle. */
  beatsBill: boolean;
}

/**
 * Mensualité d'un prêt amortissable (formule standard). `rate` est ANNUEL.
 * Renvoie un entier MAD. Taux 0 → simple division.
 */
export function loanMonthlyPayment(principal: number, annualRate: number, months: number): number {
  if (principal <= 0 || months <= 0) return 0;
  const r = annualRate / 12;
  if (r === 0) return Math.round(principal / months);
  const factor = (r * Math.pow(1 + r, months)) / (Math.pow(1 + r, months) - 1);
  return Math.round(principal * factor);
}

/**
 * WJ10 — Comparatif cash vs éco-prêt INDICATIF. Le prix comptant vient du
 * backend (TTC de l'option). Les mensualités sont une fourchette CLAIREMENT
 * indicative (taux/durée non contractuels) — la page les libelle « à confirmer ».
 * `currentBillMonthly` se déduit de `factures_mensuelles` backend (moyenne) si
 * présent, sinon null (la page masque alors l'accroche comparative).
 */
export function financingComparison(
  p: ProposalResponse,
  opt: OptionKey,
): FinancingComparison | null {
  const cash = optionTtc(p, opt);
  if (!Number.isFinite(cash) || cash <= 0) return null;
  const monthlyHigh = loanMonthlyPayment(cash, GREEN_LOAN_RATE_HIGH, GREEN_LOAN_MONTHS);
  const monthlyLow = loanMonthlyPayment(cash, GREEN_LOAN_RATE_LOW, GREEN_LOAN_MONTHS);

  const bills = p.quote?.factures_mensuelles;
  let currentBillMonthly: number | null = null;
  if (Array.isArray(bills) && bills.length > 0) {
    const valid = bills.filter((v) => typeof v === 'number' && Number.isFinite(v) && v > 0);
    if (valid.length > 0) {
      currentBillMonthly = Math.round(valid.reduce((a, b) => a + b, 0) / valid.length);
    }
  }

  return {
    cash,
    monthlyLow,
    monthlyHigh,
    months: GREEN_LOAN_MONTHS,
    currentBillMonthly,
    beatsBill: currentBillMonthly !== null && monthlyLow < currentBillMonthly,
  };
}

// ── WJ12 · Contact intégré (WhatsApp prérempli avec la réf devis) ────────────

/**
 * Numéro WhatsApp TAQINOR (format international sans « + », tel que requis par
 * wa.me). Valeur RÉELLE confirmée (= `WHATSAPP_LEADS` de lib/nap.ts) ; dupliquée
 * ici pour garder ce module autonome (importable côté navigateur sans dépendance).
 */
export const TAQINOR_WHATSAPP = '212661850410';

/**
 * WJ12 — Construit un deep-link wa.me prérempli citant la RÉFÉRENCE du devis.
 * `phone` peut surcharger le numéro par défaut. Le message est encodé URL.
 */
export function whatsappLink(reference: string, phone: string = TAQINOR_WHATSAPP): string {
  const digits = (phone || TAQINOR_WHATSAPP).replace(/[^\d]/g, '') || TAQINOR_WHATSAPP;
  const ref = (reference || '').trim();
  const msg = ref
    ? `Bonjour, j'ai une question sur ma proposition Taqinor (réf. ${ref}).`
    : 'Bonjour, j\'ai une question sur ma proposition Taqinor.';
  return `https://wa.me/${digits}?text=${encodeURIComponent(msg)}`;
}

// ── WJ11 · Payload d'acceptation enrichi (rétro-compatible) ──────────────────

export interface SignSignatureMeta {
  /** Image PNG de la signature manuscrite (data URL), ou chaîne vide. */
  signature_data_url?: string;
  /** Consentement explicite à la signature électronique. */
  consent_esign?: boolean;
  /** Horodatage côté client (ISO 8601) du moment de la signature. */
  signed_at_client?: string;
}

/**
 * WJ11 — Étend `buildAcceptBody` avec des champs OPTIONNELS que le backend peut
 * ignorer sans casser le contrat existant (`nom` + `option?` restent la base).
 * Aucun champ obligatoire n'est ajouté — un backend non mis à jour fonctionne
 * exactement comme avant.
 */
export function buildAcceptBodyRich(
  form: SignFormState,
  twoOptions: boolean,
  meta: SignSignatureMeta = {},
): AcceptRequestBody & SignSignatureMeta {
  const body: AcceptRequestBody & SignSignatureMeta = buildAcceptBody(form, twoOptions);
  if (typeof meta.signature_data_url === 'string' && meta.signature_data_url) {
    body.signature_data_url = meta.signature_data_url;
  }
  if (meta.consent_esign === true) body.consent_esign = true;
  if (typeof meta.signed_at_client === 'string' && meta.signed_at_client) {
    body.signed_at_client = meta.signed_at_client;
  }
  return body;
}
