/**
 * ADEV50 (C-ADEV-017) — le titre « Économies cumulées sur 25 ans » est le
 * chiffre SERVI `economies_cumul_25_ans[option]` (même flux que le PDF
 * `/proposal`), option par option — jamais l'ancien « `eco_a_cumul` × 25 » qui
 * affichait 400 350 MAD pour les DEUX options (sonde VA p7).
 *
 * Exécute la VRAIE fonction de titre (`savingsHeadline`) sur l'échantillon
 * PARTAGÉ `proposal_data.json` (contrat ADEV2).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { savingsHeadline, type ProposalResponse } from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const CONTRAT = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, unknown>;
const EXEMPLE = CONTRAT.exemple as unknown as ProposalResponse;
const PAGE = read('../src/pages/proposition/[...token].astro');
const LIB = read('../src/lib/proposition.ts');

describe('ADEV50 — cumul 25 ans servi, option par option', () => {
  it('le titre de chaque option = la valeur servie pour cette option', () => {
    expect(EXEMPLE.economies_cumul_25_ans).toEqual({ sans_batterie: 342314, avec_batterie: 346653 });
    expect(savingsHeadline(EXEMPLE, 'sans_batterie').cumulative).toBe(342314);
    expect(savingsHeadline(EXEMPLE, 'avec_batterie').cumulative).toBe(346653);
  });

  it('jamais « économie × 25 » : les deux options ne partagent pas un chiffre recalculé', () => {
    const s = savingsHeadline(EXEMPLE, 'sans_batterie').cumulative;
    const a = savingsHeadline(EXEMPLE, 'avec_batterie').cumulative;
    expect(s).not.toBe(a);
    const ecoA = (EXEMPLE.quote as { eco_a_cumul?: number }).eco_a_cumul;
    if (typeof ecoA === 'number') expect(a).not.toBe(ecoA * 25);
  });

  it('clé absente → aucun cumul (le bloc n’est pas rendu)', () => {
    const sans = { ...EXEMPLE } as ProposalResponse;
    delete (sans as { economies_cumul_25_ans?: unknown }).economies_cumul_25_ans;
    expect(savingsHeadline(sans, 'sans_batterie').cumulative).toBeNull();
    expect(savingsHeadline(sans, 'avec_batterie').cumulative).toBeNull();
  });

  it('aucun second calcul de cumul côté web ; le nombre porte data-figure', () => {
    expect(LIB).not.toMatch(/rate\s*\*\s*years/);
    expect(LIB).not.toMatch(/const\s+BILL_INFLATION_RATE/);
    expect(PAGE).toContain('data-figure="economies_cumul_25_ans"');
  });
});
