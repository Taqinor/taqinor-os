// SUITE « ESTIMATEUR COURANT » — contrat de l'estimateur de toiture actuel.
//
// Route courante = /preview/toiture-3d-pro-11 (la plus haute des pro-N).
// Le cerveau courant est composé : V2 (toit plat) + V3 (pose affleurante pente)
// + V5 (jambe PVGIS pente) + V7 (optimiseur vivant plat) + V8 (optimiseur
// vivant pente). Le fichier de base estimatorBrain.ts est l'ORIGINAL V1 (la
// route courante ne l'utilise plus). Cette suite affirme, contre les exports
// RÉELS, les garanties énumérées (balayage→argmax, plafond besoin, borne
// empreinte, signe d'azimut PVGIS, formule de production, pente coplanaire,
// verrous de l'optimiseur, tarif sélectif, honnêteté) + l'interaction de page
// et la dégradation gracieuse atteignables sans WebGL/carte.
//
// La carte/3D ne rend pas ici (clés Cloudflare, pas de WebGL en CI) — tout est
// ancré à du DOM/JS vérifiable et à de la logique pure, jamais à des pixels.
// Les internes par version sont aussi couverts par estimatorBrainV2/V7/V8 ;
// cette suite ajoute le contrat consolidé de l'estimateur courant + la page.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  recommend, packConfig, neededPanelsForTarget, optimalSouthTiltDeg, tiltSweepSouth,
  specificYield, productionKwh, aspectForAzimuth, billMAD, billToAnnualKwh, annualSavingsMad,
  tariffForCity, REGIE_TARIFF, PANEL2_WATT, TILT_SWEEP_MIN, TILT_SWEEP_STEP,
} from '../src/lib/estimatorBrainV2';
import { PANEL2_LONG_M, PANEL2_SHORT_M } from '../src/lib/roofPro2';
import { recommendPitched, packFlushPlane, FLUSH_MAINTENANCE_GAP_M, PITCH_PRESETS_DEG, type RoofPlane } from '../src/lib/estimatorBrainV3';
import { pitchedPlaneLeg, aspectFromCompass, PITCHED_MOUNTINGPLACE } from '../src/lib/estimatorBrainV5';
import { solveLive } from '../src/lib/estimatorBrainV7';
import { solveLivePitched } from '../src/lib/estimatorBrainV8';
import { geodesicAreaM2, pointInPolygon, orientationToAspect, type LngLat } from '../src/lib/roof';
import { createRoofTypeSelect, type RoofTypeButton } from '../src/lib/roofTypeSelect';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// ─────────── fixtures géométriques (idiome des suites V2/V7/V8) ───────────
const LAT = 33.59; // Casablanca
const OPT = optimalSouthTiltDeg(LAT);

function squareRing(side: number, lng0 = -7.62, lat0 = 33.59): LngLat[] {
  const dLat = side / 111320;
  const dLng = side / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

// ════════════════════ PAGE — interaction sans WebGL ════════════════════
describe('page pro-11 — sélecteur de type de toit (régression bouton inerte)', () => {
  // Stub DOM minimal (aucun jsdom) — même idiome que roofTypeSelectPro9.test.ts.
  class FakeButton implements RoofTypeButton {
    private attrs = new Map<string, string>();
    private handlers: Array<() => void> = [];
    constructor(rooftype: string, pressed: boolean) {
      this.attrs.set('data-rooftype', rooftype);
      this.attrs.set('aria-pressed', String(pressed));
    }
    getAttribute(n: string) { return this.attrs.has(n) ? (this.attrs.get(n) as string) : null; }
    setAttribute(n: string, v: string) { this.attrs.set(n, v); }
    addEventListener(t: 'click', h: () => void) { if (t === 'click') this.handlers.push(h); }
    click() { for (const h of this.handlers) h(); }
    get pressed() { return this.getAttribute('aria-pressed') === 'true'; }
  }
  const makeDoc = (b: FakeButton[]) => ({ querySelectorAll: () => b });

  it('« Toit plat » répond au clic et entre dans le flux plat', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));
    pitched.click();
    expect(sel.get()).toBe('pitched');
    flat.click();
    expect(sel.get()).toBe('flat'); // le bouton plat n'est pas inerte
    expect(flat.pressed).toBe(true);
    expect(pitched.pressed).toBe(false);
  });

  it('« Toit en pente » répond au clic et entre dans le flux pente', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));
    let notified: string | null = null;
    sel.subscribe((t) => { notified = t; });
    pitched.click();
    expect(sel.get()).toBe('pitched');
    expect(notified).toBe('pitched'); // abonnement déclenché au changement
    expect(pitched.pressed).toBe(true);
  });

  it('un tap mobile = un clic (un seul gestionnaire couvre les deux plateformes)', () => {
    // Le code écoute UNIQUEMENT « click » par conception (un tap déclenche click).
    expect(read('../src/lib/roofTypeSelect.ts')).toContain("addEventListener('click'");
    // .set() programmatique reflète + notifie (utilisé par l'optimiseur).
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));
    sel.set('pitched');
    expect(sel.get()).toBe('pitched');
    expect(pitched.pressed).toBe(true);
  });
});

