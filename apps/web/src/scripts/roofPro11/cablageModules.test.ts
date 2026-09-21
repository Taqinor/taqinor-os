// @vitest-environment jsdom
// CALX109/CALX110 CÂBLAGE — LE CHOIX DE MODULE ATTEINT ENFIN L'ATELIER, LE DOCUMENT ET LE PAVAGE.
//
// LE CONSTAT (lane HOOKS2). `moduleSelect.ts` savait tout faire — lire le catalogue de la
// société, résoudre le module d'un pan, calculer son kWc, écrire le tout dans le document —
// et RIEN ne l'appelait : `computePanStats` n'était invoqué qu'avec deux arguments,
// `SerializeMeta.modules` n'était jamais fourni, aucun sélecteur DOM n'existait et aucun
// moteur n'acceptait les cotes d'un module. Ce fichier ne prouve que ces lignes-là.
//
// LA GARANTIE QUI REVIENT PARTOUT : tant que personne n'a choisi, RIEN ne bouge — le
// document repart octet pour octet identique, et le module par défaut de l'atelier est NOMMÉ.
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createZones } from './zones';
import { serializeLayout, deserializeLayout } from './prefill';
import {
  MODULE_PAR_DEFAUT_ATELIER,
  affectationDesPans,
  type ModulesDisponibles,
} from './moduleSelect';
import { type Ctx } from './context';
import { type AreaRecord } from './types';
import { MODULE_ATELIER_PAR_DEFAUT, cotesDePavage, type Panel2Module } from '../../lib/roofPro2';
import { packConfig } from '../../lib/estimatorBrainV2';
import { solveLive } from '../../lib/estimatorBrainV7';
import { solveLivePitched } from '../../lib/estimatorBrainV8';

const VERTS: [number, number][] = [
  [-7.6, 33.59],
  [-7.599, 33.59],
  [-7.599, 33.591],
  [-7.6, 33.591],
];

/** Un module de catalogue COMPLET (toutes les cotes de pavage renseignées). */
function moduleComplet(id: string, longueurMm: number, largeurMm: number, pmaxWc: number) {
  return {
    id,
    produitId: 7,
    libelle: `Module ${id} (${longueurMm} × ${largeurMm} mm)`,
    longueurMm,
    largeurMm,
    epaisseurMm: 35,
    poidsKg: 28,
    pmaxWc,
    source: 'fiche produit du stock',
  };
}

/** La réponse du serveur, telle que `GET calepinages/<pk>/modules-disponibles/` la sert. */
function reponseCatalogue(): ModulesDisponibles {
  return {
    calepinage: 12,
    modules: [
      { module: moduleComplet('produit-1', 2000, 1000, 500), selectionnable: true, champs_manquants: [], motif: null },
      { module: moduleComplet('produit-2', 2384, 1303, 720), selectionnable: true, champs_manquants: [], motif: null },
      {
        module: { ...moduleComplet('produit-3', 2100, 1050, 600), longueurMm: null, pmaxWc: null },
        selectionnable: false,
        champs_manquants: ['longueur_mm', 'pmax_wc'],
        motif: 'fiche produit incomplète : longueur et puissance crête manquantes',
      },
    ],
    champs_requis: ['longueur_mm', 'largeur_mm', 'pmax_wc'],
    motif_liste_vide: null,
  };
}

