/**
 * Custom software page (YBW64) — same keys as the French one, translated from
 * the approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './sur-mesure.fr';

export const en: DictEn<typeof fr> = {
  titre: 'Custom software — YanBow',
  description: 'YanBow builds custom software for companies: need, prototype, putting into service, operation.',
  surtitre: 'Custom software',
  h1: 'The software your company needs',
  cta: 'Book a meeting',
  demarche: {
    surtitre: 'The approach',
    titre: 'Four steps, in this order',
    besoin: { titre: 'The need', detail: 'We start from how you work and from what is stuck today.' },
    prototype: { titre: 'The prototype', detail: 'A first working piece of software, to try before going further.' },
    service: { titre: 'Putting into service', detail: 'The software is installed and used by your teams.' },
    exploitation: { titre: 'Operation', detail: 'We maintain it and evolve it with you.' },
  },
  preuve: {
    surtitre: 'The proof',
    titre: 'Two built products',
    solarbow: 'Discover SolarBow',
    marketingbow: 'Discover MarketingBow',
  },
  appel: {
    titre: 'Let’s talk about your need',
    bouton: 'Book a meeting',
  },
};
