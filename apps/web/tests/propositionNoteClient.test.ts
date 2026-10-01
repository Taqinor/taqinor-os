/**
 * QJR627 (D-QJR5-6) — le champ « Notes » du générateur est un texte CLIENT :
 * la proposition le lit (`note_client`, contrat QJR501) et l'affiche ; vide
 * ou absent → aucun bloc. La forme vient de l'échantillon COMMITTÉ
 * `proposal_data.json` (PACT10), seule la valeur du texte est posée ici.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { lireProposal, resolveNoteClient } from '../src/lib/proposition';

const CONTRAT = JSON.parse(readFileSync(
  fileURLToPath(new URL('../src/contract_samples/proposal_data.json', import.meta.url)),
  'utf-8',
)) as Record<string, Record<string, unknown>>;
const EXEMPLE = CONTRAT.exemple as Record<string, unknown>;
const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

describe('QJR627 — note_client est lue et rendue', () => {
  it('l’échantillon porte la clé (chaîne vide = aucun bloc)', () => {
    expect(EXEMPLE).toHaveProperty('note_client');
    expect(resolveNoteClient(EXEMPLE)).toBeNull();
    expect(lireProposal(EXEMPLE)?.noteClient).toBeNull();
  });

  it('un texte client est rendu tel quel, nettoyé', () => {
    const payload = { ...EXEMPLE, note_client: '  Pose prévue en mars.\nAccès par le portail.  ' };
    expect(resolveNoteClient(payload)).toBe('Pose prévue en mars.\nAccès par le portail.');
    expect(lireProposal(payload)?.noteClient).toBe('Pose prévue en mars.\nAccès par le portail.');
  });

  it('une valeur non textuelle ou absente ne produit rien', () => {
    expect(resolveNoteClient({ ...EXEMPLE, note_client: 42 as unknown as string })).toBeNull();
    expect(resolveNoteClient({})).toBeNull();
    expect(resolveNoteClient(null)).toBeNull();
  });

  it('la page monte le bloc « Note de votre conseiller » depuis resolveNoteClient', () => {
    expect(PAGE).toContain('resolveNoteClient(data!)');
    expect(PAGE).toContain('id="note-client"');
  });
});
