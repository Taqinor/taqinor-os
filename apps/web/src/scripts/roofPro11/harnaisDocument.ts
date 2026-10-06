/* ============================================================================
   ACAL345 — HARNAIS PARTAGÉ « OUVRIR → ENREGISTRER » DE L'ATELIER (tests seulement).
   ----------------------------------------------------------------------------
   `allerRetourDocument.test.ts` (ACAL31) et `prefill.pinSource.test.ts` (ACAL193)
   recopiaient le même atelier neuf, la même hydratation par la SEULE fonction
   d'application (`appliquerHydratationAuCtx`) et le même appel du sérialiseur câblé
   du wrapper. Une seule copie ici : un écart entre les deux ne pourrait que masquer
   une perte de clé d'un côté.
   ========================================================================== */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { hydrateFromDevis } from './prefill';
import { appliquerHydratationAuCtx, serialiserDocumentAtelier } from './hydratation';
import { creerCoucheElectrique } from './electrique3d';
import { uniformSetbacks } from '../../lib/roofPro2';
import { emptyCurve } from '../../lib/applianceConsumption';
import { type Ctx } from './context';
import { racineDepot } from './harnaisAtelier';

type Hydratation = ReturnType<typeof hydrateFromDevis>;

/** L'`exemple` COMPLET du contrat `roof_layout_v2.schema.json`, lu dans le dépôt. */
export function exempleRoofLayoutV2(): Record<string, unknown> {
  return (JSON.parse(readFileSync(join(
    racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples', 'roof_layout_v2.schema.json',
  ), 'utf8')) as { exemple: Record<string, unknown> }).exemple;
}

/** L'état vivant d'un atelier qui vient de démarrer (défauts de roof-tool-pro11.ts). */
export function ctxAtelierNeuf(): Record<string, unknown> {
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

/** Boot (le payload de la page) → hydratation : la scène prête, rien n'est encore enregistré. */
export function ouvrirAtelier(payload: Parameters<typeof hydrateFromDevis>[0]): { c: Ctx; h: Hydratation } {
  const h = hydrateFromDevis(payload);
  const ctx = ctxAtelierNeuf();
  const zones = h.zones!;
  const actif = zones.find((z) => z.id === h.activeAreaId) ?? zones[0];
  Object.assign(ctx, {
    areas: zones, activeAreaId: actif.id, vertices: actif.vertices, obstacles: actif.obstacles,
    roofType: actif.roofType, pitchDeg: actif.pitchDeg, facingAzimuthDeg: actif.facingAzimuthDeg,
    facingManual: actif.facingManual ?? false, neededPanels: actif.neededPanels, neededAuto: actif.neededAuto,
  });
  const c = ctx as unknown as Ctx;
  appliquerHydratationAuCtx(c, h);
  return { c, h };
}

/** « Enregistrer » : le sérialiseur câblé du wrapper (origine devis fournie par l'appelant). */
export function enregistrerAtelier(
  c: Ctx,
  devisOrigin: Parameters<typeof serialiserDocumentAtelier>[2]['devisOrigin'] = null,
) {
  return serialiserDocumentAtelier(c, null, {
    devisOrigin,
    solarAccess: null,
    setbacks: c.setbacks!,
    horizonProfile: c.horizonProfile as never,
    modules: null,
    coucheElectrique: creerCoucheElectrique(c),
  });
}
