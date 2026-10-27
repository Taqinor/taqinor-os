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
import type { SignChamp, SignEntreprise, SignFormState, SignValidation } from './proposition';

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
    ice: normaliserIce(e.ice),
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
 * CPRW7 — une validation avec ses messages dans les trois langues. `error` (FR) reste le champ lu
 * par `SignValidation` ; `errorEn` / `errorAr` s'y AJOUTENT (la page les adoptera : tâche RWEB).
 */
export interface SignValidationB2b extends SignValidation {
  errorEn: string;
  errorAr: string;
}

/** ICE : séparateurs courants (espaces, points, tirets) retirés — la saisie reste libre, la valeur envoyée est nette. */
export function normaliserIce(valeur: string | null | undefined): string {
  const chiffres = (valeur ?? '')
    .replace(/[٠-٩]/g, (c) => String(c.charCodeAt(0) - 0x0660))
    .replace(/[۰-۹]/g, (c) => String(c.charCodeAt(0) - 0x06f0));
  return chiffres.trim().replace(/^\s*ICE\s*[:°n.\-]*\s*/i, '').replace(/[\s.\-_/\u00a0\u202f‐-―]/g, '');
}

const ICE_RE = /^\d{15}$/;

function erreurChamp(
  champ: SignChamp,
  error: string,
  errorEn: string,
  errorAr: string,
): SignValidationB2b {
  return { valid: false, error, errorEn, errorAr, champ };
}

/**
 * Validation côté client du bloc `entreprise` d'un devis C&I (le serveur revalide) :
 * `null` quand tout est rempli, sinon l'erreur qui NOMME le champ fautif (FR / EN / AR).
 */
export function validerEntreprise(form: SignFormState): SignValidationB2b | null {
  const e = form.entreprise ?? { raison_sociale: '', signataire_qualite: '', ice: '' };
  if (!(e.raison_sociale ?? '').trim()) {
    return erreurChamp(
      'entreprise.raison_sociale',
      'Veuillez saisir la raison sociale de l’entreprise.',
      'Please enter the company name.',
      'يرجى إدخال اسم الشركة (الاسم التجاري).',
    );
  }
  if (!(e.signataire_qualite ?? '').trim()) {
    return erreurChamp(
      'entreprise.signataire_qualite',
      'Veuillez indiquer votre qualité (gérant, DAF, DG…).',
      'Please state your position (manager, finance director, CEO…).',
      'يرجى ذكر صفتكم (مسير، مدير مالي، مدير عام…).',
    );
  }
  const ice = normaliserIce(e.ice);
  if (!ice) {
    return erreurChamp(
      'entreprise.ice',
      'Veuillez saisir l’ICE de l’entreprise.',
      'Please enter the company’s ICE number.',
      'يرجى إدخال رقم ICE الخاص بالشركة.',
    );
  }
  if (!ICE_RE.test(ice)) {
    return erreurChamp(
      'entreprise.ice',
      'L’ICE doit comporter exactement 15 chiffres.',
      'The ICE number must have exactly 15 digits.',
      'يجب أن يتكون رقم ICE من 15 رقمًا بالضبط.',
    );
  }
  if (!EMAIL_RE.test((e.signataire_email ?? '').trim())) {
    return erreurChamp(
      'entreprise.signataire_email',
      'Veuillez saisir votre e-mail professionnel.',
      'Please enter your business email.',
      'يرجى إدخال بريدكم الإلكتروني المهني.',
    );
  }
  if (e.pouvoir_engager !== true) {
    return erreurChamp(
      'entreprise.pouvoir_engager',
      'Veuillez attester que vous avez le pouvoir d’engager la société.',
      'Please confirm that you have the authority to bind the company.',
      'يرجى التأكيد على أن لديكم صلاحية إلزام الشركة.',
    );
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
