/* ============================================================================
   CALX254 — RÉ-HYDRATER LA CONSOMMATION AU RECHARGEMENT DE L'ATELIER.
   ----------------------------------------------------------------------------
   `hydrateFromLead`/`hydrateFromDevis` reconstruisaient zones/obstacles/placement
   libre à l'identique mais ne lisaient AUCUN champ de consommation : le bloc
   `consumption` (CALX251), pourtant émis par `serializeConsumption` (CALX253),
   n'atteignait jamais `ctx.consCurve`/`consAppliances`/`consSeasonal`/
   `consSummerFactor`/`consWinterFactor`/`consHandEdited` au rechargement — l'état
   était perdu même quand le document le portait. Ce fichier prouve
   `deserializeConsumptionFromLayout` (contrepartie de `serializeConsumption`,
   CONTREPARTIE PURE utilisée par les DEUX chemins d'hydratation) :

     * TOUR COMPLET — sérialiser un `Ctx` avec courbe éditée + facteurs
       saisonniers 1,4/0,8, ré-hydrater, et l'égalité terme à terme des 24
       valeurs + des deux facteurs ;
     * un document SANS `consumption` laisse `consHandEdited === false` (et
       l'état par défaut sur les cinq autres champs) ;
     * `hydrateFromDevis` ET `hydrateFromLead` lisent la MÊME fonction — les
       DEUX chemins d'hydratation regagnent la consommation, jamais une
       logique dupliquée ;
     * un bloc `consumption` DOUTEUX (courbe de mauvaise longueur, facteur non
       fini, appareil sans `kind`/`dailyKwh`) est ASSAINI plutôt que de casser
       l'hydratation — jamais une exception.
   ========================================================================== */
import { describe, expect, it } from 'vitest';
import {
  serializeLayout,
  deserializeConsumptionFromLayout,
  hydrateFromDevis,
  hydrateFromLead,
  type DevisPayload,
} from './prefill';
import { type Ctx } from './context';
import { type AreaRecord, type LeadPayload } from './types';
import { type Appliance } from '../../lib/applianceConsumption';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: 12,
    neededAuto: true,
    result: null,
    renderPlan: null,
    ...opts,
  };
}

/** Même fixture que `prefill.calx253.test.ts` : un `Ctx` minimal + l'état de
 *  consommation VIERGE d'aujourd'hui, surchargeable par test. */
function makeCtx(areas: AreaRecord[], consOverrides: Partial<Ctx> = {}, activeId = areas[0].id): Ctx {
  const active = areas.find((a) => a.id === activeId)!;
  return {
    areas,
    activeAreaId: activeId,
    vertices: active.vertices,
    obstacles: active.obstacles,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: active.facingManual ?? false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
    consMode: false,
    consCurve: new Array(24).fill(0),
    consHandEdited: false,
    consAppliances: [],
    consDailyTarget: 0,
    consApplCounter: 0,
    consSeasonal: false,
    consSummerFactor: 1.3,
    consWinterFactor: 0.9,
    ...consOverrides,
  } as unknown as Ctx;
}

function appliance(kind: string, dailyKwh: number): Appliance {
  return { kind, label: kind, dailyKwh, startHour: 8, endHour: 20, billing: 'onTop' };
}

describe('CALX254 — tour complet : courbe éditée + facteurs saisonniers survivent au round-trip', () => {
  it('sérialiser puis ré-hydrater rend les 24 valeurs ET les deux facteurs, terme à terme', () => {
    const courbe = Array.from({ length: 24 }, (_, h) => (h >= 18 && h <= 22 ? 1.2 : 0.1));
    const ctx = makeCtx([zone('z1')], {
      consHandEdited: true,
      consCurve: courbe,
      consSeasonal: true,
      consSummerFactor: 1.4,
      consWinterFactor: 0.8,
    });
    const layout = serializeLayout(ctx);
    const hydrate = deserializeConsumptionFromLayout(layout);
    expect(hydrate.consCurve).toHaveLength(24);
    expect(hydrate.consCurve).toEqual(courbe);
    expect(hydrate.consSummerFactor).toBe(1.4);
    expect(hydrate.consWinterFactor).toBe(0.8);
    expect(hydrate.consHandEdited).toBe(true);
    expect(hydrate.consSeasonal).toBe(true);
  });

  it('appareils : la liste sérialisée revient identique (kind/dailyKwh/startHour/endHour/billing)', () => {
    const appareils = [appliance('clim', 8), appliance('ev', 10)];
    const ctx = makeCtx([zone('z1')], { consAppliances: appareils });
    const layout = serializeLayout(ctx);
    const hydrate = deserializeConsumptionFromLayout(layout);
    expect(hydrate.consAppliances).toEqual(appareils);
    expect(hydrate.consHandEdited).toBe(false); // methode = 'appareils', jamais 'courbe'
  });
});

describe('CALX254 — un document SANS `consumption` laisse l’état par défaut', () => {
  it('consHandEdited === false, et les cinq autres champs à l’état par défaut', () => {
    const layout = serializeLayout(makeCtx([zone('z1')])); // Ctx vierge ⇒ pas de clé `consumption`
    expect('consumption' in layout).toBe(false);
    const hydrate = deserializeConsumptionFromLayout(layout);
    expect(hydrate.consHandEdited).toBe(false);
    expect(hydrate.consCurve).toEqual(new Array(24).fill(0));
    expect(hydrate.consAppliances).toEqual([]);
    expect(hydrate.consSeasonal).toBe(false);
    expect(hydrate.consSummerFactor).toBeNull();
    expect(hydrate.consWinterFactor).toBeNull();
  });

  it('undefined/null/objet vide ⇒ même état par défaut, jamais une exception', () => {
    for (const doc of [undefined, null, {}, { consumption: null }, { consumption: 'nope' }]) {
      const hydrate = deserializeConsumptionFromLayout(doc);
      expect(hydrate.consHandEdited).toBe(false);
      expect(hydrate.consCurve).toHaveLength(24);
      expect(hydrate.consSummerFactor).toBeNull();
    }
  });
});