function zone(id: string, opts: Partial<AreaRecord> = {}): AreaRecord {
  return {
    id,
    label: `Zone ${id}`,
    vertices: VERTS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'flat',
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

/** Un plan de rendu MINIMAL : ce qu'il faut pour que `serializeLayout` émette `geometry`. */
function planDeRendu(nb: number, kwc: number) {
  return {
    pack: { origin: [-7.6, 33.59] as [number, number], azimuthDeg: 180 },
    grid: {
      panels: Array.from({ length: nb }, (_, i) => ({ cx: i, cy: 0 })),
      kwc,
    },
    tiltDeg: 13,
    family: 'south',
    flush: false,
    count: nb,
  } as unknown as AreaRecord['renderPlan'];
}

function makeCtx(areas: AreaRecord[], modulesDisponibles?: unknown, activeId = areas[0].id): Ctx {
  const active = areas.find((a) => a.id === activeId)!;
  return {
    opts: { modulesDisponibles },
    areas,
    activeAreaId: activeId,
    activeArea: () => areas.find((a) => a.id === activeId),
    vertices: active.vertices,
    obstacles: active.obstacles,
    closed: true,
    roofType: active.roofType,
    pitchDeg: active.pitchDeg,
    facingAzimuthDeg: active.facingAzimuthDeg,
    facingManual: active.facingManual ?? false,
    neededPanels: active.neededPanels,
    neededAuto: active.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
    dom: {},
  } as unknown as Ctx;
}

/** Le panneau « Zones » de l'hôte : le sélecteur se greffe dedans, comme les autres. */
function monterPanneauZones(): HTMLElement {
  document.body.innerHTML = '<div id="rp9-areas"></div>';
  return document.getElementById('rp9-areas')!;
}

function ctxAvecDom(areas: AreaRecord[], modulesDisponibles?: unknown): Ctx {
  const ctx = makeCtx(areas, modulesDisponibles);
  (ctx as unknown as { dom: Record<string, unknown> }).dom = {
    areasWindowEl: monterPanneauZones(),
    areasListEl: null,
    addAreaBtn: null,
    areasTotalPanelsEl: null,
    areasTotalKwcEl: null,
    areasTotalProdEl: null,
    areasTotalSavingsEl: null,
  };
  return ctx;
}

afterEach(() => {
  document.body.innerHTML = '';
  vi.clearAllMocks();
});

/** Le SOURCE de l'entrée du constructeur — la ligne d'appel câblée ici y vit (page à effets
 *  de bord, non importable en test). Aucune assertion ne porte sur plusieurs lignes à la fois
 *  (CRLF local). */
const SOURCE_ENTREE = readFileSync(
  resolve(process.cwd(), 'src/scripts/roof-tool-pro11.ts'),
  'utf8',
);
const SOURCE_ZONES = readFileSync(
  resolve(process.cwd(), 'src/scripts/roofPro11/zones.ts'),
  'utf8',
);

describe('CALX110 câblage — `SerializeMeta.modules` est enfin fourni par l’entrée', () => {
  it('aucun module choisi ⇒ le document est IDENTIQUE, octet pour octet', () => {
    const areas = [zone('area-1', { renderPlan: planDeRendu(10, 7.2) })];
    const ctx = makeCtx(areas, reponseCatalogue());
    const catalogue = [moduleComplet('produit-1', 2000, 1000, 500)];

    const sans = JSON.stringify(serializeLayout(ctx, 12000));
    const avec = JSON.stringify(
      serializeLayout(ctx, 12000, { modules: affectationDesPans(catalogue, ctx.areas) }),
    );

    expect(avec).toBe(sans);
    expect(JSON.parse(avec).modules).toBeUndefined();
    expect(JSON.parse(avec).zones[0].geometry.moduleId).toBeUndefined();
  });

  it('un pan qui a choisi ⇒ `modules[]`, `geometry.moduleId`, kWc et `panelWatt` suivent SON module', () => {
    const areas = [zone('area-1', { renderPlan: planDeRendu(10, 7.2), moduleId: 'produit-1' })];
    const ctx = makeCtx(areas, reponseCatalogue());
    const catalogue = [moduleComplet('produit-1', 2000, 1000, 500)];

    const doc = serializeLayout(ctx, 12000, { modules: affectationDesPans(catalogue, ctx.areas) });

    expect(doc.modules?.map((m) => m.id)).toEqual(['produit-1']);
    expect(doc.zones[0].geometry?.moduleId).toBe('produit-1');
    // 10 modules × 500 Wc = 5 kWc — jamais les 7,2 kWc du module par défaut.
    expect(doc.zones[0].geometry?.kwc).toBeCloseTo(5, 6);
    expect(doc.result?.kwc).toBeCloseTo(5, 6);
    expect(doc.panelWatt).toBe(500);
  });

  it('deux pans, deux modèles ⇒ le kWc total est la SOMME des deux, pas un forfait', () => {
    const areas = [
      zone('area-1', { renderPlan: planDeRendu(10, 7.2), moduleId: 'produit-1' }),
      zone('area-2', { renderPlan: planDeRendu(4, 2.88), moduleId: 'produit-2' }),
    ];
    const ctx = makeCtx(areas, reponseCatalogue());
    const catalogue = [
      moduleComplet('produit-1', 2000, 1000, 500),
      moduleComplet('produit-2', 2384, 1303, 720),
    ];

    const doc = serializeLayout(ctx, 12000, { modules: affectationDesPans(catalogue, ctx.areas) });

    expect(doc.modules?.map((m) => m.id)).toEqual(['produit-1', 'produit-2']);
    expect(doc.result?.kwc).toBeCloseTo(10 * 0.5 + 4 * 0.72, 6);
    // Majoritaire EN MODULES POSÉS (10 contre 4) : c'est son watt qui reste à la racine.
    expect(doc.panelWatt).toBe(500);
  });

  it('un `moduleId` que le catalogue ne porte pas n’écrit RIEN sur ce pan', () => {
    const areas = [zone('area-1', { renderPlan: planDeRendu(10, 7.2), moduleId: 'produit-inconnu' })];
    const ctx = makeCtx(areas, reponseCatalogue());
    const catalogue = [moduleComplet('produit-1', 2000, 1000, 500)];

    const doc = serializeLayout(ctx, 12000, { modules: affectationDesPans(catalogue, ctx.areas) });

    expect(doc.modules).toBeUndefined();
    expect(doc.zones[0].geometry?.moduleId).toBeUndefined();
    expect(doc.zones[0].geometry?.kwc).toBeCloseTo(7.2, 6);
  });

  it('l’entrée du constructeur passe bien l’affectation à `serializeLayout`', () => {
    expect(SOURCE_ENTREE).toContain('modules: affectationDesPans(catalogueModulesAtelier, ctx.areas),');
    expect(SOURCE_ENTREE).toContain('lireModulesDisponibles(opts.modulesDisponibles).choisissables');
  });
});

describe('CALX110 câblage — le choix RESSÈME au rechargement', () => {
  it('`deserializeLayout` rend au pan le `moduleId` que le document porte', () => {
    const areas = [zone('area-1', { renderPlan: planDeRendu(10, 7.2), moduleId: 'produit-1' })];
    const ctx = makeCtx(areas, reponseCatalogue());
    const catalogue = [moduleComplet('produit-1', 2000, 1000, 500)];
    const doc = serializeLayout(ctx, 12000, { modules: affectationDesPans(catalogue, ctx.areas) });

    const relus = deserializeLayout(doc);

    expect(relus[0].moduleId).toBe('produit-1');
  });

  it('un document sans module ne fabrique AUCUN `moduleId` à la lecture', () => {
    const areas = [zone('area-1', { renderPlan: planDeRendu(10, 7.2) })];
    const doc = serializeLayout(makeCtx(areas), 12000);

    const relus = deserializeLayout(doc);

    expect(relus[0].moduleId).toBeUndefined();
    expect('moduleId' in relus[0]).toBe(false);
  });
});

describe('CALX109 câblage — le sélecteur de module du pan, créé par le constructeur', () => {
  it('liste le module par défaut NOMMÉ, les choisissables, et GRISE les fiches incomplètes', () => {
    const ctx = ctxAvecDom([zone('area-1')], reponseCatalogue());
    createZones(ctx);

    const select = document.getElementById('rp9-pan-module-select') as HTMLSelectElement;
    expect(select).not.toBeNull();
    const options = [...select.options];
    expect(options[0].value).toBe('');
    expect(options[0].textContent).toBe(MODULE_PAR_DEFAUT_ATELIER.libelle);
    expect(options.map((o) => o.value)).toEqual(['', 'produit-1', 'produit-2', 'produit-3']);
    const grise = options.find((o) => o.value === 'produit-3')!;
    expect(grise.disabled).toBe(true);
    expect(grise.textContent).toContain('fiche produit incomplète');
  });

  it('choisir un module l’écrit sur le pan ACTIF et RE-PAVE (le motif du repavage est dit)', () => {
    const areas = [zone('area-1')];
    const ctx = ctxAvecDom(areas, reponseCatalogue());
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { recalc, setStatus });

    expect(zones.choisirModuleDuPanActif('produit-1')).toBe(true);

    expect(areas[0].moduleId).toBe('produit-1');
    expect(recalc).toHaveBeenCalledTimes(1);
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining('produit-1'));
    expect(document.getElementById('rp9-pan-module-erreur')!.hidden).toBe(true);
  });

  it('un modèle GRISÉ est refusé en NOMMANT son motif, et rien n’est écrit ni repavé', () => {
    const areas = [zone('area-1')];
    const ctx = ctxAvecDom(areas, reponseCatalogue());
    const recalc = vi.fn();
    const setStatus = vi.fn();
    const zones = createZones(ctx, { recalc, setStatus });

    expect(zones.choisirModuleDuPanActif('produit-3')).toBe(false);

    expect(areas[0].moduleId).toBeUndefined();
    expect(recalc).not.toHaveBeenCalled();
    const erreur = document.getElementById('rp9-pan-module-erreur')!;
    expect(erreur.hidden).toBe(false);
    expect(erreur.textContent).toContain('fiche produit incomplète');
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining('fiche produit incomplète'));
  });

  it('un modèle INCONNU du catalogue est refusé en nommant `moduleId`', () => {
    const areas = [zone('area-1')];
    const ctx = ctxAvecDom(areas, reponseCatalogue());
    const setStatus = vi.fn();
    const zones = createZones(ctx, { setStatus });

    expect(zones.choisirModuleDuPanActif('produit-jamais-vu')).toBe(false);

    expect(areas[0].moduleId).toBeUndefined();
    expect(document.getElementById('rp9-pan-module-erreur')!.textContent)
      .toContain('ne figure pas dans le catalogue');
  });

  it('revenir au choix vide repose le module par défaut, NOMMÉ', () => {
    const areas = [zone('area-1', { moduleId: 'produit-1' })];
    const ctx = ctxAvecDom(areas, reponseCatalogue());
    const setStatus = vi.fn();
    const zones = createZones(ctx, { setStatus });

    expect(zones.choisirModuleDuPanActif('')).toBe(true);

    expect(areas[0].moduleId).toBeUndefined();
    expect(setStatus).toHaveBeenCalledWith(expect.stringContaining(MODULE_PAR_DEFAUT_ATELIER.libelle));
  });

  it('AUCUN catalogue (droits, réseau, société sans fiche) ⇒ le défaut est NOMMÉ, jamais muet', () => {
    const ctx = ctxAvecDom([zone('area-1')], null);
    createZones(ctx);

    const select = document.getElementById('rp9-pan-module-select') as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(['']);
    expect(document.getElementById('rp9-pan-module-mention')!.textContent)
      .toContain(MODULE_PAR_DEFAUT_ATELIER.libelle);
  });

  it('le catalogue VIDE affiche le motif du SERVEUR, jamais un motif inventé', () => {
    const ctx = ctxAvecDom([zone('area-1')], {
      calepinage: 12,
      modules: [],
      champs_requis: [],
      motif_liste_vide: 'aucune fiche « module » dans le stock de la société',
    });
    createZones(ctx);

    expect(document.getElementById('rp9-pan-module-mention')!.textContent)
      .toContain('aucune fiche « module » dans le stock de la société');
  });

  it('`zones.ts` passe bien le 3ᵉ argument `moduleFor` à `computePanStats`', () => {
    expect(SOURCE_ZONES).toContain('a.result), moduleDuPan);');
  });
});

