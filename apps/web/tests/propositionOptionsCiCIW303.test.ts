// CIW303 — Options C&I sur /proposition : l'offre réseau d'abord, la batterie en option avec sa
// seule valeur chiffrée ; simulateur batterie éteint en C&I.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  batterySimEligibleForMode,
  syntheseCi,
  valeurOptionBatterieCi,
  offrePrincipaleCi,
  type ProposalResponse,
} from '../src/lib/proposition';

function payload(mode: string, synthese: Record<string, unknown>): ProposalResponse {
  return {
    reference: 'DEV-2026-303',
    date: '07/10/2026',
    client_name: 'Usine Exemple',
    statut: 'envoye',
    mode_installation: mode,
    quote: { ref: 'DEV-2026-303', date: '07/10/2026', client_name: 'Usine Exemple' },
    synthese_ci: synthese,
  } as unknown as ProposalResponse;
}

describe('CIW303 — batterySimEligible', () => {
  it('faux en commercial et en industriel, vrai en résidentiel seulement', () => {
    expect(batterySimEligibleForMode('commercial')).toBe(false);
    expect(batterySimEligibleForMode('industriel')).toBe(false);
    expect(batterySimEligibleForMode('agricole')).toBe(false);
    expect(batterySimEligibleForMode('residentiel')).toBe(true);
  });
});

describe('CIW303 — extracteur de l\'option batterie C&I', () => {
  it('valeur absente → libellé « non chiffrée » (+ motif servi quand il dit autre chose)', () => {
    const ci = syntheseCi(
      payload('commercial', { option_servie: 'sans_batterie', option_batterie: { totaux: {}, valeur_chiffree: null, motif: 'valeur non chiffrée' } }),
    );
    const v = valeurOptionBatterieCi(ci)!;
    expect(v.chiffree).toBe(false);
    expect(v.textes.fr).toBe('valeur non chiffrée');
    expect(v.textes.en).toContain('not quantified');
    expect(v.motif).toBeNull(); // le motif servi est déjà la phrase

    const avecMotif = valeurOptionBatterieCi(
      syntheseCi(payload('industriel', { option_batterie: { valeur_chiffree: null, motif: 'aucun profil du soir déclaré' } })),
    )!;
    expect(avecMotif.chiffree).toBe(false);
    expect(avecMotif.motif).toBe('aucun profil du soir déclaré');
  });

  it('valeur chiffrée par le moteur → texte servi, repris tel quel', () => {
    const textes = { fr: 'Couverture du soir : servie.', en: 'Evening coverage: served.', ar: 'تغطية المساء: مقدمة.' };
    const v = valeurOptionBatterieCi(
      syntheseCi(payload('commercial', { option_batterie: { valeur_chiffree: { textes }, motif: null } })),
    )!;
    expect(v.chiffree).toBe(true);
    expect(v.textes).toEqual(textes);
  });

  it('pas d\'option batterie servie → null (aucune ligne inventée)', () => {
    expect(valeurOptionBatterieCi(syntheseCi(payload('commercial', { version: 1 })))).toBeNull();
    expect(valeurOptionBatterieCi(null)).toBeNull();
  });

  it('offre principale = réseau seul sauf option_servie « avec_batterie »', () => {
    expect(offrePrincipaleCi(syntheseCi(payload('commercial', { option_servie: 'sans_batterie' })))).toBe('sans_batterie');
    expect(offrePrincipaleCi(syntheseCi(payload('commercial', { option_servie: 'avec_batterie' })))).toBe('avec_batterie');
    expect(offrePrincipaleCi(null)).toBe('sans_batterie');
  });
});

describe('CIW303 — la page n\'a plus de second moteur batterie en C&I', () => {
  const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
  it('batterySimEligible passe par batterySimEligibleForMode (résidentiel seul)', () => {
    expect(page).toContain('const batterySimEligible = ok && batterySimEligibleForMode(curveMode);');
    expect(page).not.toMatch(/batterySimEligible = ok && \(curveMode === 'residentiel' \|\| curveMode === 'commercial'\)/);
  });
  it('#options C&I : offre principale + « Option proposée », valeur lue dans synthese_ci', () => {
    expect(page).toContain("'Option proposée'");
    expect(page).toContain('data-ci-valeur-batterie');
    expect(page).toContain('const ciValeurBatterie = valeurOptionBatterieCi(ci);');
  });
});
