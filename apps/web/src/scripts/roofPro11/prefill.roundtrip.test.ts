/* ============================================================================
   ACAL26 — ALLER-RETOUR DU DOCUMENT DE L'ATELIER (C-ACAL-045, live ATL-01/04/05/06).
   ----------------------------------------------------------------------------
   Un document rouvert portait cinq couches que l'atelier savait LIRE mais qu'aucun
   boot ne posait dans le ctx : surfaces de pose, environnement, matrice d'ombrage
   enregistrée, consommation affinée, couche électrique. « Enregistrer » sans geste
   les effaçait toutes.

   Ce fichier rejoue le VRAI chemin : `hydrateFromDevis` / `hydrateFromLead` (lecture)
   → `appliquerHydratationAuCtx` (la seule fonction d'application, appelée par les
   deux boots) → `serialiserDocumentAtelier` (le sérialiseur câblé du wrapper
   `onApiReady.serializeLayout`). Les couches viennent de l'`exemple` du contrat
   committé `roof_layout_v2.schema.json` (jamais une copie à la main).
   ========================================================================== */
import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import process from 'node:process';
import { hydrateFromDevis, hydrateFromLead, type SerializedLayout } from './prefill';
import {
  appliquerHydratationAuCtx,
  hydratationDeSection,
  serialiserDocumentAtelier,
  type EtatSerialisationAtelier,
} from './hydratation';
import { creerCoucheElectrique, type DocumentElectrique } from './electrique3d';
import { uniformSetbacks } from '../../lib/roofPro2';
import { emptyCurve } from '../../lib/applianceConsumption';
import { type Ctx } from './context';
import { type AreaRecord } from './types';

