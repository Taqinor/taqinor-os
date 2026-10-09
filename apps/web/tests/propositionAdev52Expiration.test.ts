/**
 * ADEV52 (C-ADEV-019) — UNE règle d'expiration : la page lit le verdict
 * SERVEUR `offre_expiree` (fin du dernier jour à l'heure du Maroc) et le
 * dernier jour `date_expiration` ; elle ne calcule plus « 12:00 UTC du dernier
 * jour » (qui déclarait l'offre expirée à 13:30 UTC le jour même où le
 * serveur l'acceptait encore).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { resolveOfferState, resolveValidity, type ProposalResponse } from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const CONTRAT = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, unknown>;
const EXEMPLE = CONTRAT.exemple as unknown as ProposalResponse;

const DERNIER_JOUR_1330_UTC = new Date(Date.UTC(2026, 9, 15, 13, 30, 0));

describe('ADEV52 — la page lit `offre_expiree`, elle ne calcule rien', () => {
  it('le contrat sert le verdict et le dernier jour', () => {
    expect(EXEMPLE.offre_expiree).toBe(false);
    expect(EXEMPLE.date_expiration).toBe('2026-10-15');
  });

  it('dernier jour, 13:30 UTC : PAS expirée tant que le serveur dit non', () => {
    const p = { ...EXEMPLE, date_validite: '2026-10-15', offre_expiree: false } as ProposalResponse;
    expect(resolveValidity(p, DERNIER_JOUR_1330_UTC).expired).toBe(false);
    expect(resolveOfferState(p, DERNIER_JOUR_1330_UTC)).toBe('live');
  });

  it('le serveur dit expirée → page « offre expirée », quelle que soit l’heure locale', () => {
    const p = { ...EXEMPLE, statut: 'envoye', accepted: false, offre_expiree: true } as ProposalResponse;
    expect(resolveValidity(p, new Date(Date.UTC(2020, 0, 1))).expired).toBe(true);
    expect(resolveOfferState(p)).toBe('expired');
  });

  it('le libellé est le dernier jour SERVI (`date_expiration`)', () => {
    const p = { ...EXEMPLE, date_validite: '2026-11-30', date_expiration: '2026-10-15' } as ProposalResponse;
    expect(resolveValidity(p).label).toBe('15 octobre 2026');
  });

  it('aucun calcul local d’expiration ne survit dans `resolveValidity`', () => {
    const lib = read('../src/lib/proposition.ts');
    const corps = lib.slice(lib.indexOf('export function resolveValidity'), lib.indexOf('export interface AcompteResolu'));
    expect(corps).toContain('p.offre_expiree === true');
    expect(corps).not.toMatch(/getTime\(\)\s*<\s*now/);
  });
});
