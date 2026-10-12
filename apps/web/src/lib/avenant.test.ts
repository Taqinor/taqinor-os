/**
 * VNT72 — la page /proposition lit l'AVENANT (V2 d'un prix négocié) servi par
 * `proposal_data` (VNT61) : « Avenant à <V1> — nouveau prix » tant qu'il reste à
 * signer, puis la confirmation. Nouveau fichier car : aucun test de
 * `proposition.ts` hors `proposition.roofLayout.test.ts` ne vise ce lecteur, et
 * les gros fichiers (11 803 / 6 607 l.) ne grossissent pas.
 *
 * Les exemples sont ceux du CONTRAT (`proposal_data.json` : `exemple` porte
 * l'avenant à signer, `exemple_avenant_a_signer` / `exemple_avenant_signe` sont
 * les deux fragments VNT2) — jamais une valeur écrite ici à la main.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { avenantVue, lireAvenant } from './avenant';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const CONTRAT = JSON.parse(read('../contract_samples/proposal_data.json')) as Record<string, any>;
const A_SIGNER = CONTRAT.exemple_avenant_a_signer.avenant as unknown;
const SIGNE = CONTRAT.exemple_avenant_signe.avenant as unknown;

describe('VNT72 — lireAvenant lit les fragments du contrat, champ par champ', () => {
  it('avenant à signer', () => {
    expect(lireAvenant(A_SIGNER)).toEqual({
      aSigner: true,
      remplaceReference: 'DEV-202610-0012',
      signeLe: null,
    });
  });

  it('avenant signé', () => {
    expect(lireAvenant(SIGNE)).toEqual({
      aSigner: false,
      remplaceReference: 'DEV-202610-0012',
      signeLe: '2026-10-12T09:30:00+00:00',
    });
  });

  it('l’exemple principal porte le même avenant à signer', () => {
    expect(lireAvenant(CONTRAT.exemple.avenant)).toEqual(lireAvenant(A_SIGNER));
  });

  it.each([
    ['a_signer', A_SIGNER],
    ['remplace', SIGNE],
    ['signe_le', SIGNE],
  ] as const)('renommer `avenant.%s` change ce que la page lit', (cle, fragment) => {
    // `a_signer` se garde sur le fragment À SIGNER (vrai) : sur le signé il vaut
    // `false`, la valeur neutre — indiscernable par renommage.
    const casse = JSON.parse(JSON.stringify(fragment)) as Record<string, unknown>;
    casse[`${cle}_v2`] = casse[cle];
    delete casse[cle];
    expect(lireAvenant(casse)).not.toEqual(lireAvenant(fragment));
  });

  it('clé absente (jamais null servi) ou illisible ⇒ aucun avenant, jamais un bloc fabriqué', () => {
    for (const brut of [undefined, null, 42, 'oui', [], true]) {
      expect(lireAvenant(brut)).toBeNull();
    }
  });

  it('une référence vide reste absente (jamais « Avenant à  »)', () => {
    const lu = lireAvenant({ a_signer: true, remplace: { reference: '  ' }, signe_le: null });
    expect(lu?.remplaceReference).toBeNull();
  });
});

describe('VNT72 — avenantVue : le texte que le client lit', () => {
  it('à signer : « Avenant à <V1> — nouveau prix », trois langues', () => {
    const vue = avenantVue(lireAvenant(A_SIGNER))!;
    expect(vue.etat).toBe('a_signer');
    expect(vue.titre.fr).toBe('Avenant à DEV-202610-0012 — nouveau prix');
    expect(vue.titre.en).toContain('DEV-202610-0012');
    expect(vue.titre.ar).toContain('DEV-202610-0012');
    expect(vue.corps.fr.length).toBeGreaterThan(30);
  });

  it('sans référence servie : titre sans la référence, jamais « undefined »', () => {
    const vue = avenantVue({ aSigner: true, remplaceReference: null, signeLe: null })!;
    expect(vue.titre.fr).toBe('Avenant — nouveau prix');
    expect(JSON.stringify(vue)).not.toMatch(/undefined|null/);
  });

  it('signé : la confirmation porte la date de signature', () => {
    const vue = avenantVue(lireAvenant(SIGNE))!;
    expect(vue.etat).toBe('signe');
    expect(vue.titre.fr).toBe('Avenant signé ✓');
    expect(vue.corps.fr).toContain('DEV-202610-0012');
    expect(vue.corps.fr).toContain('12 octobre 2026');
  });

  it('signé sans date lisible : confirmation sans date, jamais « Invalid Date »', () => {
    const vue = avenantVue({ aSigner: false, remplaceReference: 'DEV-202610-0012', signeLe: 'pas une date' })!;
    expect(vue.etat).toBe('signe');
    expect(JSON.stringify(vue)).not.toMatch(/Invalid|NaN|undefined/);
  });

  it('ni à signer ni signé ⇒ rien à afficher', () => {
    expect(avenantVue({ aSigner: false, remplaceReference: 'DEV-1', signeLe: null })).toBeNull();
    expect(avenantVue(null)).toBeNull();
  });

  it('la confirmation après signature en direct existe (rendue cachée avec l’avenant à signer)', () => {
    const vue = avenantVue(lireAvenant(A_SIGNER))!;
    expect(vue.confirmation.titre.fr).toBe('Avenant signé ✓');
    expect(vue.confirmation.corps.fr).toContain('DEV-202610-0012');
  });
});

describe('VNT72 — le composant est monté, les gros fichiers ne portent que le branchement', () => {
  const page = read('../pages/proposition/[...token].astro');
  const composant = read('../components/proposition/BandeauAvenant.astro');

  it('la page importe et monte BandeauAvenant', () => {
    expect(page).toContain("import BandeauAvenant from '../../components/proposition/BandeauAvenant.astro'");
    expect(page).toContain('<BandeauAvenant');
  });

  it('le composant lit via lib/avenant.ts et expose ses ancres', () => {
    expect(composant).toContain("from '../../lib/avenant'");
    expect(composant).toContain('id="avenant"');
    expect(composant).toContain('data-avenant-etat');
  });
});