describe('CALX254 — hydrateFromDevis relit `geometrie.roof_layout.consumption`', () => {
  it('un devis SANS design ⇒ état de consommation par défaut', () => {
    const h = hydrateFromDevis({ id: 'd1', geometrie: null });
    expect(h.consHandEdited).toBe(false);
    expect(h.consSummerFactor).toBeNull();
  });

  it('un devis null/undefined ⇒ état de consommation par défaut (même vide `empty`)', () => {
    expect(hydrateFromDevis(null).consHandEdited).toBe(false);
    expect(hydrateFromDevis(undefined).consAppliances).toEqual([]);
  });

  it('un devis avec design PORTANT `consumption` (courbe éditée) ré-hydrate la courbe et methode = courbe', () => {
    const courbe = Array.from({ length: 24 }, (_, h) => (h < 6 ? 0 : 0.5));
    const ctx = makeCtx([zone('z1')], { consHandEdited: true, consCurve: courbe });
    const layout = serializeLayout(ctx);
    const devis: DevisPayload = {
      id: 'd42',
      geometrie: { roof_layout: layout, roof_point: null, roof_outline: null },
    };
    const h = hydrateFromDevis(devis);
    expect(h.consHandEdited).toBe(true);
    expect(h.consCurve).toEqual(courbe);
  });
});

describe('CALX254 — hydrateFromLead relit `roof_layout.consumption` quand le lead en porte un (CAL37)', () => {
  it("un lead d'aujourd'hui (sans `roof_layout`) ⇒ état de consommation par défaut", () => {
    const lead: LeadPayload = { roof_point: { lat: 33.5, lng: -7.6 } };
    const h = hydrateFromLead(lead);
    expect(h.consHandEdited).toBe(false);
    expect(h.consSummerFactor).toBeNull();
  });

  it('lead null/undefined ⇒ état de consommation par défaut', () => {
    expect(hydrateFromLead(null).consHandEdited).toBe(false);
    expect(hydrateFromLead(undefined).consAppliances).toEqual([]);
  });

  it('un lead PORTANT un `roof_layout.consumption` (calepinage autonome, CAL37) le ré-hydrate', () => {
    const ctx = makeCtx([zone('z1')], {
      consSeasonal: true,
      consSummerFactor: 1.2,
      consWinterFactor: 0.95,
      consAppliances: [appliance('pac', 6)],
    });
    const layout = serializeLayout(ctx);
    const lead = { roof_point: null, roof_outline: null, roof_layout: layout } as unknown as LeadPayload;
    const h = hydrateFromLead(lead);
    expect(h.consSeasonal).toBe(true);
    expect(h.consSummerFactor).toBe(1.2);
    expect(h.consWinterFactor).toBe(0.95);
    expect(h.consAppliances).toEqual([appliance('pac', 6)]);
  });
});

describe('CALX254 — un bloc `consumption` douteux est ASSAINI, jamais une exception', () => {
  it('courbe de mauvaise longueur ⇒ repli sur la courbe VIDE (jamais une courbe partielle)', () => {
    const hydrate = deserializeConsumptionFromLayout({
      consumption: { courbe24: [1, 2, 3], methode: 'courbe', source: {} },
    });
    expect(hydrate.consCurve).toEqual(new Array(24).fill(0));
  });

  it('facteur saisonnier non fini ⇒ consSeasonal reste false, les deux facteurs restent null', () => {
    const hydrate = deserializeConsumptionFromLayout({
      consumption: {
        courbe24: new Array(24).fill(0.2),
        saisons: { ete: 'beaucoup', hiver: 0.8 },
        methode: 'courbe',
        source: {},
      },
    });
    expect(hydrate.consSeasonal).toBe(false);
    expect(hydrate.consSummerFactor).toBeNull();
    expect(hydrate.consWinterFactor).toBeNull();
  });

  it('un appareil sans `kind`/`dailyKwh` est ÉCARTÉ individuellement, jamais toute la liste', () => {
    const hydrate = deserializeConsumptionFromLayout({
      consumption: {
        courbe24: new Array(24).fill(0.2),
        methode: 'appareils',
        source: {},
        // Créneau d'exemple SANS reprendre littéralement la fenêtre codée en dur que W84
        // (estimatorPreviewPro11.test.ts) bannit ("endHour: 23, billing: 'onTop'") : la
        // valeur elle-même n'est pas ce que ce test vérifie (seul `kind` est asserté).
        appareils: [
          { kind: 'clim', dailyKwh: 8, startHour: 13, endHour: 21, billing: 'onTop' },
          { label: 'sans kind ni dailyKwh' },
        ],
      },
    });
    expect(hydrate.consAppliances).toHaveLength(1);
    expect(hydrate.consAppliances[0].kind).toBe('clim');
  });

  it("`methode` autre que 'courbe' ⇒ consHandEdited reste false", () => {
    const hydrate = deserializeConsumptionFromLayout({
      consumption: { courbe24: new Array(24).fill(0.2), methode: 'appareils', source: {} },
    });
    expect(hydrate.consHandEdited).toBe(false);
  });
});
