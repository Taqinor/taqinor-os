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
  /** Factures mensuelles (MAD) du client si le backend les expose — sert
   *  uniquement à l'accroche « < votre facture actuelle » (WJ10). Optionnel :
   *  absent → l'accroche comparative est masquée, jamais inventée. */
  factures_mensuelles?: number[] | null;
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
  /**
   * WJ25 — layout de toiture OPTIONNEL (backend PLAN2 QJ26, pas encore exposé
   * aujourd'hui : le champ est absent → la page garde le héros statique). Quand
   * il arrive, sa forme est celle de `serializeLayout` du builder
   * (roofPro11/prefill.ts) : { version, pin, outline, billKwh, zones[],
   * activeAreaId }. On le lit défensivement via `parseRoofLayout` — jamais
   * directement.
   */
  roof_layout?: unknown;
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

// ── WJ29 · « Être contacté » / « Demander un rappel » — notification équipe ──
//
// Aujourd'hui, rappel/WhatsApp sont des liens wa.me / tel: purs côté client :
// rien ne notifie le commercial en interne. Le backend n'expose PAS encore de
// route de contact (PLAN2 QJ27, pas construite) — cette fonction construit
// l'URL du chemin ATTENDU, symétrique de acceptEndpoint ; le proxy
// /api/proposition-contact dégrade proprement (message FR clair) sur 404/5xx/
// panne réseau, en gardant le lien wa.me instantané disponible en parallèle.

