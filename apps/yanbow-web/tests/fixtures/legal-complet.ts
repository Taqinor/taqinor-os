/** Fixture FICTIVE des identités légales (YBW25/YBW28) — jamais affichée par le site. */
import type { Legal } from '../../src/lib/legal';

export const LEGAL_COMPLET: Legal = {
  editeur: { nomExact: 'Fixture Test Ltd', partie: 'angleterre_galles', numero: 'TEST0001', siege: '1 Test Street, Testville', tva: 'GBTEST001' },
  maroc: {
    denomination: 'Fixture Test',
    capital: 'CAPITAL-TEST',
    siege: '2 rue du Test, Testville',
    rc: 'RC-TEST',
    ice: 'ICE-TEST',
    identifiantFiscal: 'IF-TEST',
    gerant: 'Gérant Test',
  },
  commun: {
    email: 'test@example.invalid',
    telephone: '+00 0 00 00 00 00',
    directeurPublication: 'Directeur Test',
    hebergeur: {
      valeur: { nom: 'Hébergeur Test', adresse: '3 Test Road', telephone: '+00 1' },
      urlSource: 'https://example.invalid/legal',
      dateLecture: '2026-10-07',
    },
    recepissesCndp: ['CNDP-TEST'],
    representantUe: 'Représentant Test',
    responsableTraitement: 'editeur',
    garantiesTransferts: { fr: 'Garanties de test.', en: 'Test safeguards.' },
  },
};