function racineDepot(): string {
  let dossier = resolve(process.cwd());
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier;
    dossier = dirname(dossier);
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`);
}

function contrat(nom: string): Record<string, unknown> {
  const chemin = join(racineDepot(), 'backend', 'django_core', 'apps', 'calepinage', 'contract_samples', nom);
  return JSON.parse(readFileSync(chemin, 'utf8'));
}

const EXEMPLE = contrat('roof_layout_v2.schema.json').exemple as Record<string, unknown>;
const EQUIPEMENTS = (contrat('electrique_equipements.json').exemple as { electrical: DocumentElectrique })
  .electrical;

/** Une matrice 12×24 : 0,6 de 8 h à 10 h (le scénario de la tâche), 1 ailleurs. */
function matriceOmbrage(): number[][] {
  return Array.from({ length: 12 }, () =>
    Array.from({ length: 24 }, (_, h) => (h >= 8 && h < 10 ? 0.6 : 1)),
  );
}

/** Le document « riche » semé : les zones/surfaces/environnement/consommation de
 *  l'exemple du contrat, une matrice enregistrée et UN onduleur de l'échantillon
 *  électrique. */
function documentRiche(): SerializedLayout {
  const onduleur = (EQUIPEMENTS.equipements ?? []).find((e) => e.type === 'onduleur');
  if (!onduleur) throw new Error('aucun onduleur dans electrique_equipements.json');
  return JSON.parse(
    JSON.stringify({
      version: 2,
      pin: EXEMPLE.pin,
      outline: EXEMPLE.outline,
      billKwh: null,
      activeAreaId: 'z1',
      zones: [
        {
          id: 'z1',
          label: 'Pan Sud',
          vertices: [
            [-7.6, 33.5],
            [-7.5999, 33.5],
            [-7.5999, 33.5001],
            [-7.6, 33.5001],
          ],
          obstacles: [],
          roofType: 'flat',
          pitchDeg: 10,
          facingAzimuthDeg: 180,
          facingManual: false,
          neededPanels: 12,
          neededAuto: true,
        },
      ],
      poseSurfaces: EXEMPLE.poseSurfaces,
      environment: EXEMPLE.environment,
      shading12x24: matriceOmbrage(),
      // La consommation de l'exemple, avec UN appareil saisi (courbe24, appareils et
      // source.saisi_le : les trois que la tâche nomme).
      consumption: {
        ...(EXEMPLE.consumption as Record<string, unknown>),
        appareils: [{ kind: 'clim', label: 'Climatiseur salon', dailyKwh: 6, startHour: 13, endHour: 18, billing: 'onTop' }],
        methode: 'appareils',
      },
      electrical: { equipements: [onduleur], cheminements: [] },
    }),
  ) as SerializedLayout;
}

/** Un ctx d'atelier minimal, construit comme l'état vivant après le boot : zones du
 *  document, zone active posée, réglages de consommation PAR DÉFAUT de l'atelier. */
function ctxApresBoot(zones: AreaRecord[], activeId: string): Ctx {
  const active = zones.find((z) => z.id === activeId) ?? zones[0];
  return {
    areas: zones,
    activeAreaId: active.id,
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
    shadeObstructions: [],
    environment: [],
    shadeFactors: null,
    shadeAnnualFactor: 1,
    prodPerKwc: null,
    sunDay: Number.NaN,
    sunHour: Number.NaN,
    consCurve: emptyCurve(),
    consHandEdited: false,
    consAppliances: [],
    consDailyTarget: 0,
    consSeasonal: false,
    consSummerFactor: 1.3,
    consWinterFactor: 0.9,
  } as unknown as Ctx;
}

function etatWrapper(ctx: Ctx, devisOrigin: EtatSerialisationAtelier['devisOrigin']): EtatSerialisationAtelier {
  return {
    devisOrigin,
    solarAccess: null,
    setbacks: uniformSetbacks(),
    horizonProfile: null,
    modules: null,
    coucheElectrique: creerCoucheElectrique(ctx),
  };
}

const CLES = ['poseSurfaces', 'environment', 'shading12x24', 'consumption', 'electrical'] as const;

describe('ACAL26 — les deux boots relisent les cinq couches et « Enregistrer » sans geste les réémet', () => {
  it('hydrateFromDevis → appliquerHydratationAuCtx → serializeLayout conserve poseSurfaces, environment, shading12x24, consumption, electrical', () => {
    const doc = documentRiche();
    const h = hydrateFromDevis({ id: 7, geometrie: { roof_layout: doc }, cible: { panneaux: null }, cibleVendue: false });
    const ctx = ctxApresBoot(h.zones!, h.activeAreaId!);
    appliquerHydratationAuCtx(ctx, h);
    const sortie = serialiserDocumentAtelier(ctx, null, etatWrapper(ctx, { devisId: 7, panelWatt: null, scenario: null }));
    for (const cle of CLES) {
      expect((sortie as unknown as Record<string, unknown>)[cle], cle).toStrictEqual(
        (doc as unknown as Record<string, unknown>)[cle],
      );
    }
    // Le champ au sol reste là avec ses modules rendus par le moteur.
    expect(sortie.poseSurfaces?.[0]?.engine?.modules).toBe(96);
    expect(sortie.electrical?.equipements).toHaveLength(1);
  });

  it('le boot LEAD (calepinage sans devis) applique la MÊME fonction : mêmes cinq couches', () => {
    const doc = documentRiche();
    const h = hydrateFromLead({ roof_point: { lat: 33.5, lng: -7.6 }, roof_layout: doc });
    expect(h.surfacesPose).toHaveLength(2);
    expect(h.environment).toHaveLength(1);
    expect(h.shading12x24?.[0][8]).toBe(0.6);
    expect(h.consSource?.saisi_le).toBe('2026-09-18T10:00:00Z');
    expect(h.electrical?.equipements).toHaveLength(1);
    // Le boot lead n'a pas de zones relues : l'atelier part de sa zone vierge.
    const zoneVierge: AreaRecord = {
      id: 'area-1', label: 'Zone 1', vertices: [], obstacles: [], roofType: 'flat', pitchDeg: 22,
      facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, result: null, renderPlan: null,
    };
    const ctx = ctxApresBoot([zoneVierge], 'area-1');
    appliquerHydratationAuCtx(ctx, h);
    const sortie = serialiserDocumentAtelier(ctx, null, etatWrapper(ctx, null));
    for (const cle of CLES) {
      expect((sortie as unknown as Record<string, unknown>)[cle], cle).toStrictEqual(
        (doc as unknown as Record<string, unknown>)[cle],
      );
    }
  });

  it('sans appliquerHydratationAuCtx (le défaut d’avant), les cinq couches disparaissent', () => {
    const doc = documentRiche();
    const h = hydrateFromDevis({ id: 7, geometrie: { roof_layout: doc } });
    const ctx = ctxApresBoot(h.zones!, h.activeAreaId!);
    const sortie = serialiserDocumentAtelier(ctx, null, etatWrapper(ctx, { devisId: 7, panelWatt: null, scenario: null }));
    expect(sortie.poseSurfaces).toBeUndefined();
    expect(sortie.environment).toBeUndefined();
    expect(sortie.shading12x24).toBeNull();
    expect(sortie.consumption).toBeUndefined();
    expect(sortie.electrical).toBeUndefined();
  });

  it('appliquerSection applique UNE clé par la même fonction, sans toucher aux autres', () => {
    const doc = documentRiche();
    const h = hydrateFromDevis({ id: 7, geometrie: { roof_layout: doc } });
    const ctx = ctxApresBoot(h.zones!, h.activeAreaId!);
    appliquerHydratationAuCtx(ctx, h);
    const environnementAvant = ctx.environment;
    appliquerHydratationAuCtx(ctx, hydratationDeSection('poseSurfaces', []));
    expect(ctx.surfacesPose).toEqual([]);
    // L'environnement est le MÊME tableau (référence partagée) et n'a pas bougé.
    expect(ctx.environment).toBe(environnementAvant);
    expect(ctx.environment).toHaveLength(1);
    expect(ctx.electrical?.equipements).toHaveLength(1);
  });
});
