// WJ26 — « Tout est expliqué » : légende + annotations + visite guidée.
// Chaque test prouve qu'un chiffre affiché vient du layout serveur ou du
// payload quote, et que toute donnée absente devient « estimation
// indisponible » / null — jamais une valeur fabriquée.
import { describe, expect, it } from 'vitest';
import {
  orientationLabelFr,
  zoneAnnotations,
  walkthroughSteps,
  parseRoofLayout,
  FIGURE_UNAVAILABLE,
  type ProposalResponse,
  type RoofLayout,
} from '../src/lib/proposition';

function makeProposal(over: Partial<ProposalResponse> = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-2026-042',
    date: '22/06/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-2026-042',
      date: '22/06/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      puissance_kwc: 6.48,
      nb_panneaux: 9,
      watt_par_panneau: 720,
      prod_kwh: 10000,
      eco_s_ann: 12000,
      eco_a_ann: 15000,
      recommended: 'avec_batterie',
      totaux_sans: { ht_brut: 50000, remise: 0, ht_net: 50000, tva: 10000, ttc: 60000 },
      totaux_avec: { ht_brut: 80000, remise: 0, ht_net: 80000, tva: 16000, ttc: 96000 },
      nb_options: 2,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 60000, avec_batterie: 96000, display_total: 96000, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

function makeLayout(): RoofLayout {
  return parseRoofLayout({
    version: 1,
    zones: [
      {
        id: 'z1',
        label: 'Pan sud',
        vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001], [-7.6, 33.5001]],
        roofType: 'pitched',
        pitchDeg: 22,
        facingAzimuthDeg: 170,
        neededPanels: 6,
      },
      {
        id: 'z2',
        label: 'Terrasse',
        vertices: [[-7.61, 33.5], [-7.6099, 33.5], [-7.6099, 33.5001], [-7.61, 33.5001]],
        roofType: 'flat',
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        neededPanels: 0,
      },
    ],
  })!;
}

describe('WJ26 — orientationLabelFr', () => {
  it('mappe les azimuts sur les 8 directions FR', () => {
    expect(orientationLabelFr(180)).toBe('Sud');
    expect(orientationLabelFr(135)).toBe('Sud-Est');
    expect(orientationLabelFr(225)).toBe('Sud-Ouest');
    expect(orientationLabelFr(90)).toBe('Est');
    expect(orientationLabelFr(270)).toBe('Ouest');
    expect(orientationLabelFr(0)).toBe('Nord');
    expect(orientationLabelFr(360)).toBe('Nord');
    expect(orientationLabelFr(-90)).toBe('Ouest');
    // au plus proche : 170° → Sud
    expect(orientationLabelFr(170)).toBe('Sud');
  });
});

describe('WJ26 — zoneAnnotations (chiffres serveur uniquement)', () => {
  it('annote chaque pan : orientation, pente, panneaux, kWc calculé', () => {
    const a = zoneAnnotations(makeLayout(), 720);
    expect(a).toHaveLength(2);
    expect(a[0].label).toBe('Pan sud');
    expect(a[0].orientation).toBe('Sud');
    expect(a[0].tiltDeg).toBe(22);
    expect(a[0].roofTypeLabel).toBe('Toit en pente');
    expect(a[0].panels).toBe(6);
    // kWc = panneaux (layout serveur) × Wc/panneau (payload) — traçable.
    expect(a[0].kwc).toBe(4.32);
  });

  it('toit plat : pas de pente affichée ; zone non dimensionnée : panels/kwc null', () => {
    const a = zoneAnnotations(makeLayout(), 720);
    expect(a[1].tiltDeg).toBeNull();
    expect(a[1].roofTypeLabel).toBe('Toit plat');
    expect(a[1].panels).toBeNull();
    expect(a[1].kwc).toBeNull();
  });

  it('sans watt_par_panneau (payload), kWc = null — jamais inventé', () => {
    const a = zoneAnnotations(makeLayout(), null);
    expect(a[0].kwc).toBeNull();
    const b = zoneAnnotations(makeLayout(), undefined);
    expect(b[0].kwc).toBeNull();
  });
});

describe('WJ26 — walkthroughSteps (4 étapes, chiffres payload ou repli libellé)', () => {
  it('4 étapes dans l’ordre du récit, FR + gloss arabe', () => {
    const steps = walkthroughSteps(makeProposal());
    expect(steps.map((s) => s.id)).toEqual(['toit', 'panneaux', 'production', 'economie']);
    for (const s of steps) {
      expect(s.title.length).toBeGreaterThan(0);
      expect(s.titleAr.length).toBeGreaterThan(0);
      expect(s.body.length).toBeGreaterThan(0);
    }
  });

  it('chiffres tirés du payload : panneaux, kWc, production, économie', () => {
    const steps = walkthroughSteps(makeProposal());
    expect(steps[1].body).toContain('9 panneaux');
    expect(steps[1].body).toContain('6,48 kWc');
    expect(steps[2].body).toContain('10 000 kWh');
    // Option recommandée = avec batterie → eco_a_ann = 15 000 MAD.
    expect(steps[3].body).toContain('15 000 MAD');
    expect(steps[3].body).toContain('82-21');
  });

  it('payload incomplet → « estimation indisponible », jamais un chiffre inventé', () => {
    const p = makeProposal({
      quote: {
        nb_panneaux: undefined,
        puissance_kwc: undefined,
        prod_kwh: undefined,
        eco_s_ann: undefined,
        eco_a_ann: undefined,
      },
    });
    const steps = walkthroughSteps(p);
    expect(steps[1].body).toContain(FIGURE_UNAVAILABLE);
    expect(steps[2].body).toContain(FIGURE_UNAVAILABLE);
    expect(steps[3].body).toContain(FIGURE_UNAVAILABLE);
    // Aucun montant MAD fabriqué dans les étapes sans donnée.
    expect(steps[3].body).not.toMatch(/\d+ MAD/);
  });
});
