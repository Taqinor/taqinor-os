// @vitest-environment jsdom
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

import { formatMAD, savingsHeadline, type ProposalResponse } from '../src/lib/proposition';
import { cumulParOption, peindreCumulOption } from '../src/lib/proposition/cumulOption';
import { lirePageProposition, lireLibProposition } from './astroBlocsHelper';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const CONTRAT = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, unknown>;
const EXEMPLE = CONTRAT.exemple as unknown as ProposalResponse;
const PAGE = lirePageProposition();
const LIB = lireLibProposition();

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
    expect(PAGE).toContain("data-figure={headline.gainNet !== null ? 'gain_net_25_ans' : 'economies_cumul_25_ans'}");
  });

  // ADEV107 (C-ADEV-VER-003) — cocher l'autre option change la carte : cumul + mensualité de l'option cochée.
  it('la carte suit l’option cochée au niveau ≤ 2', () => {
    // Chaque option est LUE par savingsHeadline (aucune seconde formule), seulement sans gain net (niveau ≤ 2).
    const table = cumulParOption(EXEMPLE, true);
    expect(table.sans_batterie?.valeur).toBe(formatMAD(342314));
    expect(table.avec_batterie?.valeur).toBe(formatMAD(346653));
    expect(cumulParOption(EXEMPLE, false)).toEqual({});
    expect(PAGE).toContain('cumulParOptionDe(data ?? null, !!headline && headline.gainNet === null && twoOptions)');
    expect(PAGE).toContain('cumulParOption,');
    // La bascule (syncRecap, branchée sur chaque radio) peint valeur, option et mensualité.
    const debut = PAGE.indexOf('function syncRecap(): void {');
    const bloc = PAGE.slice(debut, PAGE.indexOf("radio.addEventListener('change', syncRecap);", debut) + 60);
    expect(bloc).toContain('cfg.cumulParOption?.[opt]');
    expect(bloc).toContain("document.querySelector<HTMLElement>('[data-detail-cumul-value]')");
    expect(bloc).toContain("peindreCumulOption(cumulVal, document.querySelector<HTMLElement>('[data-detail-cumul-sous]'), cumul, opt)");
    expect(bloc).toContain("radio.addEventListener('change', syncRecap);");
    expect(PAGE).toContain('data-detail-cumul-sous');
  });

  // Rejeu FAIL du 04/11 (P4.couleur_mensualite) — la mensualité garde sa mise en valeur après la bascule.
  it('la bascule garde le span .text-brass-300 de la mensualité (FR), EN/AR réécrits', () => {
    const p = document.createElement('p');
    p.innerHTML = '<span>Économies cumulées estimées sur 25 ans — soit <span class="text-brass-300">≈ 1 MAD/mois</span> qui restent dans votre poche<span class="text-lune-faint"> (loi 82-21, autoconsommation).</span></span><span hidden>x</span><span hidden>y</span>';
    const val = document.createElement('p');
    // Économie annuelle servie (l'échantillon la porte à null) ⇒ une mensualité à mettre en valeur.
    const servi = { ...EXEMPLE, quote: { ...EXEMPLE.quote, eco_a_ann: 12000 } } as ProposalResponse;
    const avec = cumulParOption(servi, true).avec_batterie!;
    expect(avec.mensuel).toBe(`≈ ${formatMAD(1000)}`);
    peindreCumulOption(val, p, avec, 'avec_batterie');
    expect(val.textContent).toBe(avec.valeur);
    expect(val.dataset.figureOption).toBe('avec');
    const mis = p.children[0].querySelectorAll('.text-brass-300');
    expect(mis).toHaveLength(1);
    expect(mis[0].textContent).toBe(`${avec.mensuel}/mois`);
    expect(p.children[0].textContent).toBe(avec.fr);
    expect(p.children[1].textContent).toBe(avec.en);
    expect(p.children[2].textContent).toBe(avec.ar);
  });

  // Rejeu FAIL du 04/11 (P4.bascule_taille_puis_option) — après une bascule de TAILLE, l'option ne repeint
  // jamais le cumul de la taille recommandée : la section des tailles charge le détail servi de la variante cochée.
  it('après une bascule de taille, la bascule d’option suit la taille chargée', () => {
    const debut = PAGE.indexOf('function syncRecap(): void {');
    const bloc = PAGE.slice(debut, PAGE.indexOf("radio.addEventListener('change', syncRecap);", debut));
    expect(bloc).toContain('!tailleHorsDevis) peindreCumulOption(');
    expect(bloc).toContain("document.addEventListener('taqinor:taille-chargee'");
    expect(PAGE).toContain("document.dispatchEvent(new CustomEvent('taqinor:taille-chargee', { detail: { defaut: cle === cleDefaut } }));");
    expect(PAGE).toMatch(/r\?\.name === 'option' && r\.checked && cle !== cleDefaut && v !== variante[^\n]*\{ variante = v; appliquer\(\); \}/);
  });
});