describe('page pro-11 — DOM des flux plat/pente & optimiseur', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-11.astro');

  it('route privée : noindex', () => {
    expect(page).toContain('noindex={true}');
  });

  it('les deux puces de type de toit existent avec leurs libellés FR', () => {
    expect(page).toContain('data-rooftype="flat"');
    expect(page).toContain('data-rooftype="pitched"');
    expect(page).toContain('Toit plat');
    expect(page).toContain('Toit en pente / tuiles');
  });

  it('le flux PENTE expose préréglages de pente + face du pan ; le flux PLAT son inclinaison/orientation', () => {
    // Bloc pente (caché par défaut) avec préréglages data-pitch + faces data-facing.
    expect(page).toContain('id="rp9-pitched-controls"');
    for (const p of [15, 22, 30, 45]) expect(page).toContain(`data-pitch="${p}"`);
    for (const f of [180, 135, 225, 90, 270]) expect(page).toContain(`data-facing="${f}"`);
    // Bloc plat avec orientation + inclinaison.
    expect(page).toContain('id="rp9-flat-controls"');
    expect(page).toContain('data-family="south"');
    expect(page).toContain('data-tilt="reco"');
  });

  it('optimiseur vivant : bouton Réinitialiser + verrous cumulatifs + badges « Recommandé »', () => {
    expect(page).toContain('id="rp9-optimum"');
    expect(page).toContain('Réinitialiser');
    expect(page.toLowerCase()).toContain('verrou'); // la note explique l'accumulation des verrous
    expect(page).toContain('rp9-reco-badge');
  });

  it('dégradation gracieuse : repli 2D + diagnostic 60 s (carte/3D/JS absents)', () => {
    expect(page).toContain('id="rp9-fallback"');
    expect(page).toContain('/preview/toiture'); // lien vers l'outil 2D
    expect(page).toContain('#simulateur'); // lien vers le diagnostic 60 s
    expect(page).toContain('<noscript>'); // chemin sans JS
  });
});

// ════════════════════ CERVEAU — toit plat (recommend V2) ════════════════════
describe('cerveau plat — balayage, argmax, plafond & borne empreinte', () => {
  it('le balayage Sud couvre TILT_SWEEP_MIN→optimal par pas fins, et choisit le max posé', () => {
    expect(TILT_SWEEP_MIN).toBe(5);
    expect(TILT_SWEEP_STEP).toBe(1);
    const ring = squareRing(24);
    const needed = neededPanelsForTarget(billToAnnualKwh(2500) , LAT);
    const sweep = tiltSweepSouth(ring, LAT, needed);
    expect(sweep.best.tiltDeg).toBeGreaterThanOrEqual(TILT_SWEEP_MIN);
    expect(sweep.best.tiltDeg).toBeLessThanOrEqual(OPT);
    expect(sweep.maxRoofEnergyTiltDeg).toBeGreaterThanOrEqual(TILT_SWEEP_MIN);
  });

  it('toit spacieux : garde l’inclinaison optimale, couvre le besoin (zéro overfill)', () => {
    const rec = recommend(squareRing(40), LAT, 1500);
    expect(rec.roofLimited).toBe(false);
    expect(rec.recommendedTiltDeg).toBe(OPT);
    expect(rec.flatterTiltChosen).toBe(false);
    expect(rec.recommended.count).toBeLessThanOrEqual(rec.neededPanels); // plafond besoin
  });

  it('toit limité : plafond besoin TOUJOURS respecté, inclinaison ≤ optimale', () => {
    const rec = recommend(squareRing(8), LAT, 9000);
    expect(rec.roofLimited).toBe(true);
    expect(rec.recommended.count).toBeLessThanOrEqual(rec.neededPanels);
    expect(rec.recommendedTiltDeg).toBeLessThanOrEqual(OPT);
  });

  it('l’optimum recommandé apparaît bien comme une ligne du comparatif (porte le ✓)', () => {
    const rec = recommend(squareRing(14), LAT, 4000);
    expect(rec.comparison.some((c) => c.id === rec.recommended.id)).toBe(true);
  });

  it('borne empreinte : Σ(empreintes panneaux) ≤ surface utile ≤ surface tracée', () => {
    const pack = packConfig(squareRing(24), LAT, { family: 'south', tiltDeg: 20 });
    const footprint = pack.best.count * pack.best.footprintPerPanelM2;
    expect(footprint).toBeLessThanOrEqual(pack.usableAreaM2 + 1e-6);
    expect(pack.usableAreaM2).toBeLessThanOrEqual(pack.areaM2 + 1e-6);
  });

  it('obstacle keep-out : une obstruction réduit la surface utile et le nombre posé', () => {
    const ring = squareRing(24);
    const obstruction = squareRing(6); // ~36 m² au centre du toit
    const clean = packConfig(ring, LAT, { family: 'south', tiltDeg: 20 });
    const blocked = packConfig(ring, LAT, { family: 'south', tiltDeg: 20, obstructions: [obstruction] });
    expect(blocked.usableAreaM2).toBeLessThan(clean.areaM2 - 10);
    expect(blocked.best.count).toBeLessThanOrEqual(clean.best.count);
  });

  it('déterminisme : mêmes entrées → même recommandation', () => {
    const a = recommend(squareRing(20), LAT, 1500);
    const b = recommend(squareRing(20), LAT, 1500);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });
});

