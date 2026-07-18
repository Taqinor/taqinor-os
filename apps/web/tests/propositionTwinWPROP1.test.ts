// WPROP1 — le jumeau interactif du PDF : classifieur de fiches produit,
// tiroirs spéciaux, accroche « −X % », grand-livre financement, total de ligne.
// Helpers ADDITIFS de lib/proposition.ts — mêmes règles que le moteur PDF.
import { describe, expect, it } from 'vitest';

import {
  ficheSlugForItem,
  financingLedger,
  heroHook,
  itemTotalHt,
  specialDrawerKind,
  type ProposalResponse,
} from '../src/lib/proposition';

describe('WPROP1 ficheSlugForItem — port mot à mot du classifieur PDF', () => {
  it('associe chaque famille à sa fiche /produits', () => {
    expect(ficheSlugForItem('Panneau Canadien Solar 710W', 'Canadien Solar')).toBe('canadian-solar-710');
    expect(ficheSlugForItem('Panneau Jinko 710W', 'Jinko')).toBe('jinko-710');
    expect(ficheSlugForItem('Onduleur réseau Huawei 5kW Monophasé', 'Huawei')).toBe('onduleur-huawei-reseau');
    expect(ficheSlugForItem('Onduleur hybride Deye 5kW', 'Deye')).toBe('onduleur-deye-hybride');
    expect(ficheSlugForItem('Batterie Lithium Dyness 5,12 kWh', 'Dyness')).toBe('batterie-dyness');
    expect(ficheSlugForItem('Smart Meter', 'Huawei')).toBe('smart-meter-huawei');
    expect(ficheSlugForItem('Clé Wifi (dongle)', 'Huawei')).toBe('wifi-dongle-huawei');
  });

  it("ne fabrique JAMAIS de fiche pour les lignes TAQINOR ou hors marque", () => {
    expect(ficheSlugForItem('Structure de fixation aluminium')).toBe('');
    expect(ficheSlugForItem('Installation')).toBe('');
    expect(ficheSlugForItem('Transport')).toBe('');
    expect(ficheSlugForItem('Smart Meter', 'Generique')).toBe('');
    expect(ficheSlugForItem('')).toBe('');
  });
});

describe('WPROP1 specialDrawerKind — tiroirs Tableau AC/DC & Installation', () => {
  it('reconnaît le tableau de protection et la pose', () => {
    expect(specialDrawerKind('Tableau De Protection AC/DC')).toBe('tableau');
    expect(specialDrawerKind('Coffret de protection DC')).toBe('tableau');
    expect(specialDrawerKind('Installation')).toBe('installation');
    expect(specialDrawerKind('Pose et mise en service')).toBe('installation');
  });

  it('null pour tout le reste (le tiroir générique description/garantie prend le relais)', () => {
    expect(specialDrawerKind('Panneau Canadien Solar 710W')).toBeNull();
    expect(specialDrawerKind('')).toBeNull();
  });
});

describe('WPROP1 heroHook — l’accroche « −X % » 100 % chiffres backend', () => {
  const bills = [1500, 1450, 1550, 1600, 1750, 2100, 2400, 2350, 1950, 1700, 1550, 1500];
  const p = {
    quote: { factures_mensuelles: bills, eco_s_ann: 8467, eco_a_ann: 11995 },
  } as unknown as Pick<ProposalResponse, 'quote'>;

  it('calcule facture avant/après, −X % et la part de couverture', () => {
    const hook = heroHook(p, 'sans_batterie');
    expect(hook).not.toBeNull();
    expect(hook!.billBefore).toBe(1783); // moyenne des 12 factures
    expect(hook!.billAfter).toBe(1077); // 1783 − 8467/12
    expect(hook!.cutPercent).toBe(40);
    expect(hook!.coverageShare).toBeCloseTo(0.396, 2);
  });

  it("l'option avec batterie utilise SON économie backend", () => {
    const hook = heroHook(p, 'avec_batterie');
    expect(hook!.billAfter).toBe(783);
    expect(hook!.cutPercent).toBe(56);
  });

  it('null (accroche masquée, jamais inventée) sans factures ou sans économie', () => {
    expect(heroHook({ quote: { eco_s_ann: 8000 } } as never, 'sans_batterie')).toBeNull();
    expect(heroHook({ quote: { factures_mensuelles: bills } } as never, 'sans_batterie')).toBeNull();
    expect(
      heroHook({ quote: { factures_mensuelles: [0, 0, 0], eco_s_ann: 8000 } } as never, 'sans_batterie'),
    ).toBeNull();
  });
});

describe('WPROP1 financingLedger — économies − crédit = dans votre poche', () => {
  it('compose le grand-livre mensuel', () => {
    const l = financingLedger(8467, 621);
    expect(l).toEqual({ ecoMonthly: 706, creditMonthly: 621, net: 85 });
  });

  it('rend un net NÉGATIF tel quel (honnête, jamais masqué)', () => {
    const l = financingLedger(4800, 621);
    expect(l!.net).toBe(-221);
  });

  it('null quand une des deux jambes manque', () => {
    expect(financingLedger(null, 621)).toBeNull();
    expect(financingLedger(8467, 0)).toBeNull();
    expect(financingLedger(0, 621)).toBeNull();
  });
});

describe('WPROP1 itemTotalHt — P.U. HT × quantité', () => {
  it('calcule le total de ligne du tableau', () => {
    expect(itemTotalHt({ prix_unit_ht: 1273, quantite: 8 })).toBe(10184);
    expect(itemTotalHt({ prix_unit_ht: 11667, quantite: 1 })).toBe(11667);
    expect(itemTotalHt({ prix_unit_ht: 0, quantite: 5 })).toBe(0);
  });
});
