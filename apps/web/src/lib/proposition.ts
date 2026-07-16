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
  /**
   * WJ32 — texte de description du produit (fiche commerciale). Backend
   * `_line_to_item` l'expose déjà (`description`) ; optionnel — un produit
   * historique sans fiche renvoie une chaîne vide, jamais inventée.
   */
  description?: string;
  /**
   * WJ32 — texte de garantie constructeur/performance du produit. Backend
   * `_line_to_item` l'expose déjà (`garantie`) ; vide quand non renseigné.
   */
  garantie?: string;
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
  /**
   * WJ32 — bloc de financement backend (QJ12, `compute_financing_block`),
   * DIFFÉRENT du calcul générique `financingComparison` ci-dessus : porte un
   * programme réel (Tatwir Croissance Verte / ISTIDAMA…) et une comparaison
   * ONEE déjà rédigée côté serveur. Absent quand `display_total` est
   * indisponible — le bloc financement se masque alors (jamais un calcul de
   * repli qui divergerait du backend).
   */
  financing?: ProposalFinancingBlock | null;
  /**
   * WJ32 — résumés « autres tailles » des variantes actives du même devis
   * (QJ15, `_variant_summaries`). Tableau vide quand le devis est isolé
   * (aucun frère/sœur actif) — la strip « autres tailles » se masque alors.
   */
  variants?: ProposalVariantSummary[];
  /**
   * WJ114 — bloc vendeur OPTIONNEL (note personnelle + identité), pas encore
   * exposé par le backend aujourd'hui : lu défensivement (`sellerNote` ci-
   * dessous) pour qu'il s'allume dès que l'ERP le fournira, sans crash ni
   * placeholder en attendant. Aucun de ces trois champs n'est requis
   * ensemble — `sellerNote` ne renvoie que ceux réellement fournis.
   */
  seller?: {
    /** Courte note personnalisée rédigée par le vendeur pour ce client. */
    note?: string | null;
    /** Nom du vendeur/conseiller. */
    name?: string | null;
    /** URL de la photo du vendeur. */
    photo_url?: string | null;
  } | null;
}

/** WJ32 — bloc `financing` backend (QJ12), structure de `compute_financing_block`. */
export interface ProposalFinancingBlock {
  indicatif: true;
  cash: { montant_ttc: number; label: string };
  credit: {
    mensualite: number;
    duree_mois: number;
    taux_annuel_pct: number;
    programme_nom: string;
    programme_label: string | null;
  };
  onee_comparison: {
    show: boolean;
    message: string;
    eco_mensuelle_sans: number;
    eco_mensuelle_avec: number;
  };
  guidance_text: string | null;
}

/** WJ32 — un résumé de variante (QJ15 `_variant_summaries`), pour la strip « autres tailles ». */
export interface ProposalVariantSummary {
  id: number;
  reference: string;
  version: number;
  note: string;
  total_ttc: number;
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
 * WJ72 — UN SEUL style de nombre de bout en bout : l'estimation instantanée
 * (/devis/mon-toit) affichait jusqu'ici le kWc BRUT (`String(est.kwc)` →
 * point décimal, ex. « 7.5 kWc ») pendant que la proposition utilisait déjà
 * `formatNumber(kwc, 2)` (virgule décimale, zéros de fin retirés, ex.
 * « 7,5 kWc » ou « 11 kWc »). Un client qui compare son estimation à sa
 * proposition voyait deux langages de nombres différents. `formatKwc` est
 * l'UNIQUE point de formatage kWc du site — mon-toit.astro (FR/EN/AR) et la
 * proposition l'utilisent tous les deux désormais, jamais un `String(...)`
 * ou un `.toFixed(...)` local.
 */
