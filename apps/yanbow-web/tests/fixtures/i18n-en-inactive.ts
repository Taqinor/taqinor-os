// Fixture YBW13 (compilée par tests/i18n.test.ts, exclue de tsconfig.check.json).
import type { DictEn } from '../../src/i18n/config';

const fr = { titre: 'Titre', bloc: { texte: 'Texte' } } as const;

// Anglais INACTIF : un squelette vide est accepté (aucun anglais exigé avant YBW70).
export const en: DictEn<typeof fr, ['fr']> = {};
