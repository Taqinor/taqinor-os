/**
 * Homepage (YBW61) — SKELETON: same keys as the French one, empty strings.
 * No English before Reda approves the French (YBWM13); filled by YBW70.
 */
import type { DictEn } from '../config';
import type { fr } from './accueil.fr';

export const en: DictEn<typeof fr> = {
  titre: '',
  description: '',
  surtitre: '',
  cta: '',
  secondaire: '',
  produits: {
    surtitre: '',
    titre: '',
    solarbow: { surtitre: '', lien: '' },
    marketingbow: { surtitre: '', lien: '' },
  },
  surMesure: {
    surtitre: '',
    titre: '',
    besoin: '',
    prototype: '',
    service: '',
    exploitation: '',
    lien: '',
  },
  societe: {
    surtitre: '',
    titre: '',
    lien: '',
  },
  appel: {
    titre: '',
    bouton: '',
  },
};
