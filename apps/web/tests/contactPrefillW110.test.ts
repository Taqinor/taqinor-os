// @vitest-environment jsdom
//
// W110 — flux en UNE page : capture client (Nom / Téléphone / Adresse) en HAUT, surfacée
// par le diagnostic relocalisé sous le résultat. `prefillLead` est étendu pour reporter
// lf-name / lf-phone / lf-city quand on les fournit, ET pour remplir lf-city depuis
// l'adresse géocodée (#rp9-address) quand le champ ville est vide — TOUJOURS un handoff,
// JAMAIS un POST de lead (garde W85/W97). On vérifie le pur createPrefill().prefillLead +
// le garde-fou « aucun module ne poste un lead ».
import { describe, expect, it, beforeEach } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createPrefill } from '../src/scripts/roofPro11/prefill';
import { ORIENTATIONS } from '../src/lib/enrichment';

const fromRoot = (rel: string) => resolve(process.cwd(), rel);
const read = (rel: string) => readFileSync(fromRoot(rel), 'utf-8');

type PrefillCtx = Parameters<typeof createPrefill>[0];
const makeCtx = (): PrefillCtx =>
  ({
    opts: { reducedMotion: true },
    vertices: [
      [-7.5, 33.5],
      [-7.4999, 33.5],
      [-7.4999, 33.5001],
      [-7.5, 33.5001],
    ],
    roofType: 'flat',
    facingAzimuthDeg: 180,
  }) as unknown as PrefillCtx;

/** DOM du diagnostic relocalisé : Nom/Téléphone/Ville + surface/orientation/kWc + l'adresse
 *  géocodée (#rp9-address) que prefillLead lit pour pré-remplir la ville. */
const setupForm = (geocoded = '') => {
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
  document.body.innerHTML = `
    <input id="rp9-address" value="${geocoded}" />
    <details id="diag">
      <input id="lf-name" />
      <input id="lf-phone" />
      <input id="lf-city" />
      <input id="lf-area" />
      <select id="lf-orient">
        ${ORIENTATIONS.map((o) => `<option value="${o.id}">${o.label}</option>`).join('')}
      </select>
      <input id="lf-kwc-est" />
    </details>
    <div id="simulateur"></div>
  `;
};

const val = (id: string) => (document.getElementById(id) as HTMLInputElement).value;
const card = () => ({ title: '', isReco: true, count: 10, kwc: 4, annualKwh: 6000, pct: 80, savingsLow: 0, savingsHigh: 0, why: '' });

describe('W110 — prefillLead reporte Nom / Téléphone / Ville quand fournis', () => {
  beforeEach(() => setupForm());

  it('écrit lf-name / lf-phone / lf-city depuis le contact fourni', () => {
    createPrefill(makeCtx()).prefillLead(card() as never, { name: 'Reda K.', phone: '0612345678', city: 'Marrakech' });
    expect(val('lf-name')).toBe('Reda K.');
    expect(val('lf-phone')).toBe('0612345678');
    expect(val('lf-city')).toBe('Marrakech');
  });

  it('garde le pré-remplissage existant (surface + kWc + orientation)', () => {
    createPrefill(makeCtx()).prefillLead(card() as never, { name: 'X' });
    expect(Number(val('lf-area'))).toBeGreaterThan(0);
    expect(Number(val('lf-kwc-est'))).toBeGreaterThan(0);
    expect(val('lf-orient')).toBe('sud');
    expect((document.getElementById('diag') as HTMLDetailsElement).open).toBe(true);
  });

  it('un champ contact vide/absent n\'écrase rien', () => {
    setupForm();
    (document.getElementById('lf-name') as HTMLInputElement).value = 'Déjà saisi';
    createPrefill(makeCtx()).prefillLead(card() as never, { name: '   ' }); // vide après trim
    expect(val('lf-name')).toBe('Déjà saisi');
    // sans contact du tout : aucune erreur, et les champs étude restent remplis
    createPrefill(makeCtx()).prefillLead(card() as never);
    expect(Number(val('lf-area'))).toBeGreaterThan(0);
  });
});

describe('W110 — la ville est pré-remplie depuis l\'adresse géocodée (rp9-address)', () => {
  it('remplit lf-city depuis #rp9-address quand la ville est vide et non fournie', () => {
    setupForm('Casablanca, Maroc');
    createPrefill(makeCtx()).prefillLead(card() as never);
    expect(val('lf-city')).toBe('Casablanca, Maroc');
  });

  it('une ville fournie EXPLICITEMENT l\'emporte sur l\'adresse géocodée', () => {
    setupForm('Casablanca, Maroc');
    createPrefill(makeCtx()).prefillLead(card() as never, { city: 'Agadir' });
    expect(val('lf-city')).toBe('Agadir');
  });

  it('une ville DÉJÀ saisie n\'est pas écrasée par l\'adresse géocodée', () => {
    setupForm('Casablanca, Maroc');
    (document.getElementById('lf-city') as HTMLInputElement).value = 'Rabat';
    createPrefill(makeCtx()).prefillLead(card() as never);
    expect(val('lf-city')).toBe('Rabat');
  });
});

describe('W110 — garde-fou : la preview ne POSTe JAMAIS un lead', () => {
  it('aucune route lead / simulation dans la surface du builder', () => {
    const dir = fromRoot('src/scripts/roofPro11');
    const all = (existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith('.ts')) : [])
      .map((f) => read(`src/scripts/roofPro11/${f}`))
      .concat(read('src/scripts/roof-tool-pro11.ts'))
      .join('\n');
    expect(all).not.toContain('/api/preview-lead');
    expect(all).not.toContain('/api/simulate');
    // le handoff existe bien (prefillLead est câblé)
    expect(all).toContain('prefillLead(');
  });

  it('le composant partagé DiagnosticFormEnriched n\'est PAS modifié par ce flux (toujours présent)', () => {
    // la page preview rend le composant relocalisé en haut ; le composant lui-même est intact.
    const page = read('src/pages/preview/toiture-3d-pro-11.astro');
    expect(page).toContain('<DiagnosticFormEnriched');
    // une SEULE occurrence du rendu (l'ancienne section du bas a été supprimée).
    const renders = page.match(/<DiagnosticFormEnriched/g) ?? [];
    expect(renders.length).toBe(1);
  });
});