// ═══════════ CALX109 câblage — LES VRAIES COTES ENTRENT DANS LE PAVAGE ═══════════
// Jusqu'ici `Panel2Module` n'était consommé que par `roofPro2.layoutProRows2`, qui n'a AUCUN
// appelant de production : choisir un module ne changeait donc RIEN au nombre de modules
// posés. Les deux moteurs vivants (V7 toit plat, V8 toit en pente) acceptent maintenant
// l'option — et la garantie tenue est la même partout : option absente ⇒ octet pour octet.

/** Un carré de `cote` mètres autour de (LNG0, LAT0) — assez grand pour loger des rangées. */
const LAT0 = 33.59;
const LNG0 = -7.6;
const DEG2M = 111320;
function carreM(cote: number): [number, number][] {
  const d = cote / 2;
  const cosLat = Math.cos((LAT0 * Math.PI) / 180);
  const dLng = d / (DEG2M * cosLat);
  const dLat = d / DEG2M;
  return [
    [LNG0 - dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 + dLat],
    [LNG0 - dLng, LAT0 + dLat],
  ];
}

/** Un module NETTEMENT plus grand que celui de l'atelier : 3,00 × 2,00 m, 1 000 Wc. */
const GROS_MODULE: Panel2Module = { longM: 3, courtM: 2, epaisM: 0.04, watt: 1000 };

