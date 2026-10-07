/** Dictionnaire anglais de la page sonde (YBW13) — mêmes clés que le FR. */
import type { DictEn } from '../config';
import type { fr } from './bonjour.fr';

export const en: DictEn<typeof fr> = {
  titre: 'Probe',
  h1: 'Hello',
  langue: 'Language',
};
