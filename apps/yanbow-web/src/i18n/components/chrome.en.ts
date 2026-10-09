/**
 * Shared chrome dictionary (YBW60) — SKELETON: same keys as the French one,
 * empty strings. No English copy before Reda approves the French text
 * (YBWM13); filled by YBW70 from the approved French.
 */
import type { DictEn } from '../config';
import type { fr } from './chrome.fr';

export const en: DictEn<typeof fr> = {
  evitement: '',
  accueil: '',
  nav: {
    aria: '',
    ariaMobile: '',
    menu: '',
    surMesure: '',
    societe: '',
    rdv: '',
  },
  pied: {
    aria: '',
    nav: '',
  },
  capture: {
    attente: '',
    note: '',
  },
};