describe('CALX109 câblage — `cotesDePavage` : le défaut est un repli, jamais une invention', () => {
  it('option absente ⇒ EXACTEMENT le module par défaut de l’atelier', () => {
    expect(cotesDePavage()).toEqual(MODULE_ATELIER_PAR_DEFAUT);
    expect(cotesDePavage(null)).toEqual(MODULE_ATELIER_PAR_DEFAUT);
  });

  it('une cote non exploitable fait retomber sur le défaut — jamais une dimension supposée', () => {
    expect(cotesDePavage({ longM: 0, courtM: 1, epaisM: null, watt: 500 })).toEqual(MODULE_ATELIER_PAR_DEFAUT);
    expect(cotesDePavage({ longM: 2, courtM: 1, epaisM: null, watt: Number.NaN })).toEqual(MODULE_ATELIER_PAR_DEFAUT);
  });

  it('le GRAND côté est toujours `longM`, quel que soit l’ordre de la fiche produit', () => {
    expect(cotesDePavage({ longM: 1, courtM: 3, epaisM: null, watt: 400 }))
      .toEqual({ longM: 3, courtM: 1, epaisM: null, watt: 400 });
  });
});

describe('CALX109 câblage — toit PLAT (`solveLive` → `packConfig`)', () => {
  const RING = carreM(30);

  it('option absente ⇒ résultat IDENTIQUE, octet pour octet', () => {
    const sans = solveLive(RING, LAT0, 3000, [], {});
    const defaut = solveLive(RING, LAT0, 3000, [], {}, { module: MODULE_ATELIER_PAR_DEFAUT });

    expect(JSON.stringify(defaut)).toBe(JSON.stringify(sans));
  });

  it('un module plus GRAND pose moins de modules, et le kWc vient de SA puissance', () => {
    const sans = solveLive(RING, LAT0, 3000, [], {});
    const gros = solveLive(RING, LAT0, 3000, [], {}, { module: GROS_MODULE });

    expect(gros.winner.fitCount).toBeLessThan(sans.winner.fitCount);
    // 1 000 Wc par module : le kWc est exactement le nombre posé ÷ 1.
    expect(gros.winner.kwc).toBeCloseTo(gros.winner.placedCount * 1, 6);
    expect(gros.winner.kwc).not.toBeCloseTo(gros.winner.placedCount * 0.72, 6);
  });

  it('`packConfig` lui-même : sans option, pavage identique octet pour octet', () => {
    const sans = packConfig(RING, LAT0, { family: 'south', tiltDeg: 13 });
    const defaut = packConfig(RING, LAT0, { family: 'south', tiltDeg: 13, module: MODULE_ATELIER_PAR_DEFAUT });

    expect(JSON.stringify(defaut)).toBe(JSON.stringify(sans));
    expect(packConfig(RING, LAT0, { family: 'south', tiltDeg: 13, module: GROS_MODULE }).best.count)
      .toBeLessThan(sans.best.count);
  });
});

