// WJ87 — « Je signe au nom de… » : le signataire enregistré reste `nom`
// (champ de base), `on_behalf_of` est une précision FACULTATIVE et ADDITIVE —
// jamais un remplacement, jamais envoyée vide, un backend qui l'ignore
// continue de fonctionner exactement comme avant (même discipline que WJ11).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { buildAcceptBodyRich, buildAcceptBody } from '../src/lib/proposition';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[token].astro');

describe('WJ87 — buildAcceptBodyRich : on_behalf_of additif', () => {
  it('ajoute on_behalf_of quand fourni et non vide (trim appliqué)', () => {
    const body = buildAcceptBodyRich(
      { nom: 'Reda', option: 'avec_batterie' },
      true,
      { on_behalf_of: '  mes parents  ' },
    );
    expect(body.on_behalf_of).toBe('mes parents');
    expect(body.nom).toBe('Reda'); // le signataire enregistré reste `nom`
  });

  it('omet le champ quand vide/blanc/absent — jamais une chaîne vide envoyée', () => {
    expect(buildAcceptBodyRich({ nom: 'Reda', option: null }, false, { on_behalf_of: '' })).toEqual(
      buildAcceptBody({ nom: 'Reda', option: null }, false),
    );
    expect(buildAcceptBodyRich({ nom: 'Reda', option: null }, false, { on_behalf_of: '   ' })).toEqual(
      buildAcceptBody({ nom: 'Reda', option: null }, false),
    );
    expect(buildAcceptBodyRich({ nom: 'Reda', option: null }, false, {})).toEqual(
      buildAcceptBody({ nom: 'Reda', option: null }, false),
    );
    expect('on_behalf_of' in buildAcceptBodyRich({ nom: 'Reda', option: null }, false, {})).toBe(false);
  });

  it('cohabite avec les autres champs WJ11 (signature/consentement/horodatage) sans collision', () => {
    const body = buildAcceptBodyRich(
      { nom: 'Reda', option: 'avec_batterie' },
      true,
      {
        signature_data_url: 'data:image/png;base64,AAAA',
        consent_esign: true,
        signed_at_client: '2026-07-03T10:00:00Z',
        on_behalf_of: 'mon foyer',
      },
    );
    expect(body).toEqual({
      nom: 'Reda',
      option: 'avec_batterie',
      signature_data_url: 'data:image/png;base64,AAAA',
      consent_esign: true,
      signed_at_client: '2026-07-03T10:00:00Z',
      on_behalf_of: 'mon foyer',
    });
  });
});

describe('WJ87 — [token].astro : champ optionnel dans le formulaire + payload', () => {
  it('un champ #sign-on-behalf-of existe, placé à côté des cases de consentement', () => {
    expect(PROPOSITION).toContain('id="sign-on-behalf-of"');
    expect(PROPOSITION).toContain('name="on_behalf_of"');
    const idx = PROPOSITION.indexOf('id="sign-on-behalf-of"');
    const accordIdx = PROPOSITION.indexOf('id="sign-accord"');
    const consentIdx = PROPOSITION.indexOf('id="sign-consent"');
    expect(idx).toBeGreaterThan(0);
    expect(idx).toBeLessThan(accordIdx);
    expect(accordIdx).toBeLessThan(consentIdx);
  });

  it('le champ n’est PAS `required` (facultatif)', () => {
    const start = PROPOSITION.indexOf('id="sign-on-behalf-of"');
    const tagEnd = PROPOSITION.indexOf('/>', start);
    const tag = PROPOSITION.slice(start - 50, tagEnd);
    expect(tag).not.toContain('required');
  });

  it('le libellé est FR/EN/AR (data-i18n) — jamais du français figé sous EN/AR', () => {
    const start = PROPOSITION.indexOf('WJ87 · SIGNER AU NOM DU FOYER');
    const block = PROPOSITION.slice(start, start + 1600);
    expect(block).toContain('data-fr="Je signe au nom de (optionnel)"');
    expect(block).toContain('data-en="I am signing on behalf of (optional)"');
    expect(block).toContain('data-ar="أوقّع نيابة عن (اختياري)"');
  });

  it('le placeholder est traduit via le registre data-i18n-placeholder (applyLang)', () => {
    expect(PROPOSITION).toContain('data-i18n-placeholder');
    expect(PROPOSITION).toContain('data-placeholder-fr=');
    expect(PROPOSITION).toContain('data-placeholder-en=');
    expect(PROPOSITION).toContain('data-placeholder-ar=');
    expect(PROPOSITION).toContain('el.dataset.placeholderAr');
  });

  it('la valeur est lue et transmise dans buildAcceptBodyRich au submit, jamais perdue', () => {
    const submitSection = PROPOSITION.slice(
      PROPOSITION.indexOf("form?.addEventListener('submit'"),
      PROPOSITION.indexOf('</script>', PROPOSITION.indexOf("form?.addEventListener('submit'")),
    );
    expect(submitSection).toContain("getElementById('sign-on-behalf-of')");
    expect(submitSection).toContain('on_behalf_of: onBehalfOf');
  });

  it('le signataire enregistré reste explicitement `nom` — le libellé le précise au client', () => {
    const start = PROPOSITION.indexOf('WJ87 · SIGNER AU NOM DU FOYER');
    const block = PROPOSITION.slice(start, start + 2200);
    expect(block).toMatch(/signataire enregistré/);
  });
});
