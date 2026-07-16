// WJ16 — Courbe journalière production-vs-consommation (SVG pur).
// Prouve : (a) cale l'axe sur la production RÉELLE quand fournie, (b) repli
// « année type » CLAIREMENT libellé quand absente, (c) aucune transition dans le
// SVG (l'animation vit dans la page, gatée reduced-motion), (d) profils bornés.
import { describe, expect, it } from 'vitest';
import {
  renderYearCurve,
  solarProfile,
  consumptionProfile,
} from '../src/lib/proposalCurve';

describe('WJ16 — profils horaires normalisés', () => {
  it('solarProfile — nul la nuit, max vers midi solaire, borné [0,1]', () => {
    expect(solarProfile(5)).toBe(0);
    expect(solarProfile(6.5)).toBe(0);
    expect(solarProfile(19.5)).toBe(0);
    expect(solarProfile(21)).toBe(0);
    const noon = solarProfile(13);
    expect(noon).toBeGreaterThan(0.9);
    expect(noon).toBeLessThanOrEqual(1);
  });

  it('consumptionProfile — toujours dans [0,1], bosse soirée présente', () => {
    for (let h = 5; h <= 21; h += 0.5) {
      const v = consumptionProfile(h);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
    // pic de soirée > creux de l'après-midi
    expect(consumptionProfile(20)).toBeGreaterThan(consumptionProfile(15));
  });

  // WJ119 — la double-gaussienne générique a été remplacée par BASELINE_SHAPE
  // (applianceConsumption.ts, silhouette marocaine soirée-dominante, pic
  // 19h-21h ≈26 % de l'énergie) : on épingle deux valeurs précises qui n'ont de
  // sens QUE pour cette forme (repli residentiel/normal, rétro-compatible sans
  // options), pour qu'une régression vers l'ancienne courbe soit détectée.
  it('consumptionProfile — repli résidentiel/normal porte BASELINE_SHAPE (WJ119)', () => {
    // 20h est le maximum de BASELINE_SHAPE (2.4) → normalisé à 1 exactement.
    expect(consumptionProfile(20)).toBeCloseTo(1, 9);
    // 13h (poids 1.0) / 20h (poids 2.4) = 0.41666… — signature de la forme portée,
    // très différente du plateau ~1.0 (clampé) que rendait l'ancienne gaussienne.
    expect(consumptionProfile(13)).toBeCloseTo(1 / 2.4, 6);
    // Appel sans options === repli explicite { mode: 'residentiel', variant: 'normal' }.
    expect(consumptionProfile(20)).toBe(consumptionProfile(20, { mode: 'residentiel', variant: 'normal' }));
  });
});

describe('WJ16 — rendu SVG', () => {
  it('production réelle → échelle réelle (kWh affiché), pas de mention « année type »', () => {
    const out = renderYearCurve(10000);
    expect(out.hasRealScale).toBe(true);
    expect(out.svg).toContain('<svg');
    expect(out.svg).toContain('kWh');
    expect(out.svg).not.toContain('année type');
  });

  it('production absente/nulle → repli « année type » CLAIREMENT libellé', () => {
    const noProd = renderYearCurve(null);
    expect(noProd.hasRealScale).toBe(false);
    expect(noProd.svg).toContain('année type');
    // jamais une valeur kWh fabriquée sur l'axe en mode année type
    expect(noProd.svg).not.toMatch(/\d[\d ,]*kWh/);

    expect(renderYearCurve(0).hasRealScale).toBe(false);
    expect(renderYearCurve(undefined).hasRealScale).toBe(false);
    expect(renderYearCurve(-5).hasRealScale).toBe(false);
  });

  it('le SVG NE porte AUCUNE transition (animation dans la page, reduced-motion safe)', () => {
    const out = renderYearCurve(8000);
    expect(out.svg).not.toContain('<animate');
    expect(out.svg).not.toContain('transition');
    expect(out.svg).not.toContain('@keyframes');
  });

  it('SVG accessible : role=img + title + desc', () => {
    const out = renderYearCurve(null);
    expect(out.svg).toContain('role="img"');
    expect(out.svg).toContain('<title>');
    expect(out.svg).toContain('<desc>');
  });

  it('le visuel le plus persuasif ne disparaît JAMAIS (svg non vide dans tous les cas)', () => {
    expect(renderYearCurve(12000).svg.length).toBeGreaterThan(100);
    expect(renderYearCurve(null).svg.length).toBeGreaterThan(100);
  });
});
