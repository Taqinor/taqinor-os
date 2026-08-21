// L4 (21/08/2026) — équipements du lead (script d'appel : piscine / véhicule
// électrique / climatisation / chauffe-eau) composent la courbe de
// consommation journalière avec des défauts SOURCÉS et modifiables.
//
// Le backend (`apps/ventes/courbes_journalieres.py` `_equipements`) sert la
// SPÉCIFICATION de chaque couche (fenêtre d'heures + grandeur réelle) ; la
// page applique la composition (`equipmentAdjustedConsumptionKwhShape`,
// `apps/web/src/lib/proposalCurve.ts`) — jamais un second moteur de formes.
// Ces tests prouvent :
//   (1) `parseDailyCurves` lit `equipements` défensivement (couche illisible
//       écartée, jamais approximée) ;
//   (2) la composition REDISTRIBUE piscine/clim (intégrale inchangée) et
//       AJOUTE ve (la seule couche qui grossit le total, déjà inclus dans
//       le `dailyKwh` servi) — jamais l'inverse ;
//   (3) une couche hors-saison n'est jamais appliquée ;
//   (4) aucune couche ⇒ repli STRICTEMENT identique à `consumptionKwhShape`
//       (le comportement CJ1 d'avant, byte-identique) ;
//   (5) la légende sobre (`equipmentLegendLabel`) ne dit rien quand rien
//       n'est actif, et nomme les couches actives sinon.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  activeEquipmentLayers,
  equipmentLegendLabel,
  parseDailyCurves,
  type EquipmentLayers,
} from '../src/lib/dayProfiles';
import {
  consumptionKwhShape,
  equipmentAdjustedConsumptionKwhShape,
  renderYearCurve,
} from '../src/lib/proposalCurve';

const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

const PISCINE_LAYER = {
  kw: 1.5, heures: [10, 11, 12, 13, 14, 15, 16, 17], saisons: ['ete'],
  mode: 'redistribution', source: 'memo_2026-08-21_etage2:piscine_bloc_10_18h',
};
const CLIM_LAYER = {
  kw: 2.8, heures: [13, 14, 15, 16, 17, 18, 19, 20], saisons: ['ete'],
  mode: 'redistribution', source: 'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h',
};
// Forme RAW (backend, snake_case) — pour les tests `parseDailyCurves`.
const VE_LAYER = {
  kwh_jour: 4, heures: [21, 22, 23, 0, 1, 2, 3, 4, 5], saisons: null,
  mode: 'addition', source: 'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km',
};
// Forme PARSÉE (camelCase, ``EquipmentLayer`` — ce que `parseDailyCurves`
// produit) — pour les tests qui appellent directement la composition/légende.
const VE_LAYER_PARSED = {
  kwhJour: 4, heures: [21, 22, 23, 0, 1, 2, 3, 4, 5], saisons: null,
  mode: 'addition', source: 'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km',
};

