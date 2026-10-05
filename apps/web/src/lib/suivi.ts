/**
 * WJ115 — Logique PURE du suivi de chantier post-signature (`/suivi/<token>`).
 *
 * Mirroir volontaire de `lib/proposition.ts` : un module sans DOM, sans réseau,
 * testable sous vitest, que la page `/suivi/[token].astro` (frontmatter Astro,
 * SSR) est seule à appeler pour construire son modèle d'affichage. Le backend
 * (QX34, endpoint `GET /api/django/ventes/suivi/<token>/`) ne renvoie JAMAIS de
 * prix d'achat/marge ni de donnée non publique — ce module ne lit donc que le
 * contrat public documenté ci-dessous.
 *
 * DISCIPLINE « ZÉRO CHIFFRE/DATE INVENTÉ » : une étape sans `date` (ou dont la
 * `date` n'est pas un ISO parsable) n'affiche jamais de date fabriquée ;
 * `buildTimeline` se contente alors d'omettre le champ. Contrat serveur :
 * `backend/.../ventes/contract_samples/suivi_public.json` (ADOC112).
 */

/** Une étape du suivi telle que renvoyée par le backend (contrat QX34). */
export interface SuiviMilestone {
  key: string;
  label: string;
  done: boolean;
  date: string | null;
}

/** Réponse complète de GET /api/django/ventes/suivi/<token>/. */
export interface SuiviResponse {
  reference: string;
  /** Horodatage TECHNIQUE de la réponse — JAMAIS affiché comme « mis à jour ». */
  generated_at?: string;
  /** ADOC130 — date ISO du jalon fait le plus récent, `null` si aucun. */
  mis_a_jour_le?: string | null;
  milestones: SuiviMilestone[];
}

/**
 * Construit l'URL backend de lecture du suivi à partir d'une base API et d'un
 * token. Même convention EXACTE que `proposalEndpoint` (lib/proposition.ts) :
 * base sans slash final, token encodé (segment de chemin).
 */
export function suiviEndpoint(apiBase: string, token: string): string {
  const base = (apiBase || 'https://api.taqinor.ma').replace(/\/+$/, '');
  return `${base}/api/django/ventes/suivi/${encodeURIComponent(token)}/`;
}

// ── Libellés arabes des étapes (le backend ne fournit que le FR) ────────────

/**
 * WJ115 — Libellés AR par clé d'étape. INTENTIONNELLEMENT une table fermée sur
 * les 5 clés du contrat backend documenté (accepte/acompte/materiel/
 * installation/facture) : une clé future absente d'ici retombe sur le libellé
 * FR envoyé par le backend plutôt que sur un texte arabe inventé.
 */
const MILESTONE_LABELS_AR: Record<string, string> = {
  accepte: 'تم قبول العرض',
  acompte: 'تم استلام العربون',
  materiel: 'تم طلب المعدات',
  installation: 'التركيب',
  facture: 'تمت الفوترة',
};

/** Libellé AR d'une étape (repli sur le libellé FR backend si clé inconnue). */
export function milestoneLabelAr(m: Pick<SuiviMilestone, 'key' | 'label'>): string {
  return MILESTONE_LABELS_AR[m.key] ?? m.label;
}

// ── Garde-fou date : une chaîne de statut chantier n'est jamais une date ────

/**
 * Vrai si `raw` ressemble à une date/horodatage ISO 8601 parsable
 * (`YYYY-MM-DD` ou `YYYY-MM-DDTHH:mm...`). Le backend peut faire voyager, pour
 * la clé `installation`, une chaîne de STATUT chantier (ex. "planifie") dans
 * ce même champ `date` — ce garde-fou empêche de jamais l'afficher/formater
 * comme si c'était une date.
 */
export function isIsoDateString(raw: string | null | undefined): raw is string {
  if (!raw || typeof raw !== 'string') return false;
  if (!/^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2})?/.test(raw.trim())) return false;
  const dt = new Date(raw);
  return !Number.isNaN(dt.getTime());
}

