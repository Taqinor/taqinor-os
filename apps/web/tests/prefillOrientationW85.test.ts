// @vitest-environment jsdom
//
// W85 — handoff d'orientation du builder pro-11 vers le diagnostic enrichi.
// `prefillLead` écrivait `lf-orient = 'sud'` EN DUR, perdant l'Est-Ouest (plat)
// et chaque face d'un toit en pente. On vérifie que l'id écrit dans le `<select>`
// du diagnostic correspond à la VRAIE config gagnante lue dans `ctx` :
//   - toit en pente : la face réelle (facingAzimuthDeg) mappée sur les ids
//     enrichment.ORIENTATIONS (180→sud, 135→sud-est, 225→sud-ouest, 90→est, 270→ouest) ;
//   - toit plat (sud + est-ouest) : « sud » (la liste n'a pas d'« est-ouest »).
// Et le garde-fou permanent : AUCUN module roofPro11 ne poste un lead.
import { describe, expect, it, beforeEach } from 'vitest';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { createPrefill } from '../src/scripts/roofPro11/prefill';
import { ORIENTATIONS } from '../src/lib/enrichment';

// En jsdom `import.meta.url` n'est pas une URL `file:` → on résout depuis le cwd
// (la racine apps/web quand vitest tourne) pour le scan de sources du garde-fou.
const fromRoot = (rel: string) => resolve(process.cwd(), rel);
const read = (rel: string) => readFileSync(fromRoot(rel), 'utf-8');

// ctx minimal : prefillLead ne lit que vertices, roofType, facingAzimuthDeg et opts.reducedMotion.
type PrefillCtx = Parameters<typeof createPrefill>[0];
const makeCtx = (over: Partial<{ roofType: 'flat' | 'pitched'; facingAzimuthDeg: number }>): PrefillCtx =>
  ({
    opts: { reducedMotion: true },
    // un carré minuscule fermé → aire géodésique > 0 (peu importe la valeur exacte ici).
    vertices: [
      [-7.5, 33.5],
      [-7.4999, 33.5],
      [-7.4999, 33.5001],
      [-7.5, 33.5001],
    ],
    roofType: over.roofType ?? 'flat',
    facingAzimuthDeg: over.facingAzimuthDeg ?? 180,
  }) as unknown as PrefillCtx;

const setupForm = () => {
  // jsdom n'implémente pas scrollIntoView : prefillLead l'appelle après le pré-remplissage.
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
  document.body.innerHTML = `
    <details id="diag">
      <input id="lf-area" />
      <select id="lf-orient">
        ${ORIENTATIONS.map((o) => `<option value="${o.id}">${o.label}</option>`).join('')}
      </select>
      <input id="lf-kwc-est" />
    </details>
    <div id="simulateur"></div>
  `;
};

const orientValue = () => (document.getElementById('lf-orient') as HTMLSelectElement).value;
const card = () => ({ title: '', isReco: true, count: 10, kwc: 4, annualKwh: 6000, pct: 80, savingsLow: 0, savingsHigh: 0, why: '' });

describe('W85 — l\'orientation pré-remplie suit la config gagnante', () => {
  beforeEach(setupForm);

  it('toit plat (sud + est-ouest) → « sud » (la liste enrichment n\'a pas d\'est-ouest)', () => {
    const prefill = createPrefill(makeCtx({ roofType: 'flat' }));
    prefill.prefillLead(card() as never);
    expect(orientValue()).toBe('sud');
  });

  it('toit en pente plein sud (180°) → « sud »', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 180 })).prefillLead(card() as never);
    expect(orientValue()).toBe('sud');
  });

  it('toit en pente sud-est (135°) → « sud-est »', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 135 })).prefillLead(card() as never);
    expect(orientValue()).toBe('sud-est');
  });

  it('toit en pente sud-ouest (225°) → « sud-ouest »', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 225 })).prefillLead(card() as never);
    expect(orientValue()).toBe('sud-ouest');
  });

  it('toit en pente est (90°) → « est »', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 90 })).prefillLead(card() as never);
    expect(orientValue()).toBe('est');
  });

  it('toit en pente ouest (270°) → « ouest »', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 270 })).prefillLead(card() as never);
    expect(orientValue()).toBe('ouest');
  });

  it('face quelconque (ex. 100°) → la face enrichment LA PLUS PROCHE (est)', () => {
    createPrefill(makeCtx({ roofType: 'pitched', facingAzimuthDeg: 100 })).prefillLead(card() as never);
    expect(orientValue()).toBe('est');
  });
});

describe('W85 — garde-fou : aucun module roofPro11 ne poste un lead', () => {
  it('aucune route lead / simulation n\'est appelée dans la surface du builder', () => {
    const dir = fromRoot('src/scripts/roofPro11');
    const all = (existsSync(dir) ? readdirSync(dir).filter((f) => f.endsWith('.ts')) : [])
      .map((f) => read(`src/scripts/roofPro11/${f}`))
      .concat(read('src/scripts/roof-tool-pro11.ts'))
      .join('\n');
    expect(all).not.toContain('/api/preview-lead');
    expect(all).not.toContain('/api/simulate');
    expect(all).toContain('prefillLead(');
  });
});
