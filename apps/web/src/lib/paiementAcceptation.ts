/**
 * ADEV53 (C-ADEV-023) — le succès post-signature de /proposition.
 *
 * La réponse 200 de l'acceptation porte `paiement` (contrat partagé
 * `contract_samples/proposal_accept.json` › `reponse_200.paiement`, sortie réelle de
 * `public/paiement_views._deposit_success_payload`) : l'acompte (tranche 1 servie par
 * l'ERP), le RIB de la société émettrice et `declare_url` (POST `/virement/`, relayé par
 * le proxy same-origin `/api/proposition-virement`).
 *
 * ZÉRO CHIFFRE INVENTÉ : l'acompte et le RIB sont LUS ; absents ou illisibles, la ligne
 * n'est pas rendue — jamais un montant ni un numéro de repli. Aucun lien carte : la route
 * `pay-card` n'existe pas (le serveur ne sert plus `card_payment_url`).
 */
import { formatMADCentimes, type Lbl3 } from './proposition';

/** `reponse_200.paiement` du contrat `proposal_accept.json`. */
export interface PaiementAcceptation {
  acompte_ttc: string | null;
  pourcentage: string | null;
  rib: string;
  message: string;
  declare_url: string;
}

/** Ce que l'écran de succès affiche ; `null` quand il n'y a rien à montrer. */
export interface PaiementVue {
  /** « 3 240,00 MAD », ou null si le serveur n'a servi aucun acompte. */
  acompte: string | null;
  /** « 30 » (virgule décimale FR), seulement avec un acompte. */
  pourcentage: string | null;
  /** RIB de la société émettrice, ou null (champ absent — jamais un numéro de repli). */
  rib: string | null;
  /** Message de protection de l'acompte servi par l'ERP, ou null. */
  message: string | null;
  /** Vrai si le serveur sert l'URL de déclaration `/virement/`. */
  peutDeclarer: boolean;
}

function texte(v: unknown): string {
  if (typeof v === 'string') return v.trim();
  return typeof v === 'number' && Number.isFinite(v) ? String(v) : '';
}

/** Lit `paiement` d'une réponse d'acceptation (succès) ; `null` si absent ou mal formé. */
export function lirePaiementAcceptation(payload: unknown): PaiementAcceptation | null {
  const corps = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : null;
  const brut = corps?.paiement;
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return null;
  const p = brut as Record<string, unknown>;
  return {
    acompte_ttc: texte(p.acompte_ttc) || null,
    pourcentage: texte(p.pourcentage) || null,
    rib: texte(p.rib),
    message: texte(p.message),
    declare_url: texte(p.declare_url),
  };
}

/** Met en forme le bloc de paiement pour l'écran de succès (fonction pure, testée sur le contrat). */
export function paiementVue(p: PaiementAcceptation | null | undefined): PaiementVue | null {
  if (!p) return null;
  const montant = Number(p.acompte_ttc ?? '');
  const acompte = p.acompte_ttc && Number.isFinite(montant) && montant > 0 ? formatMADCentimes(montant) : null;
  const pct = Number(p.pourcentage ?? '');
  const pourcentage =
    acompte && p.pourcentage && Number.isFinite(pct) && pct > 0 ? String(Math.round(pct * 100) / 100).replace('.', ',') : null;
  const rib = p.rib || null;
  const peutDeclarer = /\/virement\/$/.test(p.declare_url);
  if (!acompte && !rib) return null;
  return { acompte, pourcentage, rib, message: p.message || null, peutDeclarer };
}

/** URL backend de la déclaration de virement (même convention que `acceptEndpoint`). */
export function virementEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/proposal/${encodeURIComponent(token)}/virement/`;
}

export interface VirementResult {
  ok: boolean;
  status: number;
  detail: string;
  /** Déclaration déjà enregistrée dans l'heure (idempotence serveur). */
  already?: boolean;
}

/** Normalise (statut, JSON amont) ; `otp_required` reste lisible pour la page. */
export function normalizeVirementResponse(status: number, payload: unknown): VirementResult {
  const corps = payload && typeof payload === 'object' ? (payload as Record<string, unknown>) : {};
  const detail = texte(corps.detail);
  const ok = status >= 200 && status < 300;
  return { ok, status, detail, ...(ok && corps.already === true ? { already: true } : {}) };
}

export const VIREMENT_MSG = {
  succes: {
    fr: 'Merci ! Votre déclaration a été transmise à votre conseiller.',
    en: 'Thank you! Your notice has been sent to your advisor.',
    ar: 'شكراً! تم إرسال تصريحكم إلى مستشاركم.',
  },
  otp: {
    fr: 'Votre accès a expiré : rechargez la page et saisissez à nouveau votre code.',
    en: 'Your access has expired: reload the page and enter your code again.',
    ar: 'انتهت صلاحية الوصول: أعيدوا تحميل الصفحة وأدخلوا الرمز من جديد.',
  },
  generique: {
    fr: 'La déclaration n’a pas pu être envoyée. Réessayez, ou contactez votre conseiller.',
    en: 'The notice could not be sent. Try again, or contact your advisor.',
    ar: 'تعذّر إرسال التصريح. أعيدوا المحاولة أو تواصلوا مع مستشاركم.',
  },
} satisfies Record<string, Lbl3>;

/** Message à montrer après la déclaration (le serveur répond 200 / 403 / 404). */
export function virementMessage(r: Pick<VirementResult, 'ok' | 'status' | 'detail'>): Lbl3 {
  if (r.ok) return VIREMENT_MSG.succes;
  if (r.status === 403 && r.detail === 'otp_required') return VIREMENT_MSG.otp;
  return VIREMENT_MSG.generique;
}
