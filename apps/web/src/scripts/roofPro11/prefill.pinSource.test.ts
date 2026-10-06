/* ============================================================================
   ACAL193 (C-ACAL-003, D-ACAL-13) — PROVENANCE DE L'ÉPINGLE.
   ----------------------------------------------------------------------------
   `pinSource` ('lead' | 'manuel') et `repereAcquitte` (posé par « Garder ce repère »)
   survivent à l'aller-retour ouvrir → enregistrer sans geste, octet-identiques ; un
   déplacement de l'épingle À LA MAIN pose `pinSource: 'manuel'` et cette épingle. Le
   document vient de l'`exemple` du contrat `roof_layout_v2.schema.json` (lu dans le dépôt).
   ========================================================================== */
import { beforeEach, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { deplacerEpingleALaMain, hydrateFromDevis, oublierEpingleDeplacee } from './prefill';
import { appliquerHydratationAuCtx, serialiserDocumentAtelier } from './hydratation';
import { creerCoucheElectrique } from './electrique3d';
import { uniformSetbacks } from '../../lib/roofPro2';
import { emptyCurve } from '../../lib/applianceConsumption';
import { reinitialiserNumerotation } from './numerotation';
import { type Ctx } from './context';
import { racineDepot } from './harnaisAtelier';

const EXEMPLE = (JSON.parse(readFileSync(join(
  racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples', 'roof_layout_v2.schema.json',
), 'utf8')) as { exemple: Record<string, unknown> }).exemple;

/** L'état vivant d'un atelier qui vient de démarrer (défauts de roof-tool-pro11.ts). */
function ctxNeuf(): Record<string, unknown> {
  return {
    areas: [], activeAreaId: '', vertices: [], obstacles: [], roofType: 'flat', pitchDeg: 22,
    facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, layoutPlan: null,
    layoutOptimalCount: 0, shadeObstructions: [], environment: [], exclusionZones: [], measurements: [],
    setbacks: uniformSetbacks(), shadeFactors: null, shadeAnnualFactor: 1, prodPerKwc: null,
    sunDay: 355, sunHour: 12, consCurve: emptyCurve(), consHandEdited: false, consAppliances: [],
    consDailyTarget: 0, consSeasonal: false, consSummerFactor: 1.3, consWinterFactor: 0.9,
    sel: { family: 'south', tilt: 'reco', orient: 'auto', azimuth: 'south', margin: 'keep' },
    pinned: new Set(), useRecommended: true, rec: null,
  };
}

/** Boot (payload de la page) → hydratation : la scène prête, rien n'est encore enregistré. */
function ouvrir(document: Record<string, unknown>): Ctx {
  const h = hydrateFromDevis({ id: null, geometrie: { roof_layout: JSON.parse(JSON.stringify(document)) }, cibleVendue: false });
  const ctx = ctxNeuf();
  const zones = h.zones!;
  const actif = zones.find((z) => z.id === h.activeAreaId) ?? zones[0];
  Object.assign(ctx, {
    areas: zones, activeAreaId: actif.id, vertices: actif.vertices, obstacles: actif.obstacles,
    roofType: actif.roofType, pitchDeg: actif.pitchDeg, facingAzimuthDeg: actif.facingAzimuthDeg,
    facingManual: actif.facingManual ?? false, neededPanels: actif.neededPanels, neededAuto: actif.neededAuto,
  });
  const c = ctx as unknown as Ctx;
  appliquerHydratationAuCtx(c, h);
  return c;
}

/** « Enregistrer » : le sérialiseur câblé du wrapper. */
function enregistrer(c: Ctx): Record<string, unknown> {
  return serialiserDocumentAtelier(c, null, {
    devisOrigin: null,
    solarAccess: null,
    setbacks: c.setbacks!,
    horizonProfile: c.horizonProfile as never,
    modules: null,
    coucheElectrique: creerCoucheElectrique(c),
  }) as unknown as Record<string, unknown>;
}

beforeEach(() => reinitialiserNumerotation());

describe('ACAL193 — pinSource et repereAcquitte', () => {
  it('serializeLayout(deserializeLayout(doc)) conserve pinSource et repereAcquitte', () => {
    expect(EXEMPLE.pinSource).toBe('lead');
    expect(EXEMPLE.repereAcquitte).toBeTruthy();
    const premiere = enregistrer(ouvrir(EXEMPLE));
    expect(premiere.pinSource).toBe(EXEMPLE.pinSource);
    expect(premiere.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    expect(premiere.pin).toEqual(EXEMPLE.pin);
    // Rouvrir le document enregistré, enregistrer sans geste : inchangé.
    const seconde = enregistrer(ouvrir(premiere));
    expect(seconde.pinSource).toBe(EXEMPLE.pinSource);
    expect(seconde.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    expect(JSON.stringify(seconde)).toBe(JSON.stringify(premiere));
  });

  it('un document sans provenance n’en reçoit aucune (rien d’inventé)', () => {
    const sansProvenance = JSON.parse(JSON.stringify(EXEMPLE)) as Record<string, unknown>;
    delete sansProvenance.pinSource;
    delete sansProvenance.repereAcquitte;
    const sortie = enregistrer(ouvrir(sansProvenance));
    expect('pinSource' in sortie).toBe(false);
    expect('repereAcquitte' in sortie).toBe(false);
  });

  it('déplacer l’épingle pose pinSource manuel', () => {
    const c = ouvrir(EXEMPLE);
    deplacerEpingleALaMain(c, [-7.61, 33.58]);
    const sortie = enregistrer(c);
    expect(sortie.pinSource).toBe('manuel');
    expect(sortie.pin).toEqual({ lat: 33.58, lng: -7.61 });
    // L'acquittement du repère n'est pas touché par le geste.
    expect(sortie.repereAcquitte).toEqual(EXEMPLE.repereAcquitte);
    // Rouvrir le document : la provenance manuelle tient sans nouveau geste.
    const relu = enregistrer(ouvrir(sortie));
    expect(relu.pinSource).toBe('manuel');
    expect(relu.pin).toEqual({ lat: 33.58, lng: -7.61 });
  });

  it('un pin posé depuis le lead reste « lead » sans geste ; « Effacer » oublie le déplacement', () => {
    const c = ouvrir(EXEMPLE);
    expect(enregistrer(c).pinSource).toBe('lead');
    deplacerEpingleALaMain(c, [-7.61, 33.58]);
    oublierEpingleDeplacee(c);
    expect(enregistrer(c).pinSource).toBe('lead');
  });

  it('une coordonnée non finie est ignorée', () => {
    const c = ouvrir(EXEMPLE);
    deplacerEpingleALaMain(c, [Number.NaN, 33.58]);
    const sortie = enregistrer(c);
    expect(sortie.pinSource).toBe('lead');
    expect(sortie.pin).toEqual(EXEMPLE.pin);
  });
});
