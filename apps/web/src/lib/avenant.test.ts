import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { resolveAvenant } from './avenant';

const CONTRAT = JSON.parse(
  readFileSync(fileURLToPath(new URL('../contract_samples/proposal_data.json', import.meta.url)), 'utf-8'),
) as Record<string, Record<string, unknown>>;

describe('VNT72 — l’avenant lu sur les exemples du contrat', () => {
  it('à signer : référence de la V1 remplacée, pas de date', () => {
    expect(resolveAvenant(CONTRAT.exemple_avenant_a_signer)).toEqual({
      etat: 'a_signer', reference: 'DEV-202610-0012', signeLe: null,
    });
  });
  it('signé : date de signature jj/mm/aaaa', () => {
    expect(resolveAvenant(CONTRAT.exemple_avenant_signe)).toEqual({
      etat: 'signe', reference: 'DEV-202610-0012', signeLe: '12/10/2026',
    });
  });
  it('clé absente ou incohérente : aucun bandeau', () => {
    expect(resolveAvenant({})).toBeNull();
    expect(resolveAvenant(null)).toBeNull();
    expect(resolveAvenant({ avenant: null })).toBeNull();
    expect(resolveAvenant({ avenant: { a_signer: 'oui' } })).toBeNull();
    expect(resolveAvenant({ avenant: { a_signer: false, signe_le: null } })).toBeNull();
    expect(resolveAvenant({ avenant: { a_signer: false, signe_le: 'pas une date' } })).toBeNull();
  });
  it('référence illisible : bandeau sans référence, jamais inventée', () => {
    expect(resolveAvenant({ avenant: { a_signer: true } })?.reference).toBeNull();
  });
});
