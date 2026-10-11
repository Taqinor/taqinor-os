/**
 * Homepage (YBW61) — same keys as the French one, translated from the
 * approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './accueil.fr';

export const en: DictEn<typeof fr> = {
  titre: 'YanBow — business software',
  description:
    'YanBow builds business software: SolarBow for solar installers, MarketingBow for advertising campaigns, and custom software development.',
  surtitre: 'Software studio',
  cta: 'Book a meeting',
  secondaire: 'Discover the products',
  produits: {
    surtitre: 'Products',
    titre: 'Two built products',
    solarbow: { surtitre: 'For solar installers', lien: 'Discover SolarBow' },
    marketingbow: { surtitre: 'For advertising campaigns', lien: 'Discover MarketingBow' },
  },
  surMesure: {
    surtitre: 'Custom software',
    titre: 'And for the rest, custom software',
    besoin: 'The need',
    prototype: 'The prototype',
    service: 'Putting into service',
    exploitation: 'Operation',
    lien: 'The custom software approach',
  },
  societe: {
    surtitre: 'Company',
    titre: 'Why YanBow',
    lien: 'Who we are',
  },
  appel: {
    titre: 'Let’s talk about your project',
    bouton: 'Book a meeting',
  },
};