/** Formate une date ISO en `JJ/MM/AAAA` (FR et AR — chiffres occidentaux, LTR). */
export function formatSuiviDate(raw: string | null | undefined): string | null {
  if (!isIsoDateString(raw)) return null;
  const dt = new Date(raw);
  const dd = String(dt.getUTCDate()).padStart(2, '0');
  const mm = String(dt.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = dt.getUTCFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

// ── Modèle d'affichage (timeline) ───────────────────────────────────────────

export type SuiviLang = 'fr' | 'ar';

export interface SuiviStep {
  key: string;
  /** Libellé localisé (FR = tel que fourni par le backend ; AR = table ci-dessus). */
  label: string;
  done: boolean;
  /** Date formatée `JJ/MM/AAAA`, ou `null` si absente/non ISO (ex. statut chantier). */
  dateLabel: string | null;
  /** Vrai pour la PREMIÈRE étape non terminée (celle « en cours »). */
  current: boolean;
}

/**
 * WJ115 — Construit le modèle d'affichage de la timeline de suivi. Honnête par
 * construction :
 *  - `milestones` absent/vide → tableau vide (la page affiche alors un état
 *    « aucune étape disponible », jamais une timeline inventée) ;
 *  - `current` = la première étape avec `done === false` (aucune étape « en
 *    cours » n'est marquée si TOUTES sont déjà faites, ou si AUCUNE ne l'est
 *    encore mais qu'on ne veut pas sur-affirmer — voir note ci-dessous) ;
 *  - `dateLabel` ne rend JAMAIS une chaîne de statut (`installation` peut
 *    porter un statut chantier dans `date` — `formatSuiviDate` retombe sur
 *    `null` pour toute valeur non-ISO).
 */
export function buildTimeline(data: Pick<SuiviResponse, 'milestones'>, lang: SuiviLang): SuiviStep[] {
  const milestones = Array.isArray(data?.milestones) ? data.milestones : [];
  let currentAssigned = false;
  return milestones.map((m) => {
    const done = m?.done === true;
    const isCurrent = !done && !currentAssigned;
    if (isCurrent) currentAssigned = true;
    return {
      key: typeof m?.key === 'string' ? m.key : '',
      label: lang === 'ar' ? milestoneLabelAr(m) : (typeof m?.label === 'string' ? m.label : ''),
      done,
      dateLabel: formatSuiviDate(m?.date ?? null),
      current: isCurrent,
    };
  });
}

// ── ADOC132 — « Mis à jour le » : la vraie date de la dernière évolution ────

/**
 * Libellés « Mis à jour le JJ/MM/AAAA » (FR + AR) construits UNIQUEMENT depuis
 * `mis_a_jour_le` — jamais depuis `generated_at` (horodatage technique de la
 * réponse : il vaut « maintenant » à chaque lecture). `null` si la date est
 * absente/null/non ISO : la page n'affiche alors aucune ligne « Mis à jour ».
 */
export function libelleMiseAJour(
  data: Pick<SuiviResponse, 'mis_a_jour_le'> | null | undefined,
): { fr: string; ar: string; date: string } | null {
  const date = formatSuiviDate(data?.mis_a_jour_le ?? null);
  if (!date) return null;
  return { fr: `Mis à jour le ${date}`, ar: `آخر تحديث بتاريخ ${date}`, date };
}

// ── ADOC133 — état d'erreur du suivi (refus OTP vs introuvable vs panne) ────

/** Détail machine du refus 403 quand le lien exige un code non vérifié. */
export const SUIVI_OTP_DETAIL = 'otp_required';

export type EtatErreurSuivi = 'otp' | 'introuvable' | 'indisponible';

/**
 * Classe une réponse non-OK de l'endpoint de suivi : 403 `otp_required` → écran
 * de saisie du code ; 404 → lien introuvable/expiré ; tout le reste (autre 403,
 * 5xx, 429…) → indisponible. Pure : aucune I/O.
 */
export function etatErreurSuivi(status: number, detail: string | null | undefined): EtatErreurSuivi {
  if (status === 403 && (detail ?? '').trim() === SUIVI_OTP_DETAIL) return 'otp';
  if (status === 404) return 'introuvable';
  return 'indisponible';
}
