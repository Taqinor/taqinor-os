/**
 * Harnais PARTAGÉ des tests de l'atelier (ACAL345) — fixtures de pan / de contexte et lecture
 * du dépôt, extraites de `roofPro11/*.test.ts` où elles étaient recopiées à l'identique.
 *
 * Ce fichier n'est PAS un test (pas de `.test.`) : vitest ne le collecte pas, les tests
 * l'importent. Aucune logique de production ne doit l'importer.
 */
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import process from 'node:process';
import { vi } from 'vitest';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { type Appliance } from '../../lib/applianceConsumption';

/** Racine du dépôt, cherchée en remontant depuis le dossier de travail de vitest. */
export function racineDepot(): string {
  let dossier = resolve(process.cwd());
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier;
    dossier = dirname(dossier);
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`);
}

/** Le contour carré de référence (Casablanca) des tests de pan. */
export const VERTS_REFERENCE: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

/** Un pan de test : toit en pente 22° plein sud, 12 panneaux, contour de référence ;
 *  `opts` surcharge n'importe quel champ (dont `vertices`). */
export function panDeTest(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS_REFERENCE.map(([lng, lat]) => [lng, lat] as [number, number]),
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

/** Les champs de `Ctx` que tout test d'atelier lit depuis la zone active ; les tests
 *  y ajoutent ce qui leur est propre (`{ ...ctxDeBase(zones), dom: {} }`). */
export function ctxDeBase(areas: AreaRecord[], activeId: string = areas[0].id): Record<string, unknown> {
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
  };
}

/** `ctxDeBase` typé `Ctx`, pour les tests qui n'ajoutent rien. */
export function ctxMinimal(areas: AreaRecord[], activeId: string = areas[0].id): Ctx {
  return ctxDeBase(areas, activeId) as unknown as Ctx;
}

/** L'état de consommation VIERGE de l'atelier (panneau « Affiner » jamais ouvert). */
export function consommationVierge(): Record<string, unknown> {
  return {
    consMode: false,
    consCurve: new Array(24).fill(0),
    consHandEdited: false,
    consAppliances: [],
    consDailyTarget: 0,
    consApplCounter: 0,
    consSeasonal: false,
    consSummerFactor: 1.3,
    consWinterFactor: 0.9,
  };
}

/** Les méthodes de carte MapLibre inertes que les faux de carte des tests partagent. */
export function methodesCarteInertes() {
  return {
    getLayer: () => undefined,
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
    setLayoutProperty: vi.fn(),
    setPaintProperty: vi.fn(),
    on: vi.fn(),
  };
}

/** Un `Ctx` minimal + l'état de consommation VIERGE ; `consOverrides` surcharge les `cons*`. */
export function ctxAvecConsommation(
  areas: AreaRecord[],
  consOverrides: Partial<Ctx> = {},
  activeId: string = areas[0].id,
): Ctx {
  return { ...ctxDeBase(areas, activeId), ...consommationVierge(), ...consOverrides } as unknown as Ctx;
}

export function appareilDeTest(kind: string, dailyKwh: number): Appliance {
  return { kind, label: kind, dailyKwh, startHour: 8, endHour: 20, billing: 'onTop' };
}
