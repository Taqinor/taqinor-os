/**
 * ENF19 — constantes communes des pages /parrainage (FR / EN / AR).
 *
 * GATE WG14 — non tranché par le fondateur : ne JAMAIS inventer de chiffre.
 * Dès que WG14 est décidé, ces deux constantes portent la valeur réelle et
 * tout le reste des pages l'affiche automatiquement (3 langues d'un coup).
 */
import { WHATSAPP_LEADS } from './nap';
import { whatsappLink } from './whatsapp';

export const REWARD_AMOUNT_LABEL: string | null = null;
export const REWARD_MILESTONE_LABEL: string | null = null;

// WAUD10 (D-WAUD-3=a) — texte pré-rempli dans la langue de la page ; FR identique.
const TEXTE_PARRAINAGE = {
  fr: 'Bonjour, je souhaite parrainer un proche pour une installation solaire Taqinor.',
  en: 'Hello, I would like to refer someone close to me for a Taqinor solar installation.',
  ar: 'مرحباً، أرغب في إحالة أحد أقاربي لتركيبة شمسية من تاكينور. عافاك تواصلو معايا.',
} as const;
export const waParrainageLocale = (locale: keyof typeof TEXTE_PARRAINAGE) =>
  whatsappLink(WHATSAPP_LEADS, TEXTE_PARRAINAGE[locale]);
export const waParrainage = waParrainageLocale('fr');
