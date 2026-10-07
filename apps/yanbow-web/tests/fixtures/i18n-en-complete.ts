// Fixture YBW13 (compilée par tests/i18n.test.ts, exclue de tsconfig.check.json).
import type { DictEn } from '../../src/i18n/config';

const fr = { titre: 'Titre', bloc: { texte: 'Texte' } } as const;

// Anglais ACTIF + toutes les clés : doit compiler.
export const en: DictEn<typeof fr, ['fr', 'en']> = { titre: 'Title', bloc: { texte: 'Text' } };
