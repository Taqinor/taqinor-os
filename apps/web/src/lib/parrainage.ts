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

// Le texte pré-rempli reste en français (il arrive à l'équipe commerciale
// francophone) — même convention que les autres liens WhatsApp EN/AR.
export const waParrainage = whatsappLink(
  WHATSAPP_LEADS,
  'Bonjour, je souhaite parrainer un proche pour une installation solaire Taqinor.',
);