// ════════════════════ CERVEAU — azimut PVGIS & production ════════════════════
describe('cerveau — signe d’azimut PVGIS & formule de génération', () => {
  it('mapping de signe exact : S=0, E=−90, O=+90, N=180', () => {
    // Mapping compas → aspect (pente / face du pan).
    expect(aspectFromCompass(180)).toBe(0);
    expect(aspectFromCompass(90)).toBe(-90);
    expect(aspectFromCompass(270)).toBe(90);
    expect(aspectFromCompass(0)).toBe(180);
    // Mapping orientation (outil 2D) — même convention.
    expect(orientationToAspect('sud')).toBe(0);
    expect(orientationToAspect('est')).toBe(-90);
    expect(orientationToAspect('ouest')).toBe(90);
    expect(orientationToAspect('nord')).toBe(180);
    // aspectForAzimuth (famille Sud) : 180→0, 90→−90, 270→+90.
    expect(aspectForAzimuth('south', 180)).toBe(0);
    expect(aspectForAzimuth('south', 90)).toBe(-90);
    expect(aspectForAzimuth('south', 270)).toBe(90);
    expect(aspectForAzimuth('eastwest', 90)).toBe(0);
  });

  it('génération = kWc × rendement spécifique (Sud) ; E-O = moitié Est + moitié Ouest', () => {
    const kwc = 5;
    expect(productionKwh(LAT, 'south', 20, kwc, 0)).toBeCloseTo(kwc * specificYield(LAT, 20, 0), 6);
    const ew = productionKwh(LAT, 'eastwest', 10, 4, 0);
    expect(ew).toBeCloseTo(2 * specificYield(LAT, 10, -90) + 2 * specificYield(LAT, 10, 90), 6);
  });

  it('le rendement baisse honnêtement hors plein sud', () => {
    expect(specificYield(LAT, OPT, 0)).toBeGreaterThan(specificYield(LAT, OPT, 45));
    expect(specificYield(LAT, OPT, 0)).toBeGreaterThan(specificYield(LAT, OPT, -45));
  });
});

