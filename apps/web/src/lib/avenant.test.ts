import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { avenantASigner, resolveAvenant } from './avenant';
import { resolveOfferState, type ProposalResponse } from './proposition';

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

describe('ERR-VNT83-AVENANT-SIGNATURE-PAGE — un avenant à signer reste signable', () => {
  const V2 = { statut: 'accepte', accepted: true, date_validite: null, quote: {} } as unknown as ProposalResponse;
  it('avenantASigner : vrai seulement si a_signer et pas de signe_le', () => {
    expect(avenantASigner(CONTRAT.exemple_avenant_a_signer)).toBe(true);
    expect(avenantASigner(CONTRAT.exemple_avenant_signe)).toBe(false);
    expect(avenantASigner({ avenant: { a_signer: true, signe_le: '2026-10-12T09:30:00+00:00' } })).toBe(false);
    expect(avenantASigner({})).toBe(false);
    expect(avenantASigner(null)).toBe(false);
  });
  it('V2 acceptée en interne + avenant à signer : état live (formulaire visible)', () => {
    expect(resolveOfferState({ ...V2, ...CONTRAT.exemple_avenant_a_signer } as ProposalResponse)).toBe('live');
  });
  it('avenant signé ou devis accepté ordinaire : état accepted inchangé', () => {
    expect(resolveOfferState({ ...V2, ...CONTRAT.exemple_avenant_signe } as ProposalResponse)).toBe('accepted');
    expect(resolveOfferState(V2)).toBe('accepted');
  });
  it('avenant à signer mais offre expirée : reste expirée', () => {
    const p = { ...V2, ...CONTRAT.exemple_avenant_a_signer, statut: 'expire', accepted: false } as ProposalResponse;
    expect(resolveOfferState(p)).toBe('expired');
  });
});