describe('CALX109 câblage — toit EN PENTE (`solveLivePitched` → `packFlushPlane`)', () => {
  const RING = carreM(30);

  it('option absente ⇒ résultat IDENTIQUE, octet pour octet', () => {
    const sans = solveLivePitched(RING, LAT0, 3000, 22, 180, [], {});
    const defaut = solveLivePitched(RING, LAT0, 3000, 22, 180, [], {}, { module: MODULE_ATELIER_PAR_DEFAUT });

    expect(JSON.stringify(defaut)).toBe(JSON.stringify(sans));
  });

  it('un module plus GRAND pose moins de modules, et le kWc vient de SA puissance', () => {
    const sans = solveLivePitched(RING, LAT0, 3000, 22, 180, [], {});
    const gros = solveLivePitched(RING, LAT0, 3000, 22, 180, [], {}, { module: GROS_MODULE });

    expect(gros.winner.fitCount).toBeLessThan(sans.winner.fitCount);
    expect(gros.winner.kwc).toBeCloseTo(gros.winner.placedCount * 1, 6);
  });
});

describe('CALX109 câblage — l’optimiseur passe les cotes du pan ACTIF', () => {
  it('`optimizer.ts` transmet `module` aux deux solveurs vivants', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/scripts/roofPro11/optimizer.ts'), 'utf8');
    expect(source).toContain('const cotesDuModuleDuPanActif = (): Panel2Module | undefined => {');
    // Deux lignes d'appel : `solveLive` (plat) et `solveLivePitched` (pente).
    expect(source.split('module: cotesDuModuleDuPanActif(),').length - 1).toBe(2);
  });
});