// ════════════════════ CERVEAU — tarif, inversion & honnêteté ════════════════════
describe('cerveau — tarif sélectif ONEE, inversion facture & plafond d’économies', () => {
  it('barème sélectif (seuil 150 kWh), top ≈ 1,60 — JAMAIS l’ancien 1,4 ni le 1,66 force-motrice', () => {
    expect(REGIE_TARIFF.selectiveThresholdKwh).toBe(150);
    expect(REGIE_TARIFF.selective.length).toBeGreaterThanOrEqual(3);
    expect(REGIE_TARIFF.selective[REGIE_TARIFF.selective.length - 1].rate).toBeCloseTo(1.5958, 4);
    const rates = [...REGIE_TARIFF.progressive, ...REGIE_TARIFF.selective].map((t) => t.rate);
    expect(rates).not.toContain(1.4); // ancien plat
    expect(rates).not.toContain(1.66); // ancien tarif force-motrice retiré
    expect(tariffForCity('Casablanca')).toBe(REGIE_TARIFF);
    expect(tariffForCity()).toBe(REGIE_TARIFF);
  });

  it('inversion facture → consommation : monotone, fidèle, jamais sur-estimée (sélectif)', () => {
    // Inversion monotone non-décroissante (plus de facture ⇒ plus de conso).
    const k = (B: number) => billToAnnualKwh(B);
    expect(k(500)).toBeLessThanOrEqual(k(800));
    expect(k(800)).toBeLessThanOrEqual(k(1500));
    expect(k(1500)).toBeLessThanOrEqual(k(5000));
    expect(k(5000)).toBeLessThanOrEqual(k(12000));
    // La facture reconstituée ne dépasse JAMAIS la cible (un palier sélectif peut
    // « sauter » par-dessus une facture irréelle — l'inverse retombe juste dessous).
    for (const B of [800, 1500, 5000, 12000]) {
      expect(billMAD(billToAnnualKwh(B) / 12)).toBeLessThanOrEqual(B + 1e-6);
    }
    // Dans la tranche haute ouverte (continue, > 510 kWh), l'inversion est fidèle.
    for (const B of [1500, 5000, 12000]) {
      expect(billMAD(billToAnnualKwh(B) / 12)).toBeCloseTo(B, 0);
    }
  });

  it('honnêteté : l’économie ne dépasse JAMAIS le coût énergie évitable', () => {
    const consKwhYr = 6000;
    const consMo = consKwhYr / 12;
    const avoidable = billMAD(consMo) * 12;
    const s = annualSavingsMad(100000 /* production énorme */, consKwhYr);
    expect(s.high).toBeLessThanOrEqual(avoidable + 1e-6);
    expect(s.high).toBeGreaterThanOrEqual(s.low);
    expect(s.low).toBeGreaterThanOrEqual(0);
  });

  it('constante panneau = Canadian Solar TOPBiHiKu7 720 W (2,384 × 1,303 m, 0,72 kWc)', () => {
    expect(PANEL2_WATT).toBe(720);
    expect(PANEL2_LONG_M).toBeCloseTo(2.384, 3);
    expect(PANEL2_SHORT_M).toBeCloseTo(1.303, 3);
    expect(PANEL2_WATT / 1000).toBeCloseTo(0.72, 2);
  });
});

// ════════════════════ CERVEAU — toit en pente (V3/V5/V8) ════════════════════
describe('cerveau pente — pose affleurante coplanaire, honnêteté nord, PVGIS bâtiment', () => {
  const southPlane: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 180 };

  it('recommendPitched pose des panneaux et respecte le plafond besoin', () => {
    const rec = recommendPitched([southPlane], LAT, 1500);
    expect(rec.totalPlacedCount).toBeGreaterThan(0);
    expect(rec.totalPlacedCount).toBeLessThanOrEqual(rec.neededPanels);
    expect(rec.planes.length).toBeGreaterThan(0);
  });

  it('honnêteté : un pan orienté nord est signalé et écarté', () => {
    const northPlane: RoofPlane = { ring: squareRing(20), pitchDeg: 30, facingAzimuthDeg: 0 };
    const rec = recommendPitched([northPlane], LAT, 1500);
    expect(rec.skippedNorth).toBeGreaterThanOrEqual(1);
  });

  it('pose AFFLEURANTE : jeu de maintenance constant 0,15 m, AUCUN pas inter-rangées solaire', () => {
    expect(FLUSH_MAINTENANCE_GAP_M).toBe(0.15);
    const flush = packFlushPlane(southPlane);
    // Le pas affleurant (empreinte + 0,15) est bien plus serré que le pas anti-ombre
    // d'une pose sur racks inclinés à plat (mêmes ~30°) → pas d'écartement solaire.
    const rack = packConfig(squareRing(20), LAT, { family: 'south', tiltDeg: 30 });
    expect(flush.best.rowPitchM).toBeLessThan(rack.best.rowPitchM);
    // Le pas affleurant inclut le jeu de maintenance mais aucun écartement anti-ombre.
    expect(flush.best.rowPitchM).toBeGreaterThan(FLUSH_MAINTENANCE_GAP_M);
  });

  it('chaque panneau posé tombe à l’intérieur du polygone tracé', () => {
    const flush = packFlushPlane(southPlane);
    expect(flush.best.panels.length).toBeGreaterThan(0);
    for (const p of flush.best.panels) {
      expect(pointInPolygon([p.cx, p.cy], flush.ringENU)).toBe(true);
    }
  });

  it('production pente via une seule jambe PVGIS à pente=inclinaison, face=aspect, pose bâtiment', () => {
    expect(PITCHED_MOUNTINGPLACE).toBe('building');
    expect(pitchedPlaneLeg(30, 180, 5)).toEqual({ kwc: 5, tiltDeg: 30, aspect: 0 });
    expect(pitchedPlaneLeg(22, 90, 3).aspect).toBe(-90);
    expect(PITCH_PRESETS_DEG).toContain(30);
  });
});

