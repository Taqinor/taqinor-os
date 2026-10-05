// AGW300 — page /proposition agricole : plus d'« Économie / an » ni de « Rentabilisé
// en » résidentiels, plus de CO₂ au facteur réseau. Fonction PURE
// `chiffresEconomiePhare` (proposition.ts), seule définition de ces chiffres.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chiffresEconomiePhare, type ProposalResponse } from '../src/lib/proposition';

function payload(mode: string, quote: Record<string, unknown> = {}): ProposalResponse {
  return {
    reference: 'DEV-2026-300',
    date: '01/10/2026',
    client_name: 'Atlas Agri',
    statut: 'envoye',
    mode_installation: mode,
    quote: {
      ref: 'DEV-2026-300',
      date: '01/10/2026',
      client_name: 'Atlas Agri',
      totaux_sans: { ht_brut: 900000, remise: 0, ht_net: 900000, tva: 180000, ttc: 1080000 },
      display_total: 1080000,
      nb_options: 2,
      eco_s_ann: 24000,
      eco_a_ann: 31000,
      roi_s: 5.2,
      roi_a: 6.1,
      ...quote,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 1080000, avec_batterie: 1300000, display_total: 1080000, nb_options: 2 },
    accepted: false,
  } as unknown as ProposalResponse;
}

describe('AGW300 — chiffresEconomiePhare', () => {
  it('un payload agricole AVEC eco_s_ann et roi_s remplis donne tout à null', () => {
    for (const reco of [null, 'sans_batterie', 'avec_batterie'] as const) {
      expect(chiffresEconomiePhare(payload('agricole'), reco)).toEqual({
        ecoSans: null, ecoAvec: null, paybackSans: null, paybackAvec: null, ecoHero: null, paybackHero: null,
      });
    }
  });

  it('« pompage » (alias) est traité comme agricole', () => {
    expect(chiffresEconomiePhare(payload('pompage'), 'sans_batterie').ecoHero).toBeNull();
  });

  it('le résidentiel est inchangé (sans / avec / héros selon la reco)', () => {
    const sans = chiffresEconomiePhare(payload('residentiel'), 'sans_batterie');
    expect(sans.ecoSans).toBe(24000);
    expect(sans.ecoAvec).toBe(31000);
    expect(sans.ecoHero).toBe(24000);
    expect(sans.paybackHero).toBe(sans.paybackSans);
    expect(sans.paybackSans).toContain('ans');
    const avec = chiffresEconomiePhare(payload('residentiel'), 'avec_batterie');
    expect(avec.ecoHero).toBe(31000);
    expect(avec.paybackHero).toBe(avec.paybackAvec);
  });

  it('industriel / commercial / mode absent gardent leurs chiffres', () => {
    for (const m of ['industriel', 'commercial', '']) {
      expect(chiffresEconomiePhare(payload(m), 'sans_batterie').ecoHero).toBe(24000);
    }
  });

  it('payload nul/absent → tout à null, sans exception', () => {
    expect(chiffresEconomiePhare(null).ecoHero).toBeNull();
    expect(chiffresEconomiePhare(undefined).paybackHero).toBeNull();
  });
});

describe('AGW300 — la page n\'a qu\'UNE définition de ces chiffres et un CO₂ éteint en agricole', () => {
  const page = readFileSync(
    fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
    'utf-8',
  );
  it('ecoHero / paybackHero ne viennent que de chiffresEconomiePhare', () => {
    expect(page).toMatch(/chiffresEconomiePhare\(ok \? data : null, reco\)/);
    expect(page).not.toMatch(/const ecoHero =/);
    expect(page).not.toMatch(/const paybackHero =/);
    expect(page).not.toMatch(/const ecoSans = q\?\.eco_s_ann/);
  });
  it('enviro (CO₂) vaut null en agricole', () => {
    expect(page).toContain('const enviro = ok && !isAgricole ? environmentalImpact(prodKwh) : null;');
  });
});