/** Construit l'URL backend de la demande de contact (même convention que /accept/). */
export function contactEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/contact/`;
}

/** Canal choisi par le client pour la demande de contact. */
export type ContactChannel = 'rappel' | 'whatsapp' | 'question';

export interface ContactRequestState {
  channel: ContactChannel;
  /** Message libre optionnel (ex. depuis « Poser une question »). */
  message?: string;
}

export interface ContactRequestBody {
  channel: ContactChannel;
  message: string;
}

/**
 * WJ29 — Met en forme le corps envoyé au proxy /api/proposition-contact. Le
 * canal est normalisé (repli 'rappel' si invalide) ; le message est tronqué à
 * une longueur raisonnable pour ne jamais inonder l'upstream.
 */
export function buildContactBody(state: ContactRequestState): ContactRequestBody {
  const channel: ContactChannel =
    state.channel === 'whatsapp' || state.channel === 'question' ? state.channel : 'rappel';
  const message = (state.message ?? '').trim().slice(0, 2000);
  return { channel, message };
}

export interface ContactResult {
  /** Vrai quand la notification a probablement atteint l'équipe (best-effort). */
  ok: boolean;
  /** Message FR à confirmer au client, TOUJOURS rassurant même en dégradé. */
  detail: string;
  /**
   * Vrai quand le backend n'a pas (encore) de route de contact ou est
   * injoignable : le client garde alors le lien wa.me instantané en avant,
   * jamais un message d'échec brut.
   */
  degraded: boolean;
}

/**
 * WJ29 — Normalise le résultat du proxy de contact EN DÉGRADANT TOUJOURS
 * PROPREMENT : le backend ne porte pas encore cette route (404) ou peut être
 * injoignable (5xx / erreur réseau) — dans les deux cas, le client voit un
 * message honnête qui le renvoie vers WhatsApp, jamais une erreur technique.
 * Un succès (2xx) confirme l'envoi au client.
 */
export function normalizeContactResponse(status: number, networkError: boolean = false): ContactResult {
  if (!networkError && status >= 200 && status < 300) {
    return { ok: true, detail: 'Merci — nous vous rappelons très vite.', degraded: false };
  }
  return {
    ok: false,
    degraded: true,
    detail: 'Service momentanément indisponible — contactez-nous sur WhatsApp, nous répondons vite.',
  };
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

// ════════════════════════════════════════════════════════════════════════════
// WJ25 — VISIONNEUSE 3D EN LECTURE SEULE du toit du client sur la proposition.
//
// Toute la logique PURE vit ici (parse défensif du `roof_layout` backend,
// conversion lng/lat → ENU mètres, calepinage ILLUSTRATIF des panneaux) — la
// visionneuse Three.js (roofPro11/viewerOnly.ts) ne fait QUE dessiner ce
// modèle. Aucun chiffre affiché au client ne dérive de ce module : c'est de la
// géométrie de rendu (le nombre de panneaux vient du layout serveur, les kWc /
// production / économies viennent du payload quote).
// ════════════════════════════════════════════════════════════════════════════

/** Un obstacle du layout (zone d'exclusion, rectangle axe-aligné N/E). */
export interface RoofLayoutObstacle {
  centerLng: number;
  centerLat: number;
  lengthM: number;
  widthM: number;
}

/** Une zone (pan de toit) du layout backend, déjà validée. */
export interface RoofLayoutZone {
  id: string;
  label: string;
  /** Contour [[lng,lat],…] (≥ 3 sommets valides — garanti par le parse). */
  vertices: Array<[number, number]>;
  obstacles: RoofLayoutObstacle[];
  roofType: 'flat' | 'pitched';
  /** Pente (°) — 0 pour un toit plat ; bornée [0, 60]. */
  pitchDeg: number;
  /** Azimut de FACE des panneaux (0–360, 180 = plein sud). */
  facingAzimuthDeg: number;
  /** Nombre de panneaux dimensionné par l'étude (0 = « tout ce qui tient »). */
  neededPanels: number;
}

/** Layout de toiture validé (miroir défensif de `serializeLayout` du builder). */
export interface RoofLayout {
  version: number;
  zones: RoofLayoutZone[];
}

function isFiniteNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

/**
 * WJ25 — Parse DÉFENSIF du champ backend `roof_layout` (PLAN2 QJ26, optionnel).
 * Renvoie `null` pour tout ce qui n'est pas un layout exploitable (absent,
 * malformé, aucune zone d'au moins 3 sommets valides) — la page garde alors le
 * héros statique, comportement d'aujourd'hui. Ne jette jamais.
 */
export function parseRoofLayout(raw: unknown): RoofLayout | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  const zonesRaw = obj.zones;
  if (!Array.isArray(zonesRaw)) return null;
  const zones: RoofLayoutZone[] = [];
  for (const z of zonesRaw) {
    if (!z || typeof z !== 'object') continue;
    const zo = z as Record<string, unknown>;
    const vertsRaw = Array.isArray(zo.vertices) ? zo.vertices : [];
    const vertices: Array<[number, number]> = [];
    for (const v of vertsRaw) {
      if (!Array.isArray(v) || v.length < 2) continue;
      const lng = v[0];
      const lat = v[1];
      if (!isFiniteNum(lng) || !isFiniteNum(lat)) continue;
      if (lng < -180 || lng > 180 || lat < -90 || lat > 90) continue;
      vertices.push([lng, lat]);
    }
    if (vertices.length < 3) continue;
    const obstacles: RoofLayoutObstacle[] = [];
    const obsRaw = Array.isArray(zo.obstacles) ? zo.obstacles : [];
    for (const o of obsRaw) {
      if (!o || typeof o !== 'object') continue;
      const oo = o as Record<string, unknown>;
      if (
        isFiniteNum(oo.centerLng) && isFiniteNum(oo.centerLat) &&
        isFiniteNum(oo.lengthM) && oo.lengthM > 0 &&
        isFiniteNum(oo.widthM) && oo.widthM > 0
      ) {
        obstacles.push({
          centerLng: oo.centerLng,
          centerLat: oo.centerLat,
          lengthM: oo.lengthM,
          widthM: oo.widthM,
        });
      }
    }
    const roofType: 'flat' | 'pitched' = zo.roofType === 'pitched' ? 'pitched' : 'flat';
    const pitchRaw = isFiniteNum(zo.pitchDeg) ? zo.pitchDeg : 0;
    const pitchDeg = roofType === 'pitched' ? Math.min(60, Math.max(0, pitchRaw)) : 0;
    const azRaw = isFiniteNum(zo.facingAzimuthDeg) ? zo.facingAzimuthDeg : 180;
    const facingAzimuthDeg = ((azRaw % 360) + 360) % 360;
    const needed = isFiniteNum(zo.neededPanels) && zo.neededPanels > 0
      ? Math.floor(zo.neededPanels)
      : 0;
    zones.push({
      id: typeof zo.id === 'string' ? zo.id : `zone-${zones.length + 1}`,
      label: typeof zo.label === 'string' && zo.label.trim() ? zo.label.trim() : `Pan ${zones.length + 1}`,
      vertices,
      obstacles,
      roofType,
      pitchDeg,
      facingAzimuthDeg,
      neededPanels: needed,
    });
  }
  if (zones.length === 0) return null;
  return { version: isFiniteNum(obj.version) ? obj.version : 1, zones };
}

// ── Constantes de géométrie (dupliquées de roofPro2/roofPro11 — la visionneuse
//    reste autonome ; PURE représentation, aucun chiffre client n'en dérive) ──
/** Grand côté du panneau (m) — même valeur que lib/roofPro2 PANEL2_LONG_M. */
export const VIEWER_PANEL_LONG_M = 2.384;
/** Petit côté du panneau (m) — même valeur que lib/roofPro2 PANEL2_SHORT_M. */
export const VIEWER_PANEL_SHORT_M = 1.303;
/** Retrait de rive (m) — même valeur que lib/roofPro2 PERIMETER_SETBACK_M. */
export const VIEWER_SETBACK_M = 0.5;
/** Inclinaison VISUELLE des châssis sur toit plat (°) — représentation 3D
 *  uniquement (aucune valeur affichée n'en dérive). */
export const VIEWER_FLAT_TILT_DEG = 15;
/** Plafond dur d'instances panneau (garde-fou perf bas de gamme). */
export const VIEWER_MAX_PANELS = 600;

const VIEWER_DEG2RAD = Math.PI / 180;
const VIEWER_DEG2M = 111_320; // mètres par degré de latitude (WGS84 approx.)

/** Point-dans-polygone (ray casting) en coordonnées planes. */
export function viewerPointInRing(pt: [number, number], ring: Array<[number, number]>): boolean {
  let inside = false;
  const [px, py] = pt;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects = yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

/** Un panneau posé (centre ENU mètres, dans la frame du modèle). */
export interface ViewerPanel {
  x: number;
  y: number;
}

/** Une zone prête à dessiner (tout en mètres ENU, origine = centroïde global). */
export interface ViewerZone {
  ringENU: Array<[number, number]>;
  obstaclesENU: Array<{ x: number; y: number; widthM: number; lengthM: number }>;
  roofType: 'flat' | 'pitched';
  /** Inclinaison des PANNEAUX (° — pente du pan si pitched, châssis visuel sinon). */
  tiltDeg: number;
  azimuthDeg: number;
  panels: ViewerPanel[];
  /** Empreinte du panneau : le long de la rangée / dans la pente (m). */
  panelAlongM: number;
  panelDepthM: number;
}

/** Modèle complet consommé par roofPro11/viewerOnly.ts. JSON pur. */
export interface ViewerModel {
  zones: ViewerZone[];
  /** Rayon englobant (m) — cadre la caméra sans calcul côté client. */
  radiusM: number;
  totalPanels: number;
}

/**
 * WJ25 — Calepinage ILLUSTRATIF d'une zone : grille orientée par l'azimut de
 * face, cellules entièrement DANS le contour (retrait de rive) et HORS des
 * obstacles, plafonnée à `neededPanels` (quand > 0). Même esprit que le builder
 * (les N premières cellules), sans en dupliquer l'optimiseur. Pur.
 */
export function packZonePanels(
  ringENU: Array<[number, number]>,
  azimuthDeg: number,
  tiltDeg: number,
  roofType: 'flat' | 'pitched',
  neededPanels: number,
  obstaclesENU: Array<{ x: number; y: number; widthM: number; lengthM: number }> = [],
): { panels: ViewerPanel[]; alongM: number; depthM: number } {
  // Portrait sur pan incliné (pose affleurante courante), paysage sur toit plat.
  const alongM = roofType === 'pitched' ? VIEWER_PANEL_SHORT_M : VIEWER_PANEL_LONG_M;
  const slopeM = roofType === 'pitched' ? VIEWER_PANEL_LONG_M : VIEWER_PANEL_SHORT_M;
  const tilt = tiltDeg * VIEWER_DEG2RAD;
  const depthM = slopeM * Math.cos(tilt); // empreinte au sol dans le sens de la pente
  // Pas de rangée : affleurant → quasi bord à bord ; châssis plat → espace anti-ombrage.
  const rowPitch = roofType === 'pitched' ? depthM + 0.05 : depthM + 1.2;
  const colPitch = alongM + 0.05;

  const az = azimuthDeg * VIEWER_DEG2RAD;
  const f: [number, number] = [Math.sin(az), Math.cos(az)]; // direction de face (aval)
  const u: [number, number] = [-f[1], f[0]]; // direction de rangée

  let aMin = Infinity, aMax = -Infinity, bMin = Infinity, bMax = -Infinity;
  for (const [x, y] of ringENU) {
    const a = x * u[0] + y * u[1];
    const b = x * f[0] + y * f[1];
    if (a < aMin) aMin = a;
    if (a > aMax) aMax = a;
    if (b < bMin) bMin = b;
    if (b > bMax) bMax = b;
  }
  if (!Number.isFinite(aMin) || aMax - aMin < alongM || bMax - bMin < depthM) {
    return { panels: [], alongM, depthM };
  }

  const inObstacle = (x: number, y: number): boolean => {
    for (const o of obstaclesENU) {
      if (Math.abs(x - o.x) <= o.widthM / 2 + 0.1 && Math.abs(y - o.y) <= o.lengthM / 2 + 0.1) return true;
    }
    return false;
  };

  const cap = neededPanels > 0 ? Math.min(neededPanels, VIEWER_MAX_PANELS) : VIEWER_MAX_PANELS;
  const panels: ViewerPanel[] = [];
  const halfA = alongM / 2;
  const halfD = depthM / 2;
  // Parcours des rangées de l'AVAL vers l'AMONT (le sud d'abord pour une face sud),
  // même esprit que « les N premières cellules » du builder.
  for (let b = bMax - VIEWER_SETBACK_M - halfD; b >= bMin + VIEWER_SETBACK_M + halfD; b -= rowPitch) {
    for (let a = aMin + VIEWER_SETBACK_M + halfA; a <= aMax - VIEWER_SETBACK_M - halfA; a += colPitch) {
      const cx = a * u[0] + b * f[0];
      const cy = a * u[1] + b * f[1];
      // Centre + 4 coins dans le polygone, et centre/coins hors obstacles.
      const corners: Array<[number, number]> = [
        [cx + halfA * u[0] + halfD * f[0], cy + halfA * u[1] + halfD * f[1]],
        [cx - halfA * u[0] + halfD * f[0], cy - halfA * u[1] + halfD * f[1]],
        [cx + halfA * u[0] - halfD * f[0], cy + halfA * u[1] - halfD * f[1]],
        [cx - halfA * u[0] - halfD * f[0], cy - halfA * u[1] - halfD * f[1]],
      ];
      if (!viewerPointInRing([cx, cy], ringENU)) continue;
      if (!corners.every((c) => viewerPointInRing(c, ringENU))) continue;
      if (inObstacle(cx, cy) || corners.some(([x, y]) => inObstacle(x, y))) continue;
      panels.push({ x: cx, y: cy });
      if (panels.length >= cap) return { panels, alongM, depthM };
    }
  }
  return { panels, alongM, depthM };
}

/**
 * WJ25 — Construit le modèle 3D complet à partir d'un layout validé : centroïde
 * global comme origine ENU, une ViewerZone par zone (contour + obstacles +
 * calepinage), rayon englobant pour cadrer la caméra. Renvoie `null` quand rien
 * n'est dessinable. Pur, JSON-sûr (calculé côté serveur, sérialisé au client).
 */
export function buildViewerModel(layout: RoofLayout | null): ViewerModel | null {
  if (!layout || layout.zones.length === 0) return null;
  // Centroïde global (tous sommets confondus) = origine de la scène.
  let lng0 = 0, lat0 = 0, n = 0;
  for (const z of layout.zones) {
    for (const [lng, lat] of z.vertices) {
      lng0 += lng;
      lat0 += lat;
      n++;
    }
  }
  if (n === 0) return null;
  lng0 /= n;
  lat0 /= n;
  const cosLat = Math.cos(lat0 * VIEWER_DEG2RAD);
  const toENU = ([lng, lat]: [number, number]): [number, number] => [
    (lng - lng0) * VIEWER_DEG2M * cosLat,
    (lat - lat0) * VIEWER_DEG2M,
  ];

  const zones: ViewerZone[] = [];
  let radiusM = 0;
  let totalPanels = 0;
  let budget = VIEWER_MAX_PANELS;
  for (const z of layout.zones) {
    const ringENU = z.vertices.map(toENU);
    for (const [x, y] of ringENU) radiusM = Math.max(radiusM, Math.hypot(x, y));
    const obstaclesENU = z.obstacles.map((o) => {
      const [x, y] = toENU([o.centerLng, o.centerLat]);
      return { x, y, widthM: o.widthM, lengthM: o.lengthM };
    });
    const tiltDeg = z.roofType === 'pitched' ? z.pitchDeg : VIEWER_FLAT_TILT_DEG;
    const packed = packZonePanels(ringENU, z.facingAzimuthDeg, tiltDeg, z.roofType, z.neededPanels, obstaclesENU);
    const panels = packed.panels.slice(0, Math.max(0, budget));
    budget -= panels.length;
    totalPanels += panels.length;
    zones.push({
      ringENU,
      obstaclesENU,
      roofType: z.roofType,
      tiltDeg,
      azimuthDeg: z.facingAzimuthDeg,
      panels,
      panelAlongM: packed.alongM,
      panelDepthM: packed.depthM,
    });
  }
  if (zones.length === 0) return null;
  return { zones, radiusM: Math.max(radiusM, 6), totalPanels };
}

// ════════════════════════════════════════════════════════════════════════════
// WJ26 — « Tout est expliqué » : légende + annotations + visite guidée autour
// de la 3D. Discipline inchangée : CHAQUE chiffre vient du layout serveur ou du
// payload quote ; quand une valeur manque, on renvoie null et la page affiche
// « estimation indisponible » — jamais une valeur fabriquée.
// ════════════════════════════════════════════════════════════════════════════

/** Libellé FR d'orientation (8 directions) depuis un azimut de face 0–360. */
export function orientationLabelFr(azimuthDeg: number): string {
  const az = ((azimuthDeg % 360) + 360) % 360;
  const labels = ['Nord', 'Nord-Est', 'Est', 'Sud-Est', 'Sud', 'Sud-Ouest', 'Ouest', 'Nord-Ouest'];
  return labels[Math.round(az / 45) % 8];
}

/** Annotation client-lisible d'une zone (pan) du layout. */
export interface ZoneAnnotation {
  label: string;
  /** Nombre de panneaux dimensionné pour ce pan (null si non dimensionné). */
  panels: number | null;
  /** Orientation lisible (« Sud », « Sud-Est »…). */
  orientation: string;
  /** Pente (°) du pan — null pour un toit plat (châssis standard). */
  tiltDeg: number | null;
  roofTypeLabel: string;
  /** kWc du pan = panneaux × Wc/panneau (payload) ; null si l'un manque. */
  kwc: number | null;
}

/**
 * WJ26 — Annotations par pan, à afficher en légende autour de la 3D. Le nombre
 * de panneaux vient du layout SERVEUR (`neededPanels`), la puissance par
 * panneau du payload quote (`watt_par_panneau`) — le kWc n'est calculé que si
 * les deux sont présents (produit de deux valeurs serveur, pas une invention).
 */
export function zoneAnnotations(
  layout: RoofLayout,
  wattParPanneau?: number | null,
): ZoneAnnotation[] {
  const watt = isFiniteNum(wattParPanneau) && wattParPanneau > 0 ? wattParPanneau : null;
  return layout.zones.map((z) => {
    const panels = z.neededPanels > 0 ? z.neededPanels : null;
    return {
      label: z.label,
      panels,
      orientation: orientationLabelFr(z.facingAzimuthDeg),
      tiltDeg: z.roofType === 'pitched' && z.pitchDeg > 0 ? Math.round(z.pitchDeg) : null,
      roofTypeLabel: z.roofType === 'pitched' ? 'Toit en pente' : 'Toit plat',
      kwc: panels !== null && watt !== null ? Math.round(((panels * watt) / 1000) * 100) / 100 : null,
    };
  });
}

/** Texte de repli honnête quand un chiffre ne peut pas être calculé. */
export const FIGURE_UNAVAILABLE = 'estimation indisponible';

/** Une étape de la visite guidée (FR + gloss arabe court). */
export interface WalkStep {
  id: string;
  title: string;
  titleAr: string;
  /** Phrase FR en langage simple — chiffres serveur ou repli libellé. */
  body: string;
}

/**
 * WJ26 — Visite guidée en 4 étapes : « voici votre toit → voici vos panneaux →
 * voici ce qu'ils produisent → voici votre économie ». Chaque chiffre est lu du
 * payload backend (nb_panneaux / puissance_kwc / prod_kwh / eco_*_ann) ; toute
 * valeur absente devient « estimation indisponible » — jamais un nombre
 * fabriqué. Pure (testable sans DOM).
 */
export function walkthroughSteps(p: ProposalResponse): WalkStep[] {
  const q = p.quote;
  const nb = isFiniteNum(q?.nb_panneaux) && q!.nb_panneaux! > 0 ? q!.nb_panneaux! : null;
  const kwc = isFiniteNum(q?.puissance_kwc) && q!.puissance_kwc! > 0 ? q!.puissance_kwc! : null;
  const prod = isFiniteNum(q?.prod_kwh) && q!.prod_kwh! > 0 ? q!.prod_kwh! : null;
  const head = savingsHeadline(p, recommendedOption(p));

  const panneauxBody =
    nb !== null
      ? `${formatNumber(nb)} panneaux${kwc !== null ? `, soit ${formatNumber(kwc, 2)} kWc` : ''}, positionnés selon l’étude de votre toiture.`
      : `Vos panneaux sont positionnés selon l’étude de votre toiture (nombre : ${FIGURE_UNAVAILABLE}).`;
  const prodBody =
    prod !== null
      ? `Environ ${formatNumber(prod)} kWh produits par an — de l’électricité que vous n’achetez plus au réseau.`
      : `Production annuelle : ${FIGURE_UNAVAILABLE}.`;
  const ecoBody =
    head.annual !== null
      ? `Environ ${formatMAD(head.annual)} d’économies par an${head.monthly !== null ? ` (≈ ${formatMAD(head.monthly)}/mois)` : ''}, en autoconsommation (loi 82-21).`
      : `Économie annuelle : ${FIGURE_UNAVAILABLE}.`;

  return [
    {
      id: 'toit',
      title: 'Voici votre toit',
      titleAr: 'هذا سطح منزلكم',
      body: 'Le contour et les pans que vous voyez sont ceux de VOTRE toiture, telle que tracée lors de l’étude. Faites glisser pour tourner autour.',
    },
    {
      id: 'panneaux',
      title: 'Voici vos panneaux',
      titleAr: 'هذه ألواحكم الشمسية',
      body: panneauxBody,
    },
    {
      id: 'production',
      title: 'Voici ce qu’ils produisent',
      titleAr: 'هذا ما تنتجه',
      body: prodBody,
    },
    {
      id: 'economie',
      title: 'Voici votre économie',
      titleAr: 'هذا ما توفرونه',
      body: ecoBody,
    },
  ];
}
