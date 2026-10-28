/**
 * RWEB9 — messages d'erreur du formulaire de signature dans la langue de la page
 * (FR / EN / AR). `validateSign` et `propositionB2b.validerEntreprise` portent le
 * FR dans `error` et, quand ils les fournissent, `errorEn` / `errorAr` : la page
 * les lit, sinon elle retombe sur le FR (jamais un message vide).
 */
export type LangueSignature = 'fr' | 'en' | 'ar';

export interface MessageTraduit {
  error: string | null;
  errorEn?: string | null;
  errorAr?: string | null;
}

export function messageEnLangue(m: MessageTraduit, langue: LangueSignature, repli = 'Formulaire incomplet.'): string {
  const traduit = langue === 'en' ? m.errorEn : langue === 'ar' ? m.errorAr : null;
  return traduit || m.error || repli;
}

export const ERREUR_ACCORD: Required<MessageTraduit> = {
  error: 'Veuillez accepter la proposition et les conditions générales pour signer.',
  errorEn: 'Please accept the proposal and the terms and conditions to sign.',
  errorAr: 'يُرجى قبول العرض والشروط العامة للتوقيع.',
};

export const ERREUR_TYPE_MODIFICATION: Required<MessageTraduit> = {
  error: 'Veuillez choisir le type de modification souhaitée.',
  errorEn: 'Please choose the type of change you would like.',
  errorAr: 'يُرجى اختيار نوع التعديل المطلوب.',
};
