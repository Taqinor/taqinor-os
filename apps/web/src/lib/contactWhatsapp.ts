// ENF19 — les cinq liens WhatsApp de la page contact (FR/EN/AR) : même numéro « leads ».
// WAUD10 (D-WAUD-3=a) : textes pré-remplis dans la langue de la page (l'équipe lit
// AR et EN) ; FR identique à l'octet.
import type { Locale } from '../i18n/config';
import { WHATSAPP_LEADS } from './nap';
import { whatsappLink, regularizationWhatsappText } from './whatsapp';

const TEXTES: Record<Locale, { general: string; rappel: string; visite: string; sav: string }> = {
  fr: {
    // Étude solaire générale.
    general: 'Bonjour, je souhaite une étude pour une installation solaire.',
    // W249 — rappel téléphonique : demande explicitement un rappel (plutôt qu'un devis en ligne).
    rappel: 'Bonjour, pouvez-vous me rappeler par téléphone pour parler de mon projet solaire ?',
    // W285 — visite d'un chantier réel avant de décider.
    visite: 'Bonjour, je souhaite visiter une installation réelle Taqinor avant de me décider.',
    // W339 — SAV / panne d'un client existant, distinct des portes d'acquisition ci-dessus.
    sav: 'Bonjour, je suis déjà client Taqinor et je signale un problème sur mon installation existante (SAV). Merci de me recontacter.',
  },
  en: {
    general: 'Hello, I would like a study for a solar installation.',
    rappel: 'Hello, could you call me back by phone to discuss my solar project?',
    visite: 'Hello, I would like to visit a real Taqinor installation before deciding.',
    sav: 'Hello, I am already a Taqinor customer and I am reporting a problem with my existing installation (after-sales). Please contact me.',
  },
  ar: {
    general: 'مرحباً، أرغب في دراسة لتركيب نظام للطاقة الشمسية. عافاك تواصلو معايا.',
    rappel: 'مرحباً، هل يمكنكم الاتصال بي هاتفياً للحديث عن مشروعي الشمسي؟ عافاك عيطو ليا.',
    visite: 'مرحباً، أرغب في زيارة تركيبة حقيقية لتاكينور قبل أن أقرّر. بغيت نشوف شي تركيبة.',
    sav: 'مرحباً، أنا زبون لدى تاكينور وأبلّغ عن مشكل في تركيبتي الحالية (خدمة ما بعد البيع). المرجو التواصل معي. عافاك تواصلو معايا.',
  },
};

export function contactWhatsappLinks(locale: Locale = 'fr') {
  const t = TEXTES[locale];
  return {
    waGeneral: whatsappLink(WHATSAPP_LEADS, t.general),
    // Régularisation (loi 82-21 / article 33).
    waRegul: whatsappLink(WHATSAPP_LEADS, regularizationWhatsappText(undefined, locale)),
    waRappel: whatsappLink(WHATSAPP_LEADS, t.rappel),
    waVisite: whatsappLink(WHATSAPP_LEADS, t.visite),
    waSav: whatsappLink(WHATSAPP_LEADS, t.sav),
  };
}
