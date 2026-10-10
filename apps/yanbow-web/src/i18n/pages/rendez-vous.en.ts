/**
 * Book-a-meeting page (YBW66) — same keys as the French one, translated from
 * the approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './rendez-vous.fr';

export const en: DictEn<typeof fr> = {
  titre: 'Book a meeting — YanBow',
  description: 'Request a meeting with YanBow: SolarBow, MarketingBow or custom software development.',
  surtitre: 'Meeting',
  h1: 'Book a meeting',
  intro: 'Tell us who you are and what you need.',
  ensuite: {
    titre: 'What happens next',
  },
  whatsapp: 'Message us on WhatsApp',
};
