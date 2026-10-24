/**
 * L3 lien public (24/10/2026) — signature B2B de la proposition (ADEV95).
 *
 * Module séparé parce que `proposition.ts` est un fichier-mur (garde C20 : un
 * fichier de plus de 2 000 lignes ne grossit pas) ; `proposition.ts` délègue ici
 * la validation et la mise en forme du bloc `entreprise` (contrat partagé
 * `acceptation_entreprise.json`).
 *
 * Devis commercial / industriel (D-CIQ-11) : raison sociale, qualité, ICE, plus
 * le nom du signataire (celui tapé pour signer), son e-mail et l'attestation
 * « j'agis en la qualité indiquée et j'ai le pouvoir d'engager la société ».
 * Le serveur revalide tout ; un ICE différent de celui que le client porte déjà
 * répond 409 `ice_divergent` (jamais accepté en silence).
 */
import type { SignEntreprise, SignFormState, SignValidation } from './proposition';

/** Forme d'e-mail minimale (le serveur applique la règle Django complète). */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Le bloc `entreprise` nettoyé pour le corps d'acceptation, ou `null` sans saisie
 * (résidentiel : corps inchangé). `signataire_nom` = le nom tapé pour signer.
 */
export function entrepriseNettoyee(e: SignEntreprise | null | undefined, nom: string): SignEntreprise | null {
  if (!e) return null;
  const entreprise: SignEntreprise = {
    raison_sociale: (e.raison_sociale ?? '').trim(),
    signataire_qualite: (e.signataire_qualite ?? '').trim(),
    ice: (e.ice ?? '').trim(),
  };
  if (!entreprise.raison_sociale && !entreprise.signataire_qualite && !entreprise.ice) return null;
  if (e.signataire_email !== undefined || e.pouvoir_engager !== undefined) {
    entreprise.signataire_nom = (nom ?? '').trim();
    entreprise.signataire_email = (e.signataire_email ?? '').trim();
    entreprise.pouvoir_engager = e.pouvoir_engager === true;
  }
  return entreprise;
}

/**
 * Validation côté client du bloc `entreprise` d'un devis C&I (le serveur revalide) :
 * `null` quand tout est rempli, sinon l'erreur qui NOMME le champ fautif.
 */
export function validerEntreprise(form: SignFormState): SignValidation | null {
  const e = form.entreprise ?? { raison_sociale: '', signataire_qualite: '', ice: '' };
  if (!(e.raison_sociale ?? '').trim()) {
    return { valid: false, error: 'Veuillez saisir la raison sociale de l’entreprise.', champ: 'entreprise.raison_sociale' };
  }
  if (!(e.signataire_qualite ?? '').trim()) {
    return { valid: false, error: 'Veuillez indiquer votre qualité (gérant, DAF, DG…).', champ: 'entreprise.signataire_qualite' };
  }
  if (!(e.ice ?? '').trim()) {
    return { valid: false, error: 'Veuillez saisir l’ICE de l’entreprise.', champ: 'entreprise.ice' };
  }
  if (!EMAIL_RE.test((e.signataire_email ?? '').trim())) {
    return { valid: false, error: 'Veuillez saisir votre e-mail professionnel.', champ: 'entreprise.signataire_email' };
  }
  if (e.pouvoir_engager !== true) {
    return {
      valid: false,
      error: 'Veuillez attester que vous avez le pouvoir d’engager la société.',
      champ: 'entreprise.pouvoir_engager',
    };
  }
  return null;
}

/** ADEV95 — le 409 qui dit « l'ICE saisi n'est pas celui que nous avons pour votre société ». */
export const CODE_ICE_DIVERGENT = 'ice_divergent';

/** ADEV95 — vrai quand le serveur refuse la signature pour un ICE divergent (jamais un succès). */
export function estIceDivergent(status: number, payload: unknown): boolean {
  const code = (payload as { code?: unknown } | null | undefined)?.code;
  return status === 409 && code === CODE_ICE_DIVERGENT;
}
