/**
 * ADEV104 (C-L3-LIEN-10) — le REÇU de la signature et le 409 « contenu changé »
 * (ADEV51) de /proposition, sans dépendance : `proposition.ts` les lit et les ré-exporte.
 *
 * Contrat partagé `contract_samples/proposal_accept.json` › `reponse_200.recu` : DEUX
 * empreintes NOMMÉES — `empreinte_lue` (le défi que la page a renvoyé : ce que CE lien a
 * montré) et `empreinte_scellee` (`DevisSignature.content_hash`, le sceau stocké, calculé
 * avec le lien). `empreinte_contenu` reste servie un cycle comme alias d'`empreinte_scellee` :
 * lue seulement en repli, jamais confondue avec le défi.
 */

/** ADEV51 — le 409 qui dit « la proposition a changé depuis votre lecture ». */
export const CODE_EMPREINTE_PERIMEE = 'empreinte_perimee';

/** ADEV51 — vrai quand le serveur refuse la signature parce que le contenu a changé : la page recharge. */
export function estEmpreintePerimee(status: number, payload: unknown): boolean {
  const code = (payload as { code?: unknown } | null | undefined)?.code;
  return status === 409 && code === CODE_EMPREINTE_PERIMEE;
}

/** `reponse_200.recu` : horodatage, défi lu, sceau stocké, SHA-256 du PDF signé. */
export interface RecuSignature {
  /** ISO, ou null si le serveur n'a servi aucun horodatage. */
  signe_le: string | null;
  /** Le défi renvoyé par la page (vide s'il n'a pas été envoyé). */
  empreinte_lue: string;
  /** Le sceau stocké (`content_hash`). */
  empreinte_scellee: string;
  /** SHA-256 des octets du PDF signé remis (vide tant qu'il n'est pas stocké). */
  empreinte_pdf: string;
}

function texte(v: unknown): string {
  return typeof v === 'string' ? v.trim() : '';
}

/** Lit `recu` d'une réponse d'acceptation (succès) ; `null` si absent ou mal formé. */
export function lireRecuSignature(brut: unknown): RecuSignature | null {
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return null;
  const r = brut as Record<string, unknown>;
  return {
    signe_le: texte(r.signe_le) || null,
    empreinte_lue: texte(r.empreinte_lue),
    empreinte_scellee: texte(r.empreinte_scellee) || texte(r.empreinte_contenu),
    empreinte_pdf: texte(r.empreinte_pdf),
  };
}