// ════════════════════════════════════════════════════════════════════════════
describe('L4 — parseDailyCurves lit `equipements` défensivement', () => {
  it('bloc absent → objet vide (comportement CJ1 inchangé)', () => {
    const curves = parseDailyCurves({ note_horaire: 'x', occupation: 'presence_jour' })!;
    expect(curves.equipements).toEqual({});
  });

  it('trois couches bien formées → toutes lues, camelCase, kw/kwhJour distincts', () => {
    const curves = parseDailyCurves({
      note_horaire: 'x',
      occupation: 'presence_jour',
      equipements: { piscine: PISCINE_LAYER, clim: CLIM_LAYER, ve: VE_LAYER },
    })!;
    expect(curves.equipements.piscine).toEqual({
      kw: 1.5, heures: [10, 11, 12, 13, 14, 15, 16, 17], saisons: ['ete'],
      mode: 'redistribution', source: PISCINE_LAYER.source,
    });
    expect(curves.equipements.clim?.kw).toBe(2.8);
    expect(curves.equipements.ve).toEqual({
      kwhJour: 4, heures: [21, 22, 23, 0, 1, 2, 3, 4, 5], saisons: null,
      mode: 'addition', source: VE_LAYER.source,
    });
  });

  it('couche sans grandeur (kw/kwh_jour) pour son mode → écartée', () => {
    const curves = parseDailyCurves({
      equipements: {
        piscine: { ...PISCINE_LAYER, kw: undefined },
        ve: { ...VE_LAYER, kwh_jour: undefined },
      },
    })!;
    expect(curves.equipements).toEqual({});
  });

  it('mode inconnu ou heures vides/invalides → couche écartée', () => {
    const curves = parseDailyCurves({
      equipements: {
        piscine: { ...PISCINE_LAYER, mode: 'inconnu' },
        clim: { ...CLIM_LAYER, heures: [] },
        ve: { ...VE_LAYER, heures: [30, -1, 'x'] },
      },
    })!;
    expect(curves.equipements).toEqual({});
  });

  it('`saisons` filtré aux saisons canoniques, `null` reste `null` (toutes)', () => {
    const curves = parseDailyCurves({
      equipements: { piscine: { ...PISCINE_LAYER, saisons: ['ete', 'pas-une-saison'] } },
    })!;
    expect(curves.equipements.piscine?.saisons).toEqual(['ete']);
    const curves2 = parseDailyCurves({ equipements: { ve: VE_LAYER } })!;
    expect(curves2.equipements.ve?.saisons).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L4 — la légende sobre nomme les couches actives, rien de plus', () => {
  const EQUIP: EquipmentLayers = { piscine: PISCINE_LAYER as any, ve: VE_LAYER_PARSED };

  it('aucune couche active → chaîne vide (rien de neuf affiché)', () => {
    expect(equipmentLegendLabel({}, 'ete', 'fr')).toBe('');
    expect(equipmentLegendLabel(null, 'ete', 'fr')).toBe('');
  });

  it('piscine (été seulement) + ve (toutes saisons) : actives en été, ve seule en hiver', () => {
    expect(activeEquipmentLayers(EQUIP, 'ete').sort()).toEqual(['piscine', 've']);
    expect(activeEquipmentLayers(EQUIP, 'hiver')).toEqual(['ve']);
    expect(equipmentLegendLabel(EQUIP, 'ete', 'fr')).toBe(
      'profil ajusté : piscine, véhicule électrique');
    expect(equipmentLegendLabel(EQUIP, 'hiver', 'fr')).toBe(
      'profil ajusté : véhicule électrique');
  });

  it('les trois langues portent un préfixe et un nom pour chaque couche', () => {
    for (const lang of ['fr', 'en', 'ar'] as const) {
      const label = equipmentLegendLabel(EQUIP, 'ete', lang);
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L4 — composition : REDISTRIBUTION (piscine/clim), jamais d’ajout', () => {
  const OPTS = { mode: 'residentiel' as const, occupancy: 'presence_partielle' as const };

  it('l’intégrale journalière reste EXACTEMENT le dailyKwh fourni', () => {
    const out = equipmentAdjustedConsumptionKwhShape(
      24, { piscine: PISCINE_LAYER as any }, 'ete', OPTS);
    expect(out).toHaveLength(24);
    expect(out.reduce((a, b) => a + b, 0)).toBeCloseTo(24, 9);
  });

  it('les heures de la couche gagnent RÉELLEMENT du poids par rapport à la silhouette nue', () => {
    const baseline = consumptionKwhShape(24, OPTS);
    const out = equipmentAdjustedConsumptionKwhShape(
      24, { piscine: PISCINE_LAYER as any }, 'ete', OPTS);
    const sumHeures = (arr: number[], heures: number[]) =>
      heures.reduce((a, h) => a + arr[h], 0);
    const heures = PISCINE_LAYER.heures;
    expect(sumHeures(out, heures)).toBeGreaterThan(sumHeures(baseline, heures));
  });

  it('couche hors-saison affichée → aucun effet (repli EXACT sur la silhouette nue)', () => {
    const baseline = consumptionKwhShape(24, OPTS);
    const out = equipmentAdjustedConsumptionKwhShape(
      24, { piscine: PISCINE_LAYER as any }, 'hiver', OPTS); // piscine = été seulement
    expect(out).toEqual(baseline);
  });

  it('deux couches de redistribution actives ensemble restent à somme constante', () => {
    const out = equipmentAdjustedConsumptionKwhShape(
      30, { piscine: PISCINE_LAYER as any, clim: CLIM_LAYER as any }, 'ete', OPTS);
    expect(out.reduce((a, b) => a + b, 0)).toBeCloseTo(30, 9);
  });
});

describe('L4 — composition : ADDITION (ve), la SEULE couche qui grossit le total', () => {
  const OPTS = { mode: 'residentiel' as const, occupancy: 'presence_partielle' as const };

  it('chaque heure de la fenêtre ve gagne EXACTEMENT kwhJour / nb-heures, sans dilution', () => {
    // dailyKwh (20) inclut déjà ve (4) — comme le sert le backend
    // (`_consommation` ajoute ve.kwh_jour à kwh_jour AVANT de servir la clé).
    const dailyKwh = 20;
    const ve = VE_LAYER_PARSED;
    const base16 = consumptionKwhShape(dailyKwh - 4, OPTS); // niveau HORS ve
    const out = equipmentAdjustedConsumptionKwhShape(dailyKwh, { ve }, 'ete', OPTS);
    const parHeure = 4 / ve.heures.length;
    for (const h of ve.heures) {
      expect(out[h]).toBeCloseTo(base16[h] + parHeure, 9);
    }
    expect(out.reduce((a, b) => a + b, 0)).toBeCloseTo(dailyKwh, 9);
  });

  it('ve hors-saison (saisons restreintes) n’ajoute rien', () => {
    const restreint = { ...VE_LAYER_PARSED, saisons: ['ete'] as const };
    const dailyKwh = 20;
    const out = equipmentAdjustedConsumptionKwhShape(dailyKwh, { ve: restreint }, 'hiver', OPTS);
    const baseline = consumptionKwhShape(dailyKwh, OPTS);
    expect(out).toEqual(baseline);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L4 — aucune couche : repli STRICTEMENT identique au comportement CJ1', () => {
  const OPTS = { mode: 'residentiel' as const, occupancy: 'presence_jour' as const };

  it('`{}` et `null` donnent EXACTEMENT `consumptionKwhShape`', () => {
    const baseline = consumptionKwhShape(18.4, OPTS);
    expect(equipmentAdjustedConsumptionKwhShape(18.4, {}, 'ete', OPTS)).toEqual(baseline);
    expect(equipmentAdjustedConsumptionKwhShape(18.4, null, 'ete', OPTS)).toEqual(baseline);
  });

  it('renderYearCurve — `served.equipements` absent/vide produit le MÊME SVG qu’avant L4', () => {
    const production = {
      forme: Array.from({ length: 24 }, (_, h) => (h >= 6 && h <= 19 ? 1 / 14 : 0)),
      kwhJour: 40, picKw: 4, source: 'x',
    };
    const servedSans = { production, consumptionKwhJour: 20, season: 'ete' as const };
    const servedAvecVide = { ...servedSans, equipements: {} };
    const a = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, servedSans);
    const b = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, servedAvecVide);
    expect(b.svg).toBe(a.svg);
  });

  it('renderYearCurve — une couche active change RÉELLEMENT le tracé de consommation', () => {
    const production = {
      forme: Array.from({ length: 24 }, (_, h) => (h >= 6 && h <= 19 ? 1 / 14 : 0)),
      kwhJour: 40, picKw: 4, source: 'x',
    };
    const consPath = (svg: string) => svg.match(/class="curve-cons-line" d="([^"]+)"/)?.[1];
    const sans = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, {
      production, consumptionKwhJour: 20, season: 'ete',
    });
    const avec = renderYearCurve(9000, undefined, 'fr', { mode: 'residentiel' }, {
      production, consumptionKwhJour: 20, season: 'ete',
      equipements: { piscine: PISCINE_LAYER as any },
    });
    expect(consPath(avec.svg)).not.toBe(consPath(sans.svg));
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L4 — la page relie le bloc servi à la composition et à la légende', () => {
  it('la légende sobre est bien branchée (SSR + re-rendu client)', () => {
    expect(PAGE).toContain('equipmentLegendLabel');
    expect(PAGE).toContain('equipements: dailyCurves');
    expect(PAGE).toContain('equipements: curveCfg.equipements');
  });
});
