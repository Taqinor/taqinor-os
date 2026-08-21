// WJ16 — Courbe journalière production-vs-consommation (SVG pur).
// Prouve : (a) cale l'axe sur la production RÉELLE quand fournie, (b) repli
// « année type » CLAIREMENT libellé quand absente, (c) aucune transition dans le
// SVG (l'animation vit dans la page, gatée reduced-motion), (d) profils bornés.
import { describe, expect, it } from 'vitest';
import {
  renderYearCurve,
  solarProfile,
  consumptionProfile,
  consumptionShapeHours,
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

  // WJ119 — la double-gaussienne générique a été remplacée par une silhouette
  // marocaine soirée-dominante. CJ1 — ce repli n'est plus l'unique
  // `BASELINE_SHAPE` mais la silhouette d'occupation « présence partielle »
  // (dayProfiles.OCCUPANCY_SHAPES), le milieu honnête des trois quand le
  // backend n'a rien dit. On épingle deux valeurs précises qui n'ont de sens
  // QUE pour cette forme, pour qu'une régression soit détectée.
  it('consumptionProfile — repli résidentiel/normal = silhouette « présence partielle » (CJ1)', () => {
    // 20h est le maximum de la silhouette (2.2) → normalisé à 1 exactement.
    expect(consumptionProfile(20)).toBeCloseTo(1, 9);
    // 13h (poids 1.1) / 20h (poids 2.2) = 0.5 — signature de la forme portée,
    // très différente du plateau ~1.0 (clampé) que rendait l'ancienne gaussienne.
    expect(consumptionProfile(13)).toBeCloseTo(1.1 / 2.2, 6);
    // Appel sans options === repli explicite { mode: 'residentiel', variant: 'normal' }.
    expect(consumptionProfile(20)).toBe(consumptionProfile(20, { mode: 'residentiel', variant: 'normal' }));
    // …et ce repli est bien « présence partielle », jamais un quatrième profil.
    expect(consumptionProfile(13)).toBe(
      consumptionProfile(13, { mode: 'residentiel', occupancy: 'presence_partielle' }),
    );
  });

  // PACT-battery (2026-08-15) — consumptionShapeHours est la SEULE fonction qui
  // échantillonne la silhouette pour le simulateur batterie (rendu serveur
  // initial ET recalcul client au changement d'onglet Standard/Été/Ramadan
  // pendant que le calque batterie est actif) : elle doit rester un simple
  // échantillonnage heure par heure de consumptionProfile, sans rien inventer.
  it('consumptionShapeHours — échantillonne consumptionProfile heure par heure', () => {
    const shape = consumptionShapeHours(24, { mode: 'residentiel', variant: 'normal' });
    expect(shape).toHaveLength(24);
    for (let h = 0; h < 24; h++) {
      expect(shape[h]).toBe(consumptionProfile(h, { mode: 'residentiel', variant: 'normal' }));
    }
  });

  it('consumptionShapeHours — la variante change bien le tableau produit', () => {
    const normal = consumptionShapeHours(24, { mode: 'residentiel', variant: 'normal' });
    const ete = consumptionShapeHours(24, { mode: 'residentiel', variant: 'ete' });
    const ramadan = consumptionShapeHours(24, { mode: 'residentiel', variant: 'ramadan' });
    expect(ete).not.toEqual(normal);
    expect(ramadan).not.toEqual(normal);
  });

  it('consumptionShapeHours — repli sur un tableau vide pour une longueur nulle/négative', () => {
    expect(consumptionShapeHours(0)).toEqual([]);
    expect(consumptionShapeHours(-3)).toEqual([]);
  });
});

describe('WJ16 — rendu SVG', () => {
  it('production réelle → échelle réelle (kWh affiché), pas de mention « année type »', () => {
    const out = renderYearCurve(10000);
    expect(out.hasRealScale).toBe(true);
    expect(out.svg).toContain('<svg');
    expect(out.svg).toContain('kWh');
    expect(out.svg).not.toContain('année type');
    // CJ1 — sans bloc backend servi, le repli reste la cloche sin² + prod/365.
    expect(out.hasServedShape).toBe(false);
    expect(out.hasRealConsScale).toBe(false);
  });

  // CJ1 — LE DÉFAUT D'UNITÉ CORRIGÉ : un « pic » est une PUISSANCE. Le repli
  // annuel affichait « pic ≈ 14,3 kWh » — la même valeur, avec la mauvaise
  // unité. Ce test vaut sur le chemin de repli comme sur le chemin servi.
  it('le repère de pointe est libellé en kW, JAMAIS en kWh (repli annuel compris)', () => {
    const out = renderYearCurve(10000);
    // Le <text> visible du repère (le seul endroit où le client LIT le pic).
    const peakText = out.svg.match(/>pic ≈ ([^<]*)</)?.[1] ?? '';
    expect(peakText).toContain('kW');
    expect(peakText).not.toContain('kWh');
    // …et l'attribut tap-to-reveal qui reprend le même libellé.
    const peakAttr = out.svg.match(/data-peak="([^"]*)"/)?.[1] ?? '';
    expect(peakAttr).toContain('kW');
    expect(peakAttr).not.toContain('kWh');
    // La valeur elle-même n'a pas changé : seule son unité est enfin juste
    // (moyenne journalière / 4,6 h équivalent pleine puissance).
    const dailyAvg = 10000 / 365;
    const expected = (Math.round((dailyAvg / 4.6) * 10) / 10).toString().replace('.', ',');
    expect(peakText).toContain(expected);
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