// ════════════════════ CERVEAU — optimiseur vivant (verrous) ════════════════════
describe('optimiseur vivant PLAT (V7) — verrous tenus, cumulés, Réinitialiser', () => {
  const ring = squareRing(22);

  it('verrouiller une inclinaison la TIENT pendant que le reste se re-résout', () => {
    const locked = solveLive(ring, LAT, 1500, [], { tiltDeg: 10 });
    expect(locked.winner.tiltDeg).toBe(10);
  });

  it('les verrous s’ACCUMULENT (orientation + disposition tenues ensemble)', () => {
    const r = solveLive(ring, LAT, 1500, [], { orientation: 'eastwest', layout: 'portrait' });
    expect(r.winner.orientation).toBe('eastwest');
    expect(r.winner.layout).toBe('portrait');
  });

  it('Réinitialiser (aucun verrou) → le gagnant contraint = le gagnant global', () => {
    const r = solveLive(ring, LAT, 1500, [], {});
    expect(r.winner.orientation).toBe(r.globalWinner.orientation);
    expect(r.winner.tiltDeg).toBe(r.globalWinner.tiltDeg);
    expect(r.winner.layout).toBe(r.globalWinner.layout);
  });

  it('« Recommandé » par axe est exposé et porte des valeurs d’axe valides', () => {
    const r = solveLive(ring, LAT, 1500, [], { tiltDeg: 10 });
    expect(['south', 'aligned', 'eastwest']).toContain(r.recommended.orientation);
    expect(['portrait', 'landscape']).toContain(r.recommended.layout);
    expect(['keep', 'remove']).toContain(r.recommended.margin);
    expect(typeof r.recommended.tiltDeg).toBe('number');
    expect(r.recommended.need).toBe(r.neededPanels);
  });

  it('déterminisme : mêmes entrées → même résultat vivant', () => {
    expect(JSON.stringify(solveLive(ring, LAT, 1500, [], {}))).toBe(JSON.stringify(solveLive(ring, LAT, 1500, [], {})));
  });
});

describe('optimiseur vivant PENTE (V8) — pas d’axe inclinaison/orientation', () => {
  const ring = squareRing(20);

  it('pente & face IMPOSÉES par la toiture (jamais des axes libres)', () => {
    const r = solveLivePitched(ring, LAT, 1500, 30, 180, [], {});
    expect(r.pitchDeg).toBe(30);
    expect(r.facingAzimuthDeg).toBe(180);
    // Le « Recommandé » ne porte QUE disposition / marge / besoin (pas d'inclinaison ni d'orientation).
    expect(Object.keys(r.recommended).sort()).toEqual(['layout', 'margin', 'need']);
  });

  it('verrou de disposition tenu ; déterminisme', () => {
    const locked = solveLivePitched(ring, LAT, 1500, 30, 180, [], { layout: 'portrait' });
    expect(locked.winner.layout).toBe('portrait');
    expect(JSON.stringify(solveLivePitched(ring, LAT, 1500, 30, 180, [], {})))
      .toBe(JSON.stringify(solveLivePitched(ring, LAT, 1500, 30, 180, [], {})));
  });
});

// ════════════════════ GÉOMÉTRIE de base ════════════════════
describe('géométrie — aire géodésique & déterminisme', () => {
  it('geodesicAreaM2 d’un carré 20 m ≈ 400 m²', () => {
    expect(geodesicAreaM2(squareRing(20))).toBeCloseTo(400, -1); // ~400, tolérance 5 m²
  });

  it('déterminisme géométrique', () => {
    expect(geodesicAreaM2(squareRing(20))).toBe(geodesicAreaM2(squareRing(20)));
  });
});
