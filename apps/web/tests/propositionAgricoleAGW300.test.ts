// AGW300 — page /proposition agricole : plus d'« Économie / an » ni de « Rentabilisé
// en » résidentiels, plus de CO₂ au facteur réseau. Fonction PURE
// `chiffresEconomiePhare` (proposition.ts), seule définition de ces chiffres.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { chiffresEconomiePhare, type ProposalResponse } from '../src/lib/proposition';
import { lirePageProposition } from './astroBlocsHelper';

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
        paybackHeroI18n: null, paybackHeroJamais: false,
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

  it('RWEB1 — `roi_*_jamais` : aucune année (pas la sentinelle 25), libellé PDF ; unité traduite sinon', () => {
    const j = chiffresEconomiePhare(payload('residentiel', { roi_s: 25, roi_s_jamais: true }), 'sans_batterie');
    expect(j.paybackSans).toBeNull();
    expect(j.paybackHero).toBeNull();
    expect(j.paybackHeroI18n).toBeNull();
    expect(j.paybackHeroJamais).toBe(true);
    const ok = chiffresEconomiePhare(payload('residentiel'), 'avec_batterie');
    expect(ok.paybackHeroI18n).toEqual({ fr: '6,1 ans', en: '6.1 years', ar: '6,1 سنوات' });
    expect(ok.paybackHeroJamais).toBe(false);
    const long = chiffresEconomiePhare(payload('residentiel', { roi_a: 12.5 }), 'avec_batterie');
    expect(long.paybackHeroI18n?.ar).toBe('12,5 سنة');
    // RWEB14 — économie AVEC présente mais retour AVEC « jamais » : pas de repli sur le retour SANS.
    const mix = chiffresEconomiePhare(payload('residentiel', { roi_a: 25, roi_a_jamais: true }), 'avec_batterie');
    expect(mix.ecoHero).toBe(31000);
    expect(mix.paybackHero).toBeNull();
    expect(mix.paybackHeroJamais).toBe(true);
    expect(lirePageProposition()).toContain('NON_RENTABILISE_25');
  });

  it('mode absent garde ses chiffres ; industriel / commercial ne lisent plus eco_s_ann (CIW300 : synthese_ci)', () => {
    expect(chiffresEconomiePhare(payload(''), 'sans_batterie').ecoHero).toBe(24000);
    for (const m of ['industriel', 'commercial']) {
      expect(chiffresEconomiePhare(payload(m), 'sans_batterie').ecoHero).toBeNull();
    }
  });

  it('payload nul/absent → tout à null, sans exception', () => {
    expect(chiffresEconomiePhare(null).ecoHero).toBeNull();
    expect(chiffresEconomiePhare(undefined).paybackHero).toBeNull();
  });
});

describe('AGW300 — la page n\'a qu\'UNE définition de ces chiffres et un CO₂ éteint en agricole', () => {
  const page = lirePageProposition();
  it('ecoHero / paybackHero ne viennent que de chiffresEconomiePhare', () => {
    expect(page).toMatch(/chiffresEconomiePhare\(ok \? data : null, reco\)/);
    expect(page).not.toMatch(/const ecoHero =/);
    expect(page).not.toMatch(/const paybackHero =/);
    expect(page).not.toMatch(/const ecoSans = q\?\.eco_s_ann/);
  });
  it('aucune tonne CO₂ calculée sur la page (facteur non sourcé — RWEB6, tous segments)', () => {
    expect(page).not.toContain('environmentalImpact(prodKwh)');
    expect(page).not.toContain('source à préciser.');
  });
});
