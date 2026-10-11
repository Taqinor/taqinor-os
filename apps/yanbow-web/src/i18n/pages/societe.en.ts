/**
 * Company page (YBW65) — same keys as the French one, translated from the
 * approved French (YBWM13, YBW70). No new statement. `{nom}`, `{partie}`,
 * `{numero}`, `{forme}` are replaced from legal.ts.
 */
import type { DictEn } from '../config';
import type { fr } from './societe.fr';

export const en: DictEn<typeof fr> = {
  titre: 'The company — YanBow',
  description: 'YanBow builds business software for companies: SolarBow, MarketingBow and custom software development.',
  surtitre: 'Company',
  h1: 'Who we are',
  nom: {
    surtitre: 'The name',
    titre: 'Why YanBow',
  },
  entites: {
    titre: 'The companies',
    editeur: 'This site is published by {nom}, a company registered in {partie} under number {numero}.',
    maroc: 'In Morocco, clients sign with {nom}, {forme}.',
  },
  origine: {
    surtitre: 'Where SolarBow comes from',
    titre: 'SolarBow',
  },
  offre: {
    surtitre: 'What we do',
    titre: 'Two products and custom software',
    surMesure: 'Custom software',
  },
  appel: {
    titre: 'Let’s talk about your project',
    bouton: 'Book a meeting',
  },
};
