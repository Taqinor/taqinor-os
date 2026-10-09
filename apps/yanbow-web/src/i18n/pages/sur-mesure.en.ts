/**
 * Custom software page (YBW64) — SKELETON: same keys as the French one, empty
 * strings. No English before Reda approves the French (YBWM13); filled by YBW70.
 */
import type { DictEn } from '../config';
import type { fr } from './sur-mesure.fr';

export const en: DictEn<typeof fr> = {
  titre: '',
  description: '',
  surtitre: '',
  h1: '',
  cta: '',
  demarche: {
    surtitre: '',
    titre: '',
    besoin: { titre: '', detail: '' },
    prototype: { titre: '', detail: '' },
    service: { titre: '', detail: '' },
    exploitation: { titre: '', detail: '' },
  },
  preuve: {
    surtitre: '',
    titre: '',
    solarbow: '',
    marketingbow: '',
  },
  appel: {
    titre: '',
    bouton: '',
  },
};
