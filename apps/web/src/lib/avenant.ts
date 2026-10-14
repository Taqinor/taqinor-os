/**
 * VNT72 — l'avenant à signer (V2 d'un prix négocié) sur la page publique
 * /proposition. Module PUR : lit UNIQUEMENT la clé `avenant` servie par
 * `proposal_data` (contrat `src/contract_samples/proposal_data.json`, VNT2/VNT61) :
 *
 *   avenant = { a_signer: bool, remplace: { reference }, signe_le: ISO | null }
 *
 * Clé ABSENTE (jamais null) hors avenant → `null` ici, aucun bandeau. Aucun
 * champ inventé, aucun calcul : la page affiche ce que le serveur dit.
 */

export type AvenantEtat = 'a_signer' | 'signe';

export interface AvenantPublic {
  etat: AvenantEtat;
  /** Référence de la version remplacée (« Avenant à <V1> »), `null` si illisible. */
  reference: string | null;
  /** Date de signature `jj/mm/aaaa` (fuseau Casablanca), `null` tant que non signé. */
  signeLe: string | null;
}

function dateCourte(iso: string): string | null {
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return null;
  const p = new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Africa/Casablanca',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).formatToParts(t);
  const g = (type: string): string => p.find((x) => x.type === type)?.value ?? '';
  return `${g('day')}/${g('month')}/${g('year')}`;
}

/** Lecture défensive de `avenant` ; `null` si absent ou incohérent. */
export function resolveAvenant(p: unknown): AvenantPublic | null {
  const brut = p && typeof p === 'object' ? (p as Record<string, unknown>).avenant : null;
  if (!brut || typeof brut !== 'object') return null;
  const a = brut as Record<string, unknown>;
  if (typeof a.a_signer !== 'boolean') return null;
  const remplace = a.remplace && typeof a.remplace === 'object' ? (a.remplace as Record<string, unknown>) : null;
  const ref = typeof remplace?.reference === 'string' ? remplace.reference.trim() : '';
  const reference = ref || null;
  if (a.a_signer) return { etat: 'a_signer', reference, signeLe: null };
  const signeLe = typeof a.signe_le === 'string' ? dateCourte(a.signe_le) : null;
  // Ni à signer, ni daté : état incohérent → rien (on n'invente pas une signature).
  return signeLe ? { etat: 'signe', reference, signeLe } : null;
}