export function formatKwc(value: number | null | undefined): string {
  return formatNumber(value, 2);
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

/**
 * WJ83 — Garde-fou « zéro chiffre inventé » appliqué au PRIX : `optionTtc`
 * retombe sur `0` (via `?? 0`) quand aucun totaux n'est exploitable — un
 * payload dégénéré (devis mal formé, option absente) affichait alors
 * « 0 MAD TTC, clé en main » comme un VRAI prix. `hasRealPrice` distingue un
 * prix réel (TTC backend strictement positif) d'un repli à 0 : la page doit
 * alors masquer le prix + le CTA de signature et afficher un message
 * honnête (« prix communiqué par votre conseiller ») plutôt qu'un chiffre.
 */
export function hasRealPrice(p: ProposalResponse, opt: OptionKey): boolean {
  const ttc = optionTtc(p, opt);
  return Number.isFinite(ttc) && ttc > 0;
}

/** Étiquette FR courte d'une option. */
export function optionLabel(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'Avec batterie' : 'Sans batterie';
}

/** WJ43 — Étiquette arabe d'une option (paire de `optionLabel` pour le data-i18n). */
export function optionLabelAr(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'مع بطارية' : 'بدون بطارية';
}

/** WJ43 — Étiquette anglaise d'une option (paire de `optionLabel` pour le data-i18n). */
export function optionLabelEn(opt: OptionKey): string {
  return opt === 'avec_batterie' ? 'With battery' : 'Without battery';
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
export function isAccepted(p: Pick<ProposalResponse, 'accepted' | 'statut'>): boolean {
  return p.accepted === true || p.statut === 'accepte';
}

// ── WJ82 · États explicites d'une offre morte (refusée / expirée / retirée) ──

/**
 * L'état de l'offre du point de vue de la signature. `statut` backend est l'un
 * des 5 statuts canoniques du devis (brouillon/envoye/accepte/refuse/expire —
 * voir `apps/ventes/models.py Devis.Statut`) ; « withdrawn » n'existe pas côté
 * backend aujourd'hui mais est accepté défensivement comme alias de `refuse`
 * si jamais rencontré (jamais une nouvelle valeur inventée, juste une synonymie
 * de lecture). `expired` retombe sur `resolveValidity` (date_validite dépassée)
 * quand le statut lui-même ne le dit pas déjà.
 */
export type OfferState = 'live' | 'accepted' | 'refused' | 'expired' | 'withdrawn';

/**
 * WJ82 — Résout l'état de signature d'une offre : une offre acceptée, refusée,
 * expirée (statut backend `expire` OU date de validité dépassée) ou retirée ne
 * doit plus pouvoir être signée. `live` = tout le reste (brouillon/envoyé,
 * dans les temps) — seul état où le formulaire + le CTA collant restent actifs.
 */
export function resolveOfferState(
  p: Pick<ProposalResponse, 'statut' | 'accepted' | 'date_validite' | 'quote'>,
  now: Date = new Date(),
): OfferState {
  if (isAccepted(p)) return 'accepted';
  const statut = (p.statut ?? '').trim().toLowerCase();
  if (statut === 'refuse' || statut === 'refusee' || statut === 'refusé') return 'refused';
  if (statut === 'withdrawn' || statut === 'retire' || statut === 'retiré') return 'withdrawn';
  if (statut === 'expire' || statut === 'expiré' || statut === 'expired') return 'expired';
  if (resolveValidity(p, now).expired) return 'expired';
  return 'live';
}

/** Vrai quand l'offre ne peut plus être signée (tout sauf `live`). */
export function isOfferDead(state: OfferState): boolean {
  return state !== 'live';
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
// QW5 (2026-07-05) — la route backend EXISTE et est aliasée sous ce mount
// (apps/ventes/urls.py, réutilisant les vues QJ27 déjà exposées sous
// public/) : channel/message/revision_kind sont bien reçus et traités
// (chatter + notification owner+supérieur, idempotence par lien+canal). Le
// proxy /api/proposition-contact dégrade quand même proprement (message FR
// clair) sur un éventuel 404/5xx/panne réseau, en gardant le lien wa.me
// instantané disponible en parallèle.

/** Construit l'URL backend de la demande de contact (même convention que /accept/). */
export function contactEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/contact/`;
}

/** Canal choisi par le client pour la demande de contact. WJ85 — `voice`
 *  couvre l'invitation à la note vocale WhatsApp (canal distinct de `whatsapp`
 *  générique, pour que l'équipe voie que le client a été orienté vers un
 *  message vocal plutôt qu'un texte). WJ54 — `revision` couvre la demande de
 *  modification structurée (voir `RevisionKind` ci-dessous) : un canal
 *  DISTINCT des précédents pour que le CRM/lead webhook puisse la trier
 *  séparément d'un simple rappel/question. */
export type ContactChannel = 'rappel' | 'whatsapp' | 'question' | 'voice' | 'revision';

export interface ContactRequestState {
  channel: ContactChannel;
  /** Message libre optionnel (ex. depuis « Poser une question »). */
  message?: string;
  /** WJ54 — précise le TYPE de modification demandée (uniquement quand `channel === 'revision'`). */
  revisionKind?: RevisionKind;
}

export interface ContactRequestBody {
  channel: ContactChannel;
  message: string;
  /** WJ54 — omis quand `channel !== 'revision'` (jamais un champ vide envoyé sans raison). */
  revision_kind?: RevisionKind;
}

/**
 * WJ29/WJ85 — Met en forme le corps envoyé au proxy /api/proposition-contact.
 * Le canal est normalisé (repli 'rappel' si invalide) ; le message est
 * tronqué à une longueur raisonnable pour ne jamais inonder l'upstream.
 */
export function buildContactBody(state: ContactRequestState): ContactRequestBody {
  const channel: ContactChannel =
    state.channel === 'whatsapp' || state.channel === 'question' || state.channel === 'voice' || state.channel === 'revision'
      ? state.channel
      : 'rappel';
  const message = (state.message ?? '').trim().slice(0, 2000);
  const body: ContactRequestBody = { channel, message };
  if (channel === 'revision') {
    const kind = state.revisionKind;
    body.revision_kind = kind === 'kwc' || kind === 'batterie' || kind === 'autre' ? kind : 'autre';
  }
  return body;
}

// ── WJ54 · « Demander une modification » — formulaire de révision structurée ─

/**
 * WJ54 — Type d'ajustement demandé par le client sur SA proposition : ajuster
 * la puissance (kWc), changer l'option batterie, ou « autre » (texte libre
 * obligatoire dans ce cas). Volontairement les 3 catégories les plus
 * fréquentes observées en négociation avant signature — pas une nomenclature
 * exhaustive.
 */
export type RevisionKind = 'kwc' | 'batterie' | 'autre';

export interface RevisionRequestState {
  kind: RevisionKind;
  /** Texte libre — TOUJOURS envoyé (contexte utile même pour kwc/batterie), tronqué comme un message normal. */
  detail: string;
}

export interface RevisionValidation {
  valid: boolean;
  /** Message FR à afficher quand invalide (null si valide). */
  error: string | null;
}

/**
 * WJ54 — Validation du formulaire de révision : le type doit être l'une des 3
 * valeurs reconnues ; le texte libre est OBLIGATOIRE pour « autre » (sinon la
 * demande n'a aucun contenu exploitable), optionnel pour kwc/batterie (le type
 * suffit à orienter le conseiller, le texte est un complément).
 */
export function validateRevisionRequest(state: RevisionRequestState): RevisionValidation {
  const kind = state.kind;
  if (kind !== 'kwc' && kind !== 'batterie' && kind !== 'autre') {
    return { valid: false, error: 'Veuillez choisir le type de modification souhaitée.' };
  }
  const detail = (state.detail ?? '').trim();
  if (kind === 'autre' && !detail) {
    return { valid: false, error: 'Merci de préciser votre demande en quelques mots.' };
  }
  return { valid: true, error: null };
}

/**
 * WJ54 — Construit le corps de la demande de révision, prêt à poster vers le
 * proxy /api/proposition-contact (même endpoint que WJ29 — canal `revision`
 * distinct, AUCUN nouveau endpoint). Le message combine un préfixe FR lisible
 * par le conseiller (« Ajuster la puissance (kWc) » etc.) et le texte libre du
 * client, tronqué comme tout message de contact.
 */
export function buildRevisionContactState(state: RevisionRequestState): ContactRequestState {
  const kind: RevisionKind = state.kind === 'kwc' || state.kind === 'batterie' ? state.kind : 'autre';
  const labels: Record<RevisionKind, string> = {
    kwc: 'Ajuster la puissance (kWc)',
    batterie: 'Changer l’option batterie',
    autre: 'Autre modification',
  };
  const detail = (state.detail ?? '').trim();
  const message = detail ? `${labels[kind]} — ${detail}` : labels[kind];
  return { channel: 'revision', message, revisionKind: kind };
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
 * WJ9 — Horizon d'analyse des économies cumulées : 25 ans. Durée de vie
 * économique conventionnelle de l'installation retenue pour le calcul (choix
 * prudent), et non un chiffre marketing. La garantie de performance des panneaux
 * posés va en réalité au-delà : linéaire sur 30 ans, ≥ 87,4 % de la puissance
 * initiale à 30 ans (donc ≥ 89,4 % à 25 ans), cf. `src/lib/warranty.ts`.
 */
export const SAVINGS_HORIZON_YEARS = 25;

/**
 * WJ9 — Dérive annuelle de la facture d'électricité (« coût de ne rien faire »).
 * Hypothèse PRUDENTE et libellée : 0 % par défaut (économies à tarif constant).
 * Le calcul de cumul reste honnête même sans inflation tarifaire. Toute hausse
 * réelle ne ferait qu'augmenter l'économie — on ne la promet donc pas.
 *
 * WJ75 — CONFIRMÉ ALIGNÉ avec le backend (lu dans le moteur de devis vendorisé,
 * `apps/ventes/quote_engine/`) : `pricing.py calculate_savings_roi` fixe
 * `eco_a_cumul = economie_opt2` (l'économie ANNUELLE, malgré son nom) SANS
 * aucune dérive tarifaire, et `generate_devis_premium.py` l'utilise comme un
 * TAUX PAR AN pour bâtir sa courbe cumulative sur 26 points (0 à 25 ans) :
 * `CUMUL_A = [-TOTAL_AVEC + eco_a_cumul * y for y in YEARS]` — une simple
 * multiplication linéaire, aucun terme `(1+i)^y`. Le PDF premium et cette page
 * web utilisent donc EXACTEMENT la même hypothèse (0 % d'escalade tarifaire) ;
 * aucun décalage à corriger entre les deux documents. Le nom du champ backend
 * (« cumul ») est trompeur — c'est un TAUX ANNUEL, pas un total déjà cumulé
 * (voir savingsHeadline ci-dessous, qui le multiplie désormais par `years`
 * au lieu de l'afficher tel quel comme un cumul déjà calculé).
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

// ── WJ42 · Horodatage de signature localisé (FR/AR/EN) ───────────────────────

/** Langue active de la page proposition (bascule FR/EN/AR — WJ17/WJ43). */
export type PropLang = 'fr' | 'en' | 'ar';

const STAMP_LOCALE: Record<PropLang, string> = {
  fr: 'fr-MA',
  en: 'en-GB',
  ar: 'ar-MA',
};

/**
 * WJ42 — Formate un horodatage de signature dans la langue active. Auparavant
 * la page injectait toujours `frenchStamp()` en texte brut dans `#sign-stamp`,
 * ce qui (a) écrasait le markup dual-node d'i18n et (b) affichait une date
 * française même en mode arabe/anglais. Cette fonction est PURE (testable sans
 * DOM) : le composant appelant doit la ré-invoquer à chaque bascule de langue
 * ET la ré-enregistrer via le registre `propI18nBusyLabels` (même discipline
 * que `renderSubmitLabel`), jamais un remplacement ponctuel non ré-inscrit.
 */
export function localizedStamp(d: Date, lang: PropLang): string {
  const locale = STAMP_LOCALE[lang] ?? STAMP_LOCALE.fr;
  try {
    return d.toLocaleString(locale, { dateStyle: 'long', timeStyle: 'short' });
  } catch {
    return d.toLocaleString('fr-FR');
  }
}

/** WJ42 — Libellé « Réf. … · signature horodatée le … » dans les 3 langues. */
export function signStampLabel(reference: string, d: Date, lang: PropLang): string {
  const stamp = localizedStamp(d, lang);
  if (lang === 'ar') {
    return `المرجع ${reference} · تم توقيعه بتاريخ ${stamp} (بتوقيت جهازكم).`;
  }
  if (lang === 'en') {
    return `Ref. ${reference} · signature timestamped on ${stamp} (your device's local time).`;
  }
  return `Réf. ${reference} · signature horodatée le ${stamp} (heure de votre appareil).`;
}

// ── WJ9 · Argent dans le temps (cumul 25 ans + cadrage mensuel) ──────────────

export interface SavingsHeadline {
  /** Économie annuelle (MAD/an) — backend `eco_*_ann`. */
  annual: number | null;
  /** Économie cumulée sur l'horizon (MAD) — dérivée du TAUX annuel `eco_a_cumul` (× years) ou du calcul local. */
  cumulative: number | null;
  /** Horizon retenu (ans). */
  years: number;
  /** Économie mensuelle équivalente (MAD/mois) ≈ annuel / 12. */
  monthly: number | null;
  /** Retour sur investissement (déjà formaté). */
  payback: string | null;
  /** Vrai si le TAUX vient directement du backend (`eco_a_cumul`) plutôt que du fallback `annual`. */
  cumulativeFromBackend: boolean;
}

/**
 * WJ9/WJ75 — Construit le bandeau « money over time » de l'option recommandée.
 *
 *  - `annual` : économie annuelle backend (`eco_*_ann`).
 *  - `cumulative` : sur l'horizon (`years`, 25 ans par défaut).
 *
 * WJ75 — CORRECTIF : malgré son nom, le champ backend `eco_a_cumul`
 * (`apps/ventes/quote_engine/pricing.py calculate_savings_roi`) n'est PAS déjà
 * un total cumulé — c'est le même chiffre que l'économie ANNUELLE
 * (`eco_a_cumul == eco_a_ann` côté backend), utilisé par le moteur PDF comme un
 * TAUX PAR AN : `generate_devis_premium.py` construit sa courbe cumulative par
 * `CUMUL_A = [-total + eco_a_cumul * y for y in YEARS]` (multiplication
 * linéaire, AUCUNE dérive tarifaire — 0 % d'escalade, comme `BILL_INFLATION_RATE`
 * ci-dessus). Avant ce correctif, cette fonction affichait `eco_a_cumul`
 * DIRECTEMENT comme si le backend avait déjà fait `× 25` — ce qui montrait la
 * valeur d'UNE SEULE ANNÉE sous le libellé « cumul sur 25 ans » (sous-estimation
 * ≈25× du chiffre le plus visible de la page). Le calcul respecte maintenant la
 * MÊME hypothèse que le PDF (taux annuel backend × horizon, 0 % d'escalade) —
 * les deux documents sont désormais alignés, jamais un cumul sur 25 ans qui
 * n'est en réalité qu'un an. Le repli local (sans backend) applique la même
 * discipline (`BILL_INFLATION_RATE`, 0 % par défaut) à `annual`. On NE calcule
 * jamais sans un taux/annuel positif présent.
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

  // WJ75 — `eco_a_cumul` est un TAUX ANNUEL (voir la note ci-dessus), jamais un
  // total déjà cumulé : on le multiplie par `years`, exactement comme le fait
  // le moteur PDF (`eco_a_cumul * y`), au lieu de l'afficher tel quel.
  const backendRate = p.quote?.eco_a_cumul;
  const hasBackendRate = typeof backendRate === 'number' && Number.isFinite(backendRate) && backendRate > 0;
  const rate = hasBackendRate ? backendRate : annual;
  let cumulative: number | null = null;
  const cumulativeFromBackend = hasBackendRate;
  if (rate !== null && years > 0) {
    // Série honnête : taux constant (0 % d'escalade, comme le PDF) sauf si
    // BILL_INFLATION_RATE est un jour changé — alors Σ taux·(1+i)^k, k=0..years-1.
    const i = BILL_INFLATION_RATE;
    cumulative = i === 0
      ? rate * years
      : Math.round((rate * (Math.pow(1 + i, years) - 1)) / i);
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

// ── WJ53 · « Payer comptant / paiement échelonné » — toggle interactif ───────

/**
 * WJ53 — Choix de durées (mois) proposés par le toggle « paiement échelonné ».
 * Volontairement COURT (pas de simulation de crédit bancaire, voir WJ10/WJ32
 * pour l'éco-prêt) : c'est une simple division indicative du TTC, pour un
 * client qui négocie un paiement en plusieurs fois DIRECTEMENT avec Taqinor —
 * jamais présentée comme une offre bancaire.
 */
export const INSTALLMENT_MONTH_OPTIONS = [3, 6, 12, 24] as const;
export type InstallmentMonths = (typeof INSTALLMENT_MONTH_OPTIONS)[number];

export interface InstallmentSplit {
  /** Prix comptant TTC (backend, inchangé). */
  cashTtc: number;
  /** Nombre de mois choisi. */
  months: InstallmentMonths;
  /** TTC ÷ mois, arrondi au MAD — AUCUN taux/intérêt ajouté (simple division). */
  monthly: number;
}

/**
 * WJ53 — Calcule la mensualité INDICATIVE d'un paiement échelonné sur `months`
 * mois, par simple division du TTC (aucun taux inventé, aucun frais). Renvoie
 * `null` quand le TTC n'est pas un prix réel positif (même garde-fou zéro-total
 * que `hasRealPrice`) — jamais un chiffre calculé sur un montant fabriqué.
 */
export function installmentSplit(
  cashTtc: number,
  months: InstallmentMonths = 12,
): InstallmentSplit | null {
  if (!Number.isFinite(cashTtc) || cashTtc <= 0) return null;
  const safeMonths = INSTALLMENT_MONTH_OPTIONS.includes(months) ? months : 12;
  return {
    cashTtc,
    months: safeMonths,
    monthly: Math.round(cashTtc / safeMonths),
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

/**
 * WJ56 — Partage du lien TOKENISÉ de LA PROPOSITION ELLE-MÊME (pas une question
 * pour Taqinor) : le client transmet sa proposition à un conjoint/co-décideur
 * SANS rien ressaisir. Différent de `whatsappLink` (qui adresse un message AU
 * numéro Taqinor) — ici `wa.me/` sans numéro ouvre le compositeur WhatsApp
 * générique (le client choisit lui-même le destinataire). `pageUrl` est
 * l'URL COMPLÈTE de la page courante (avec le token), jamais reconstruite.
 */
export function whatsappShareLink(pageUrl: string, reference: string): string {
  const url = (pageUrl || '').trim();
  const ref = (reference || '').trim();
  const msg = ref
    ? `Voici ma proposition solaire Taqinor (réf. ${ref}) : ${url}`
    : `Voici ma proposition solaire Taqinor : ${url}`;
  return `https://wa.me/?text=${encodeURIComponent(msg)}`;
}

// ── W343 · « Partager avec un proche » — composeur de parrainage post-signature ─
//
// DISTINCT de whatsappShareLink (WJ56) : WJ56 partage LA MÊME PROPOSITION avec
// un co-décideur du MÊME foyer (avant signature, pour décider ensemble). W343
// partage le programme de PARRAINAGE (/parrainage, W338) avec un PROCHE
// DIFFÉRENT, une fois le devis SIGNÉ (le moment de satisfaction maximale) —
// un lien vers un NOUVEAU projet solaire pour ce proche, pas vers ce devis-ci.
//
// ZÉRO CHANGEMENT BACKEND (même discipline que /parrainage, W338) : le
// `<code>` du lien tagué est simplement la RÉFÉRENCE du devis déjà signé —
// aucun code de parrainage n'existe côté backend aujourd'hui, donc on réutilise
// un identifiant déjà réel plutôt que d'en inventer un nouveau. L'ERP peut
// filtrer ses leads entrants sur `utm_source=parrainage` et retrouver le
// parrain via `utm_campaign` (= la référence de SON devis), exactement comme
// documenté sur /parrainage.astro.

/**
 * W343 — Construit l'URL de /parrainage TAGUÉE avec la référence du client qui
 * vient de signer, dans le MÊME format que documenté sur /parrainage.astro
 * (`utm_source=parrainage&utm_campaign=<code>`). `siteOrigin` est l'origine
 * RÉELLE servie (ex. `Astro.url.origin`), jamais reconstruite en dur.
 */
export function referralTaggedLink(siteOrigin: string, reference: string): string {
  const origin = (siteOrigin || 'https://taqinor.ma').replace(/\/+$/, '');
  const code = (reference || '').trim();
  const qs = code ? `?utm_source=parrainage&utm_campaign=${encodeURIComponent(code)}` : '?utm_source=parrainage';
  return `${origin}/parrainage${qs}`;
}

/**
 * W343 — Compositeur WhatsApp « Partager avec un proche » : `wa.me/` SANS
 * numéro (même mécanique que whatsappShareLink) ouvre le compositeur générique
 * — le client choisit lui-même à qui l'envoyer. Le message pointe vers le lien
 * de parrainage TAGUÉ (referralTaggedLink), jamais vers la proposition elle-même.
 */
export function whatsappReferralLink(siteOrigin: string, reference: string): string {
  const url = referralTaggedLink(siteOrigin, reference);
  const msg = `J'ai fait installer mes panneaux solaires avec Taqinor — si ça vous intéresse, voici le lien : ${url}`;
  return `https://wa.me/?text=${encodeURIComponent(msg)}`;
}

/**
 * WJ85 — Intention du point de contact « au moindre doute » (avant signature).
 * `discuss` (« Discuter sur WhatsApp ») et `question` (« Poser une question »)
 * pointaient auparavant vers le MÊME `whatsappLink(reference)`, un seul message
 * générique — deux boutons qui font la même chose lisent comme du remplissage.
 * `voice` couvre l'invitation à une note vocale (canal WhatsApp natif, plus
 * rapide à envoyer qu'un texte pour beaucoup de clients).
 */
export type WhatsappIntent = 'discuss' | 'question' | 'voice';

/**
 * WJ85 — Construit un deep-link wa.me avec un PRÉREMPLISSAGE distinct par
 * intention (toujours citant la référence quand présente, même discipline que
 * `whatsappLink`). `phone` peut surcharger le numéro par défaut.
 */
export function whatsappLinkForIntent(
  reference: string,
  intent: WhatsappIntent,
  phone: string = TAQINOR_WHATSAPP,
): string {
  const digits = (phone || TAQINOR_WHATSAPP).replace(/[^\d]/g, '') || TAQINOR_WHATSAPP;
  const ref = (reference || '').trim();
  const refSuffix = ref ? ` (réf. ${ref})` : '';
  const messages: Record<WhatsappIntent, string> = {
    discuss: `Bonjour, je voudrais discuter de ma proposition Taqinor${refSuffix} avant de signer.`,
    question: `Bonjour, j'ai une question précise sur ma proposition Taqinor${refSuffix}.`,
    voice: `Bonjour, je vous envoie une note vocale au sujet de ma proposition Taqinor${refSuffix}.`,
  };
  const msg = messages[intent] ?? messages.question;
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
  /**
   * WJ87 — Nom facultatif de la personne/du foyer au nom de qui le signataire
   * agit (ex. « mes parents », « mon foyer »). Le signataire enregistré reste
   * TOUJOURS `nom` (champ de base) ; ce champ est une précision ADDITIVE,
   * jamais un remplacement — un backend qui l'ignore continue de fonctionner
   * exactement comme avant.
   */
  on_behalf_of?: string;
  /**
   * WJ108 — code OTP à 6 chiffres (backend `apps/ventes/services.py
   * validate_esign_otp`, toggle `ESIGN_OTP_ENABLED`). Omis quand vide : un
   * backend/toggle OFF ignore silencieusement ce champ (comportement
   * inchangé), un backend/toggle ON qui n'a rien reçu répond avec le message
   * « code requis » que `isOtpRequiredMessage` reconnaît plus bas.
   */
  otp_code?: string;
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
  // WJ87 — omis quand vide/absent (jamais une chaîne vide envoyée au backend).
  if (typeof meta.on_behalf_of === 'string' && meta.on_behalf_of.trim()) {
    body.on_behalf_of = meta.on_behalf_of.trim();
  }
  // WJ108 — idem : omis quand vide (jamais un champ vide envoyé sans raison).
  if (typeof meta.otp_code === 'string' && meta.otp_code.trim()) {
    body.otp_code = meta.otp_code.trim();
  }
  return body;
}

// ── WJ108 · OTP e-signature (backend toggle ESIGN_OTP_ENABLED, latent) ───────
//
// Le backend (`apps/ventes/services.py validate_esign_otp`) répond aux 3
// messages FR EXACTS ci-dessous selon l'état de l'OTP — AUCUN flag structuré
// (type `otp_required: true`) n'accompagne ces messages aujourd'hui (voir
// `apps/ventes/public_views.py proposal_accept` : un simple `{'detail': ...}`
// en 400, indiscernable structurellement d'une autre erreur de validation).
// Reconnaître le besoin d'OTP passe donc PAR CONTENU DE MESSAGE — fragile
// (un futur changement de libellé backend le casserait silencieusement) mais
// c'est le seul signal disponible sans modification côté serveur. Tant que
// ESIGN_OTP_ENABLED reste OFF (comportement par défaut), ces messages ne sont
// jamais renvoyés : cette détection reste un pur no-op aujourd'hui.

const OTP_REQUIRED_MESSAGES = [
  'Un code de confirmation est requis. Demandez-le via le bouton « Envoyer le code ».',
  'Le code de confirmation a expiré ou n\'a pas été demandé. Redemandez un nouveau code.',
  'Code de confirmation incorrect. Vérifiez le code reçu et réessayez.',
] as const;

/**
 * WJ108 — Vrai si le `detail` d'une réponse 400 de `/accept/` signale un
 * besoin d'OTP (absent/expiré/incorrect) plutôt qu'une autre erreur de
 * validation (nom manquant, devis déjà traité, etc.). `null`/vide → false.
 */
export function isOtpRequiredDetail(detail: string | null | undefined): boolean {
  const d = (detail ?? '').trim();
  if (!d) return false;
  return (OTP_REQUIRED_MESSAGES as readonly string[]).includes(d);
}

/**
 * WJ108 — Vrai UNIQUEMENT pour le message « code incorrect » (distinct de
 * « requis »/« expiré ») — permet d'afficher un message d'erreur ciblé
 * (« code incorrect, réessayez ») plutôt que de redemander un nouveau code à
 * chaque échec.
 */
export function isOtpIncorrectDetail(detail: string | null | undefined): boolean {
  return (detail ?? '').trim() === OTP_REQUIRED_MESSAGES[2];
}

/** Construit l'URL backend de demande d'envoi d'un code OTP (même convention que `/accept/`). */
export function otpRequestEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/otp/`;
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
// WJ2 — « Voir les panneaux sur votre toit » à la CAPTURE (mon-toit.astro).
// Construit un RoofLayout ILLUSTRATIF à un seul pan à partir du contour posé
// par le visiteur (captureBoot.ts onCaptureChange) + le kWc de l'estimation
// instantanée WJ1 (billEstimate). AUCUNE donnée backend ici (page publique,
// avant tout devis) : le nombre de panneaux dérive du MÊME calcul
// PANEL2_WATT que le reste du site (estimatorBrain), jamais un chiffre
// inventé. Toit supposé plat orienté plein sud (176°) — représentation
// illustrative « votre toit, vos panneaux », pas une étude technique.
// ════════════════════════════════════════════════════════════════════════════

/** Watt-crête d'un panneau — même constante que le reste du site (roofPro2). */
export const CAPTURE_PANEL_WATT = 720;

/**
 * WJ2 — Construit un RoofLayout à un seul pan (plat, plein sud illustratif)
 * depuis un contour de toit `[[lat,lng],…]` (≥ 3 sommets, tel que renvoyé par
 * `onCaptureChange`) et un kWc cible (estimation WJ1). Renvoie `null` si le
 * contour n'a pas assez de sommets ou si le kWc n'est pas un nombre positif —
 * la page dégrade alors proprement (pas de bouton « voir les panneaux »).
 */
export function capturePreviewLayout(
  outlineLatLng: Array<[number, number]>,
  kwc: number | null,
): RoofLayout | null {
  if (!Array.isArray(outlineLatLng) || outlineLatLng.length < 3) return null;
  if (!Number.isFinite(kwc) || (kwc as number) <= 0) return null;
  const vertices: Array<[number, number]> = [];
  for (const pt of outlineLatLng) {
    if (!Array.isArray(pt) || pt.length < 2) continue;
    const [lat, lng] = pt;
    if (!isFiniteNum(lat) || !isFiniteNum(lng)) continue;
    vertices.push([lng, lat]); // RoofLayoutZone attend [lng,lat]
  }
  if (vertices.length < 3) return null;
  const neededPanels = Math.max(1, Math.ceil(((kwc as number) * 1000) / CAPTURE_PANEL_WATT));
  return {
    version: 1,
    zones: [
      {
        id: 'capture-preview',
        label: 'Votre toit',
        vertices,
        obstacles: [],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 176, // plein sud illustratif — aucune boussole réelle à cette étape
        neededPanels,
      },
    ],
  };
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

// ════════════════════════════════════════════════════════════════════════════
// WJ32 — Complétude du contenu de la proposition : financement backend réel,
// fiche produit enrichie (marque/garantie/fiche technique), « Et après ? »,
// « Nos hypothèses », accompagnement post-installation, FAQ objections,
// variantes côte-à-côte. Même discipline « zéro chiffre inventé » : chaque
// fonction ne lit QUE des champs backend présents, et dégrade proprement
// (tableau vide / null) quand une donnée manque — jamais un repli fabriqué.
// ════════════════════════════════════════════════════════════════════════════

/**
 * WJ32 — Lecture défensive du bloc `financing` BACKEND (QJ12). Différent de
 * `financingComparison` (calcul générique ci-dessus, gardé pour compat) : ce
 * bloc porte le VRAI programme (Tatwir/ISTIDAMA) choisi par le backend selon
 * `inst_type`. Renvoie `null` quand absent/malformé — la page masque alors
 * le bloc financement (jamais de mélange entre les deux sources).
 */
export function backendFinancing(p: Pick<ProposalResponse, 'financing'>): ProposalFinancingBlock | null {
  const f = p.financing;
  if (!f || typeof f !== 'object') return null;
  if (!f.cash || !f.credit || typeof f.cash.montant_ttc !== 'number') return null;
  return f;
}

/** WJ32 — Variantes actives « autres tailles » (tableau vide si le devis est isolé). */
export function proposalVariants(p: Pick<ProposalResponse, 'variants'>): ProposalVariantSummary[] {
  return Array.isArray(p.variants) ? p.variants : [];
}

/** WJ114 — note personnelle du vendeur, lue défensivement. */
export interface SellerNote {
  note: string | null;
  name: string | null;
  photoUrl: string | null;
}

/**
 * WJ114 — « décider en 10 secondes » (Storydoc) : la personnalisation
 * (note + identité du vendeur) augmente l'engagement, mais le backend
 * n'expose PAS ENCORE ce bloc aujourd'hui (aucune intégration ERP livrée) —
 * lecture défensive (optional chaining) pour s'allumer sans changement de
 * code le jour où l'ERP le fournira. Renvoie `null` si les TROIS champs sont
 * absents/vides (rien à rendre) ; sinon un objet avec les seuls champs
 * réellement fournis (jamais de valeur fabriquée pour compléter).
 */
export function sellerNote(p: Pick<ProposalResponse, 'seller'>): SellerNote | null {
  const s = p?.seller;
  if (!s || typeof s !== 'object') return null;
  const note = typeof s.note === 'string' && s.note.trim() ? s.note.trim() : null;
  const name = typeof s.name === 'string' && s.name.trim() ? s.name.trim() : null;
  const photoUrl = typeof s.photo_url === 'string' && s.photo_url.trim() ? s.photo_url.trim() : null;
  if (!note && !name && !photoUrl) return null;
  return { note, name, photoUrl };
}

// ── WJ32 · « Et après ? » — timeline des prochaines étapes ───────────────────

export interface NextStep {
  id: string;
  title: string;
  titleAr: string;
  /** WJ43 — variante anglaise (segment marocains-du-monde). */
  titleEn: string;
  body: string;
  bodyAr: string;
  bodyEn: string;
}

/**
 * WJ32 — Les 4 étapes après signature. Les DÉLAIS (48–72 h visite, 7–14 j
 * installation) sont des repères opérationnels standard TAQINOR — libellés
 * comme des fourchettes indicatives, jamais un engagement contractuel daté.
 * Toujours affichée (pas de dépendance à un champ backend) : c'est un
 * processus, pas un chiffre client — rien à masquer.
 */
export function nextSteps(): NextStep[] {
  return [
    {
      id: 'signature',
      title: 'Signature',
      titleAr: 'التوقيع',
      titleEn: 'Signature',
      body: 'Vous signez en ligne ci-dessous. Votre conseiller Taqinor confirme la réception dans la journée.',
      bodyAr: 'توقعون إلكترونياً أدناه، ويؤكد مستشاركم الاستلام خلال اليوم نفسه.',
      bodyEn: 'You sign online below. Your Taqinor advisor confirms receipt the same day.',
    },
    {
      id: 'visite',
      title: 'Visite technique',
      titleAr: 'الزيارة التقنية',
      titleEn: 'Technical visit',
      body: 'Un technicien confirme les mesures sur site sous 48–72 h (délai indicatif).',
      bodyAr: 'يتحقق فني من القياسات في الموقع خلال 48 إلى 72 ساعة (أجل تقريبي).',
      bodyEn: 'A technician confirms the on-site measurements within 48–72 h (indicative timeframe).',
    },
    {
      id: 'installation',
      title: 'Installation',
      titleAr: 'التركيب',
      titleEn: 'Installation',
      body: 'Pose de votre installation par notre équipe, généralement sous 7–14 jours (délai indicatif) selon la disponibilité matériel.',
      bodyAr: 'تركيب منظومتكم بواسطة فريقنا، عادة خلال 7 إلى 14 يوماً (أجل تقريبي) حسب توفر المعدات.',
      bodyEn: 'Our team installs your system, typically within 7–14 days (indicative timeframe) depending on equipment availability.',
    },
    {
      id: 'mise-en-service',
      title: 'Mise en service',
      titleAr: 'التشغيل',
      titleEn: 'Commissioning',
      body: 'Vérification finale, mise en service et remise des documents (garanties, attestations).',
      bodyAr: 'فحص نهائي، تشغيل المنظومة وتسليم الوثائق (الضمانات والشهادات).',
      bodyEn: 'Final check, commissioning, and handover of documents (warranties, certificates).',
    },
  ];
}

// ── WJ32 · « Nos hypothèses » — disclosure sourcée, jamais de valeur inventée ─

export interface AssumptionItem {
  label: string;
  labelAr: string;
  /** WJ43 — variante anglaise. */
  labelEn: string;
  value: string;
  /**
   * WJ43 — la valeur n'avait jusqu'ici AUCUNE traduction (ni AR ni EN) : elle
   * s'affichait en français quelle que soit la langue active. `valueAr`/
   * `valueEn` corrigent cette fuite au passage (même chiffres, texte traduit).
   */
  valueAr: string;
  valueEn: string;
}

/**
 * WJ32 — Hypothèses RÉELLES qui sous-tendent les chiffres de la page, sourcées
 * UNIQUEMENT depuis des champs backend/constantes déjà affichées ailleurs sur
 * la page (jamais une nouvelle valeur inventée ici) :
 *  - tarif : loi 82-21 autoconsommation, dérive 0 % (BILL_INFLATION_RATE) ;
 *  - horizon : SAVINGS_HORIZON_YEARS (25 ans, durée de vie économique retenue —
 *    la garantie de performance panneau va au-delà : 30 ans, cf. warranty.ts) ;
 *  - type d'installation : `quote.inst_type` (résidentiel/industriel/agricole) ;
 *  - financement : programme backend s'il est présent (Tatwir/ISTIDAMA…).
 * Toujours au moins 2 lignes (tarif + horizon sont des constantes du module,
 * jamais absentes) — le bloc n'est donc jamais vide.
 */
export function proposalAssumptions(p: ProposalResponse): AssumptionItem[] {
  const items: AssumptionItem[] = [
    {
      label: 'Cadre tarifaire',
      labelAr: 'الإطار التعريفي',
      labelEn: 'Tariff framework',
      value: 'Autoconsommation basse tension (loi 82-21), tarif ONEE supposé constant (0 % de dérive) — toute hausse réelle ne ferait qu\'augmenter l\'économie.',
      valueAr: 'الاستهلاك الذاتي في التوتر المنخفض (القانون 82-21)، بافتراض تعريفة ONEE ثابتة (0 % تغير) — أي ارتفاع فعلي لن يزيد إلا من التوفير.',
      valueEn: 'Low-voltage self-consumption (law 82-21), assuming a constant ONEE tariff (0 % drift) — any real increase would only raise your savings.',
    },
    {
      label: 'Horizon d\'analyse',
      labelAr: 'أفق التحليل',
      labelEn: 'Analysis horizon',
      value: `${SAVINGS_HORIZON_YEARS} ans — durée de garantie de performance standard d'un panneau photovoltaïque.`,
      valueAr: `${SAVINGS_HORIZON_YEARS} سنة — مدة ضمان الأداء المعيارية للوح الشمسي.`,
      valueEn: `${SAVINGS_HORIZON_YEARS} years — standard performance warranty duration of a solar panel.`,
    },
  ];
  const instType = p.quote?.inst_type;
  if (instType) {
    const label =
      instType === 'agricole'
        ? 'Pompage solaire (dimensionné HMT + débit souhaité)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'Autoconsommation industrielle/commerciale (étude taux de couverture)'
          : 'Résidentiel (simulateur)';
    const labelAr =
      instType === 'agricole'
        ? 'ضخ شمسي (محسوب حسب HMT ومعدل الضخ المرغوب)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'استهلاك ذاتي صناعي/تجاري (دراسة معدل التغطية)'
          : 'سكني (المحاكي)';
    const labelEn =
      instType === 'agricole'
        ? 'Solar pumping (sized on head + desired flow rate)'
        : instType === 'industriel' || instType === 'commercial'
          ? 'Industrial/commercial self-consumption (coverage-rate study)'
          : 'Residential (simulator)';
    items.push({ label: 'Type d\'installation', labelAr: 'نوع التركيب', labelEn: 'Installation type', value: label, valueAr: labelAr, valueEn: labelEn });
  }
  const fin = backendFinancing(p);
  if (fin?.credit?.programme_label) {
    const rate = formatNumber(fin.credit.taux_annuel_pct, 2);
    const years = Math.round(fin.credit.duree_mois / 12);
    items.push({
      label: 'Programme de financement indicatif',
      labelAr: 'برنامج التمويل الإرشادي',
      labelEn: 'Indicative financing programme',
      value: `${fin.credit.programme_label} — taux ${rate} %/an, ${years} ans (à confirmer avec votre banque).`,
      valueAr: `${fin.credit.programme_label} — معدل ${rate} %/سنة، ${years} سنة (يُؤكَّد مع بنككم).`,
      valueEn: `${fin.credit.programme_label} — rate ${rate} %/year, ${years} years (to confirm with your bank).`,
    });
  }
  return items;
}

// ── WJ32 · Accompagnement post-installation ───────────────────────────────────

export interface MonitoringPoint {
  label: string;
  labelAr: string;
  /** WJ43 — variante anglaise. */
  labelEn: string;
}

/**
 * WJ32 — Points d'accompagnement post-installation : FAITS opérationnels
 * (garanties déjà affichées ailleurs sur la page, SAV Taqinor) — pas de
 * chiffre nouveau, aucune dépendance backend (toujours affiché).
 */
export function monitoringPoints(): MonitoringPoint[] {
  return [
    {
      label: 'Suivi de production disponible via l\'application de votre onduleur',
      labelAr: 'تتبع الإنتاج متاح عبر تطبيق العاكس',
      labelEn: 'Production monitoring available via your inverter\'s app',
    },
    {
      label: 'SAV Taqinor joignable sur WhatsApp pour toute question après installation',
      labelAr: 'خدمة ما بعد البيع لتاقينور متاحة عبر واتساب لأي سؤال بعد التركيب',
      labelEn: 'Taqinor after-sales support reachable on WhatsApp for any question after installation',
    },
    {
      label: 'Garanties constructeur actives dès la mise en service (voir « Pourquoi nous faire confiance »)',
      labelAr: 'ضمانات الصانع سارية فور التشغيل',
      labelEn: 'Manufacturer warranties active from commissioning (see "Why trust us")',
    },
  ];
}

// ── WJ32 · FAQ objections (contenu éditorial fixe, pas de dépendance backend) ─

export interface FaqItem {
  id: string;
  question: string;
  questionAr: string;
  /** WJ43 — variante anglaise. */
  questionEn: string;
  answer: string;
  answerAr: string;
  answerEn: string;
}

/** WJ32 — 5 objections fréquentes avant signature, réponses factuelles courtes. */
export function objectionFaq(): FaqItem[] {
  return [
    {
      id: 'panne-reseau',
      question: 'Que se passe-t-il en cas de coupure du réseau électrique ?',
      questionAr: 'ماذا يحدث في حال انقطاع التيار الكهربائي؟',
      questionEn: 'What happens during a power grid outage?',
      answer: 'Une installation sans batterie s\'arrête par sécurité (norme anti-îlotage) ; une installation avec batterie peut continuer à alimenter les circuits prioritaires.',
      answerAr: 'التركيب بدون بطارية يتوقف لأسباب أمنية؛ أما مع البطارية فيمكن أن يستمر تزويد الدارات ذات الأولوية.',
      answerEn: 'A battery-less installation shuts down for safety (anti-islanding standard); a battery-equipped installation can keep powering priority circuits.',
    },
    {
      id: 'entretien',
      question: 'Quel entretien est nécessaire ?',
      questionAr: 'ما هي الصيانة المطلوبة؟',
      questionEn: 'What maintenance is required?',
      answer: 'Un nettoyage occasionnel des panneaux (poussière) et une vérification visuelle annuelle suffisent dans la majorité des cas.',
      answerAr: 'تنظيف الألواح بين الحين والآخر وفحص بصري سنوي يكفيان في أغلب الحالات.',
      answerEn: 'Occasional panel cleaning (dust) and an annual visual check are enough in most cases.',
    },
    {
      id: 'demenagement',
      question: 'Puis-je emporter mon installation si je déménage ?',
      questionAr: 'هل يمكنني نقل التركيب إذا انتقلت للسكن في مكان آخر؟',
      questionEn: 'Can I take my installation with me if I move?',
      answer: 'L\'installation est fixée au bâtiment ; elle valorise généralement le bien lors d\'une revente plutôt que d\'être démontée.',
      answerAr: 'التركيب مثبت بالمبنى؛ وعادة ما يرفع من قيمة العقار عند البيع بدل تفكيكه.',
      answerEn: 'The installation is fixed to the building; it typically raises the property\'s value on resale rather than being removed.',
    },
    {
      id: 'toit-abime',
      question: 'Est-ce que l\'installation abîme la toiture ?',
      questionAr: 'هل يضر التركيب بالسطح؟',
      questionEn: 'Does the installation damage the roof?',
      answer: 'La fixation est étudiée pour respecter l\'étanchéité de votre toiture ; l\'étude technique en amont vérifie la structure porteuse.',
      answerAr: 'يُدرس التثبيت لاحترام عزل السطح؛ وتتحقق الدراسة التقنية المسبقة من متانة البنية الحاملة.',
      answerEn: 'The mounting is engineered to preserve your roof\'s waterproofing; the upfront technical study verifies the load-bearing structure.',
    },
    {
      id: 'garanties',
      question: 'Que couvrent exactement les garanties ?',
      questionAr: 'ماذا تغطي الضمانات بالضبط؟',
      questionEn: 'What exactly do the warranties cover?',
      answer: 'Les garanties constructeur (panneaux/onduleur) couvrent le matériel selon les durées indiquées dans « Pourquoi nous faire confiance » ci-dessous ; la main d\'œuvre Taqinor est couverte séparément selon votre contrat.',
      answerAr: 'تغطي ضمانات الصانع (الألواح والعاكس) المعدات حسب المدد المذكورة أدناه؛ أما اليد العاملة لتاقينور فمشمولة بضمان منفصل حسب عقدكم.',
      answerEn: 'Manufacturer warranties (panels/inverter) cover the equipment for the durations shown in "Why trust us" below; Taqinor\'s labour is covered separately under your contract.',
    },
  ];
}

// ── WJ55/WJ109 · Télémétrie de vue/engagement de la proposition ──────────────
//
// « Le CRM sait QUE le client a lu, mais pas QUAND » : un follow-up envoyé au
// moment où le client rouvre sa proposition (ou vient de faire défiler jusqu'au
// bloc financement) convertit bien mieux qu'une relance calendaire aveugle.
//
// WJ109 — [CORRECTIF DE CORRUPTION DE DONNÉES EN PRODUCTION] Cette télémétrie
// postait auparavant vers le fil lead CRM (`LEAD_WEBHOOK_URL`,
// `apps/crm/webhooks.py`) avec l'idée que le backend « ferait correspondre »
// l'événement à un lead existant via son téléphone. En réalité ce webhook
// traite CHAQUE payload comme une mise à jour de lead : sans nom exploitable
// dans l'événement, il écrase le NOM RÉEL du lead existant par « Lead site
// web » et le retague — donc un client qui se contente d'OUVRIR sa proposition
// corrompait sa propre fiche CRM. Cette télémétrie doit désormais transiter
// EXCLUSIVEMENT par le canal télémétrie/funnel dédié (`FUNNEL_WEBHOOK_URL`,
// le même que `lib/funnelBeacon.ts`), jamais par le webhook de capture de
// lead — voir `pages/api/proposition-track.ts`.

/** Les deux moments suivis (WJ55) : première vue, et défilement jusqu'au bloc financement. */
export type ProposalEngagementEvent = 'proposal_first_view' | 'proposal_scrolled_financing';

export interface ProposalTrackContext {
  reference: string;
  token: string;
  clientPhone?: string | null;
}

/**
 * WJ109 — Payload de TÉLÉMÉTRIE pure (jamais un objet « lead ») : aucun champ
 * qui ressemble à un contact (nom/téléphone) n'y voyage plus — seul un
 * identifiant de corrélation non qualifiant (référence ou token) est inclus,
 * pour permettre un futur rapprochement CÔTÉ LECTURE (jamais une écriture) au
 * moment de l'analyse, sans jamais risquer une écriture de lead par ping.
 */
export interface ProposalTrackPayload {
  event_type: ProposalEngagementEvent;
  reference: string;
  token: string;
  page: string;
}

/**
 * WJ55/WJ109 — Construit le payload envoyé au proxy `/api/proposition-track`,
 * ou `null` quand ni référence ni token ne sont disponibles (rien de
 * corrélable à journaliser). Ce payload est PUREMENT télémétrique : il ne
 * porte plus de téléphone/contact et ne doit JAMAIS être posté vers le webhook
 * de capture de lead (voir la note ci-dessus).
 */
export function buildProposalTrackPayload(
  ctx: ProposalTrackContext,
  event: ProposalEngagementEvent,
): ProposalTrackPayload | null {
  const reference = (ctx.reference ?? '').trim();
  const token = (ctx.token ?? '').trim();
  if (!reference && !token) return null;
  return {
    event_type: event,
    reference,
    token,
    page: `/proposition/${token}`,
  };
}
