/**
 * Shared chrome dictionary (YBW60) — same keys as the French one, translated
 * from the approved French (YBWM13, YBW70). No new statement.
 */
import type { DictEn } from '../config';
import type { fr } from './chrome.fr';

export const en: DictEn<typeof fr> = {
  evitement: 'Skip to content',
  accueil: 'YanBow, home',
  nav: {
    aria: 'Main navigation',
    ariaMobile: 'Navigation',
    menu: 'Menu',
    surMesure: 'Custom software',
    societe: 'Company',
    rdv: 'Book a meeting',
  },
  pied: {
    aria: 'Footer',
    nav: 'Site map',
  },
  capture: {
    attente: 'Screenshot in preparation',
    note: 'Real software screen, fictional company, cropped to the useful area.',
  },
};
