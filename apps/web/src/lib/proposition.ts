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
  roi_s?: number | string;
  roi_a?: number | string;
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
  option_totals: OptionTotals;
  accepted: boolean;
  accepte_par_nom?: string | null;
  date_acceptation?: string | null;
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
