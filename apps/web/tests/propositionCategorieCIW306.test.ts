// CIW306 — Bloc catégorie d'un devis commercial lu dans `synthese_ci` — fin de la copie TS de
// `categories.py` (COMMERCIAL_ARCHETYPES / commercialArchetype).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as lib from '../src/lib/proposition';
import { syntheseCi, categorieCi, type ProposalResponse } from '../src/lib/proposition';

function payload(mode: string, synthese: Record<string, unknown>): ProposalResponse {
  return {
    reference: 'DEV-2026-306',
    date: '07/10/2026',
    client_name: 'Hôtel Exemple',
    statut: 'envoye',
    mode_installation: mode,
    categorie_commerciale: 'hotel',
    quote: {},
    synthese_ci: synthese,
  } as unknown as ProposalResponse;
}

const CATEGORIE = {
  cle: 'hotel',
  libelle: 'Hôtel',
  accroche: 'Un hôtel consomme jour et nuit : le solaire couvre la journée.',
  bloc: {
    titre: 'Votre hôtel',
    lignes: [
      { textes: { fr: '40 chambres, réception 24 h (déclaré).', en: '40 rooms, 24-hour reception (declared).', ar: '40 غرفة، استقبال 24 ساعة (مصرح به).' } },
      { textes: { fr: 'Blanchisserie sur place.', en: 'On-site laundry.', ar: 'مصبنة في عين المكان.' } },
    ],
  },
};

describe('CIW306 — categorieCi (extracteur pur)', () => {
  it('catégorie servie → titre, accroche et lignes FR/EN/AR tels que servis', () => {
    const c = categorieCi(syntheseCi(payload('commercial', { segment: 'commercial', categorie: CATEGORIE })))!;
    expect(c.cle).toBe('hotel');
    expect(c.titre).toBe('Votre hôtel');
    expect(c.accroche).toContain('le solaire couvre la journée');
    expect(c.lignes).toHaveLength(2);
    expect(c.lignes[0]).toEqual(CATEGORIE.bloc.lignes[0].textes);
  });

  it('catégorie absente → null (le bloc est omis)', () => {
    expect(categorieCi(syntheseCi(payload('commercial', { segment: 'commercial' })))).toBeNull();
    expect(categorieCi(syntheseCi(payload('commercial', { categorie: {} })))).toBeNull();
    expect(categorieCi(null)).toBeNull();
  });

  it('catégorie sans aucun contenu lisible → null ; ligne sans texte FR écartée', () => {
    expect(categorieCi(syntheseCi(payload('commercial', { categorie: { cle: 'autre', bloc: { lignes: [] } } })))).toBeNull();
    const c = categorieCi(
      syntheseCi(payload('commercial', { categorie: { cle: 'x', libelle: 'X', bloc: { lignes: [{ textes: { en: 'only en' } }, {}] } } })),
    )!;
    expect(c.lignes).toHaveLength(0);
  });

  it('jamais en industriel (segment servi industriel)', () => {
    expect(categorieCi(syntheseCi(payload('industriel', { segment: 'industriel', categorie: CATEGORIE })))).toBeNull();
  });
});

describe('CIW306 — la copie TS est supprimée', () => {
  it('COMMERCIAL_ARCHETYPES / commercialArchetype n\'existent plus', () => {
    expect((lib as Record<string, unknown>).commercialArchetype).toBeUndefined();
    const src = readFileSync(fileURLToPath(new URL('../src/lib/proposition.ts', import.meta.url)), 'utf-8');
    expect(src).not.toMatch(/const COMMERCIAL_ARCHETYPES/);
    expect(src).not.toMatch(/export function commercialArchetype/);
    expect(src).not.toMatch(/interface CommercialArchetype/);
  });
  it('la page rend la catégorie servie, pas un archétype local', () => {
    const page = readFileSync(fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)), 'utf-8');
    expect(page).not.toMatch(/comArchetype|commercialArchetype/);
    expect(page).toContain('const ciCategorie = ok && isCommercial ? categorieCi(ci) : null;');
    expect(page).toContain('id="mode-commercial-cat"');
  });
});