describe('RWEB24 (FIX-WEB C) — gain NET 25 ans servi : la carte affiche le chiffre du PDF, sous son libellé', () => {
  it('gainNet = l’entrée UNIQUE servie (option de la carte du PDF), quelle que soit l’option phare de la page', () => {
    expect(EXEMPLE.gain_net_25_ans).toEqual({ avec_batterie: 233000 });
    for (const opt of ['sans_batterie', 'avec_batterie'] as const) {
      expect(savingsHeadline(EXEMPLE, opt).gainNet).toBe(233000);
      expect(savingsHeadline(EXEMPLE, opt).gainNetOption).toBe('avec_batterie');
    }
    // « ≈ 0 MAD » au PDF (plancher, pas « Non rentabilisé ») : la page l’affiche aussi, jamais le brut à la place.
    const zero = { ...EXEMPLE, gain_net_25_ans: { sans_batterie: 0 } } as ProposalResponse;
    expect(savingsHeadline(zero, 'avec_batterie')).toMatchObject({ gainNet: 0, gainNetOption: 'sans_batterie' });
    // Le brut reste servi (devis au niveau ≤ 2) : jamais confondu avec le net.
    expect(savingsHeadline(EXEMPLE, 'sans_batterie').cumulative).toBe(342314);
  });

  it('clé absente (devis envoyé au niveau ≤ 2, option jamais rentabilisée) → aucun net, la carte garde le cumul brut', () => {
    const sans = { ...EXEMPLE } as ProposalResponse;
    delete (sans as { gain_net_25_ans?: unknown }).gain_net_25_ans;
    expect(savingsHeadline(sans, 'sans_batterie').gainNet).toBeNull();
    expect(savingsHeadline(sans, 'sans_batterie').gainNetOption).toBeNull();
    expect(savingsHeadline(sans, 'sans_batterie').cumulative).toBe(342314);
  });

  it('la page : libellé du PDF « Gain net sur 25 ans » (FR/EN/AR), le net d’abord, plus aucune promesse « même calcul » sur le brut', () => {
    expect(PAGE).toContain('`Gain net sur ${headline.years} ans${gainNetSuffixe.fr}`');
    expect(PAGE).toContain('`Net gain over ${headline.years} years${gainNetSuffixe.en}`');
    expect(PAGE).toContain('`صافي الربح على ${headline.years} سنة${gainNetSuffixe.ar}`');
    expect(PAGE).toContain('{headline.gainNet !== null || headline.cumulative ? (');
    expect(PAGE).toContain("{...(headline.gainNet !== null ? { 'data-detail-gain-net-card': '' } : { 'data-detail-cumul-card': '' })}");
    // L'option du chiffre est celle du PDF (servie), pas l'option phare de la page.
    expect(PAGE).toContain("data-figure-option={(headline.gainNetOption ?? reco) === 'avec_batterie' ? 'avec' : 'sans'}");
    expect(PAGE).not.toContain('Même calcul que votre devis PDF');
    expect(PAGE).not.toContain('Same calculation as your PDF quote');
  });
});
