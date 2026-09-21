// CALX109 / CALX110 — LE MODULE POSÉ SUR CHAQUE PAN.
//
// CE QUE CE FICHIER PROUVE, dans l'ordre des deux tâches :
//   1. L'ÉCHANTILLON COMMITTÉ EST LU TEL QUEL. Le contrat
//      `backend/.../contract_samples/calepinage_modules_disponibles.json` est le MÊME
//      fichier que le test backend affirme (PACT10) : il est lu ici depuis le dépôt, jamais
//      recopié ni paraphrasé — une divergence entre les deux moitiés rougit des DEUX côtés.
//   2. AUCUN MODULE CHOISI ⇒ PAVAGE IDENTIQUE À CELUI D'AUJOURD'HUI. C'est la garantie de
//      non-régression : le module par défaut de l'atelier reste le repli, et il est NOMMÉ.
//   3. UN MODULE DE 2,0 × 1,0 m CHANGE LE NOMBRE DE RANGÉES. C'est la garantie que les
//      vraies cotes sont bien celles qui pavent — pas une décoration d'écran.
//   4. DEUX PANS, DEUX MODÈLES ⇒ kWc TOTAL = SOMME DES DEUX (CALX110), l'affichage nomme
//      les deux modèles, et un seul modèle rend des chiffres identiques à aujourd'hui.
//
// Aucun DOM, aucun Three, aucun réseau : tout est pur.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  ID_MODULE_PAR_DEFAUT,
  MODULE_PAR_DEFAUT_ATELIER,
  cotesDeModule,
  cotesPourPan,
  ecrireModulesDansDocument,
  estRefus,
  kwcDuPan,
  lireModulesDisponibles,
  resoudreModuleDuPan,
  syntheseModules,
  type DocumentAvecModules,
  type ModuleDocument,
} from './moduleSelect';
import {
  MODULE_ATELIER_PAR_DEFAUT,
  PANEL2_LONG_M,
  PANEL2_SHORT_M,
  PANEL2_WATT,
  layoutProRows2,
  type ProLayout2,
} from '../../lib/roofPro2';
import { type LngLat } from '../../lib/roof';
// CALX110 — le câblage RÉEL : le document écrit par `serializeLayout` et les totaux
// affichés par `computePanStats`. Ce sont les deux seuls consommateurs de ce module.
import { serializeLayout } from './prefill';
import { computePanStats } from './panStats';
import { type Ctx } from './context';
import { type AreaRecord } from './types';

/** L'échantillon de contrat, LU dans le dépôt (jamais recopié ici). */
const CONTRAT = JSON.parse(readFileSync(fileURLToPath(new URL(
  '../../../../../backend/django_core/apps/calepinage/contract_samples/calepinage_modules_disponibles.json',
  import.meta.url,
)), 'utf-8')) as {
  endpoint: string;
  exemple: { modules: unknown[]; champs_requis: string[]; motif_liste_vide: string | null };
  exemple_vide: { modules: unknown[]; motif_liste_vide: string | null };
};

function carre(cote: number, lng0 = -7.6, lat0 = 33.5): LngLat[] {
  const dLat = cote / 111320;
  const dLng = cote / (111320 * Math.cos((lat0 * Math.PI) / 180));
  return [
    [lng0 - dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 - dLat / 2],
    [lng0 + dLng / 2, lat0 + dLat / 2],
    [lng0 - dLng / 2, lat0 + dLat / 2],
  ];
}

/** Le nombre de RANGÉES d'un pavage : les centres projetés sur l'axe de montée. */
function nombreDeRangees(layout: ProLayout2): number {
  const sx = -Math.sin(layout.rowAngleRad);
  const sy = Math.cos(layout.rowAngleRad);
  return new Set(layout.panels.map((p) => Math.round((p.cx * sx + p.cy * sy) * 1000))).size;
}

function module(partiel: Partial<ModuleDocument> & { id: string }): ModuleDocument {
  return {
    produitId: null,
    libelle: `Module ${partiel.id}`,
    longueurMm: 2000,
    largeurMm: 1000,
    epaisseurMm: 30,
    poidsKg: 22,
    pmaxWc: 400,
    source: 'fiche produit',
    ...partiel,
  };
}

/** Un document minimal à deux pans, dans la forme que `serializeLayout` émet. */
function document(a: number, b: number): DocumentAvecModules {
  return {
    zones: [
      { id: 'pan-est', geometry: { count: a, kwc: (a * PANEL2_WATT) / 1000 } },
      { id: 'pan-ouest', geometry: { count: b, kwc: (b * PANEL2_WATT) / 1000 } },
    ],
    result: { panels: a + b, kwc: ((a + b) * PANEL2_WATT) / 1000, annualKwh: 0, savings: null },
    panelWatt: PANEL2_WATT,
  };
}

describe("CALX109 — l'échantillon de contrat est lu tel qu'il est committé", () => {
  it("l'endpoint du contrat est celui que l'atelier appellera", () => {
    expect(CONTRAT.endpoint).toBe(
      'GET /api/django/calepinage/calepinages/<int:pk>/modules-disponibles/');
  });

  it('les fiches complètes sont choisissables, les incomplètes restent listées', () => {
    const catalogue = lireModulesDisponibles(CONTRAT.exemple);
    expect(catalogue.choisissables.map((m) => m.id)).toEqual(['produit-4112']);
    expect(catalogue.grises.map((g) => g.module.id)).toEqual(['produit-4130']);
    expect(catalogue.grises[0].motif).toContain('puissance crête');
    expect(catalogue.motifListeVide).toBeNull();
  });

  it('les cotes arrivent dans la forme du document, en millimètres', () => {
    const [premier] = lireModulesDisponibles(CONTRAT.exemple).choisissables;
    expect(premier.longueurMm).toBe(2278);
    expect(premier.largeurMm).toBe(1134);
    expect(premier.pmaxWc).toBe(580);
    expect(premier.source).toBe('fiche produit');
  });

  it('un catalogue vide rend le motif DU SERVEUR, jamais un motif inventé', () => {
    const catalogue = lireModulesDisponibles(CONTRAT.exemple_vide);
    expect(catalogue.choisissables).toEqual([]);
    expect(catalogue.motifListeVide).toBe(CONTRAT.exemple_vide.motif_liste_vide);
  });

  it('les champs requis du serveur sont ceux qui décident du pavage', () => {
    expect(CONTRAT.exemple.champs_requis).toEqual(['longueurMm', 'largeurMm', 'pmaxWc']);
    for (const champ of CONTRAT.exemple.champs_requis) {
      const incomplet = module({ id: 'x', [champ]: null } as Partial<ModuleDocument> & { id: string });
      const cotes = cotesDeModule(incomplet);
      expect(estRefus(cotes)).toBe(true);
      expect((cotes as { champ: string }).champ).toBe(champ);
    }
  });

  it('une réponse absente ou mal formée ne jette jamais', () => {
    for (const brut of [null, undefined, 42, 'oui', {}, { modules: 'non' }]) {
      expect(lireModulesDisponibles(brut).choisissables).toEqual([]);
    }
  });
});

describe('CALX109 — aucun module choisi : le pavage est celui d’aujourd’hui', () => {
  it('le repli est le module par défaut de l’atelier, et il est NOMMÉ', () => {
    const cotes = cotesPourPan([], undefined);
    expect(estRefus(cotes)).toBe(false);
    expect(cotes).toEqual(MODULE_ATELIER_PAR_DEFAUT);
    expect(MODULE_PAR_DEFAUT_ATELIER.id).toBe(ID_MODULE_PAR_DEFAUT);
    expect(MODULE_PAR_DEFAUT_ATELIER.libelle).toContain("l'atelier");
    expect(MODULE_PAR_DEFAUT_ATELIER.pmaxWc).toBe(PANEL2_WATT);
  });

  it('le pavage sans option est IDENTIQUE au pavage avec le module par défaut', () => {
    const ring = carre(28);
    const aujourdHui = layoutProRows2(ring, 'sud', 33.5);
    const explicite = layoutProRows2(ring, 'sud', 33.5, { module: MODULE_ATELIER_PAR_DEFAUT });
    expect(explicite).toEqual(aujourdHui);
    expect(aujourdHui.dims.alongRow).toBeCloseTo(PANEL2_LONG_M, 6);
    expect(aujourdHui.dims.slope).toBeCloseTo(PANEL2_SHORT_M, 6);
    expect(aujourdHui.kwc).toBeCloseTo((aujourdHui.count * PANEL2_WATT) / 1000, 9);
  });
});

describe('CALX109 — un module de 2,0 × 1,0 m change le nombre de rangées', () => {
  const ring = carre(28);
  const petit = { longM: 2.0, courtM: 1.0, epaisM: 0.03, watt: 450 };

  it('les cotes du module choisi remplacent les constantes', () => {
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    expect(pave.dims.alongRow).toBeCloseTo(2.0, 9);
    expect(pave.dims.slope).toBeCloseTo(1.0, 9);
  });

  it('le pas de rangée et le nombre de rangées suivent la cote du module', () => {
    const aujourdHui = layoutProRows2(ring, 'sud', 33.5);
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    // 1,0 m dans le sens de la pente au lieu de 1,303 : empreinte ET ombre plus courtes,
    // donc un pas plus serré — et donc PLUS de rangées sur le même toit.
    expect(pave.rowPitchM).toBeLessThan(aujourdHui.rowPitchM);
    expect(nombreDeRangees(pave)).toBeGreaterThan(nombreDeRangees(aujourdHui));
  });

  it('le kWc est celui du module posé, jamais la constante de l’atelier', () => {
    const pave = layoutProRows2(ring, 'sud', 33.5, { module: petit });
    expect(pave.kwc).toBeCloseTo((pave.count * 450) / 1000, 9);
  });
});

describe('CALX82 — un module introuvable est REFUSÉ en nommant le champ', () => {
  const catalogue = [module({ id: 'produit-1' })];

  it('un moduleId absent du catalogue nomme `moduleId`', () => {
    const refus = resoudreModuleDuPan(catalogue, 'mod-fantome');
    expect(estRefus(refus)).toBe(true);
    expect((refus as { champ: string }).champ).toBe('moduleId');
    expect((refus as { message: string }).message).toContain('mod-fantome');
  });

  it('une fiche sans puissance nomme `pmaxWc` et ne retombe sur rien', () => {
    const refus = cotesDeModule(module({ id: 'produit-2', pmaxWc: null }));
    expect(estRefus(refus)).toBe(true);
    expect((refus as { champ: string }).champ).toBe('pmaxWc');
    expect((refus as { message: string }).message).toContain('puissance crête');
  });

  it('le grand côté est la plus grande des deux cotes, quel que soit leur ordre', () => {
    const couche = cotesDeModule(module({ id: 'a', longueurMm: 1000, largeurMm: 2000 }));
    expect(couche).toMatchObject({ longM: 2, courtM: 1 });
  });
});

describe('CALX110 — deux modèles sur deux pans', () => {
  const grand = module({ id: 'produit-1', libelle: 'Module 580 Wc', pmaxWc: 580 });
  const petit = module({ id: 'produit-2', libelle: 'Module 440 Wc', pmaxWc: 440 });
  const catalogue = [grand, petit];

  it('le kWc de chaque pan vient de SON module, le total est leur somme', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue,
      parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-2' },
    });
    expect(doc.zones[0].geometry?.kwc).toBeCloseTo((10 * 580) / 1000, 9);
    expect(doc.zones[1].geometry?.kwc).toBeCloseTo((4 * 440) / 1000, 9);
    expect(doc.result?.kwc).toBeCloseTo((10 * 580 + 4 * 440) / 1000, 9);
  });

  it('le document porte le catalogue utilisé et le moduleId de chaque pan', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue,
      parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-2' },
    });
    expect(doc.modules?.map((m) => m.id)).toEqual(['produit-1', 'produit-2']);
    expect(doc.zones[0].geometry?.moduleId).toBe('produit-1');
    expect(doc.zones[1].geometry?.moduleId).toBe('produit-2');
  });

  it('`panelWatt` racine reste servi et vaut le watt du module MAJORITAIRE', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue,
      parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-2' },
    });
    expect(doc.panelWatt).toBe(580); // 10 modules contre 4
  });

  it('l’affichage nomme les DEUX modèles dès que les pans divergent', () => {
    const synthese = syntheseModules(
      { catalogue, parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-2' } },
      [{ id: 'pan-est', panels: 10 }, { id: 'pan-ouest', panels: 4 }],
    );
    expect(synthese.plusieursModeles).toBe(true);
    expect(synthese.libelles).toEqual(['Module 580 Wc', 'Module 440 Wc']);
    expect(synthese.mention).toContain('Plusieurs modèles');
    expect(synthese.mention).toContain('Module 580 Wc');
    expect(synthese.mention).toContain('Module 440 Wc');
  });

  it('un seul modèle : aucune mention « plusieurs », les chiffres restent simples', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue,
      parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-1' },
    });
    expect(doc.panelWatt).toBe(580);
    expect(doc.result?.kwc).toBeCloseTo((14 * 580) / 1000, 9);
    expect(doc.modules?.map((m) => m.id)).toEqual(['produit-1']);
    const synthese = syntheseModules(
      { catalogue, parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'produit-1' } },
      [{ id: 'pan-est', panels: 10 }, { id: 'pan-ouest', panels: 4 }],
    );
    expect(synthese.plusieursModeles).toBe(false);
    expect(synthese.mention).not.toContain('Plusieurs');
  });

  it('kwcDuPan omet plutôt que d’inventer quand la puissance manque', () => {
    expect(kwcDuPan(10, grand)).toBeCloseTo(5.8, 9);
    expect(kwcDuPan(10, module({ id: 'x', pmaxWc: null }))).toBeNull();
    expect(kwcDuPan(Number.NaN, grand)).toBeNull();
  });
});

describe('CALX110 — sans module choisi, le document ne bouge pas d’un octet', () => {
  it('aucun catalogue : le document ressort identique', () => {
    const avant = JSON.stringify(document(10, 4));
    const apres = JSON.stringify(ecrireModulesDansDocument(document(10, 4), null));
    expect(apres).toBe(avant);
  });

  it('catalogue présent mais aucun pan affecté : le document ressort identique', () => {
    const avant = JSON.stringify(document(10, 4));
    const apres = JSON.stringify(ecrireModulesDansDocument(document(10, 4), {
      catalogue: [module({ id: 'produit-1' })],
      parPan: {},
    }));
    expect(apres).toBe(avant);
  });

  it('un pan resté sur le module par défaut n’écrit aucun moduleId', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue: [module({ id: 'produit-1', pmaxWc: 580 })],
      parPan: { 'pan-est': 'produit-1' },
    });
    expect(doc.zones[0].geometry?.moduleId).toBe('produit-1');
    expect(doc.zones[1].geometry?.moduleId).toBeUndefined();
    // Le pan resté par défaut garde SON kWc d'aujourd'hui ; le total est la somme réelle.
    expect(doc.zones[1].geometry?.kwc).toBeCloseTo((4 * PANEL2_WATT) / 1000, 9);
    expect(doc.result?.kwc).toBeCloseTo((10 * 580 + 4 * PANEL2_WATT) / 1000, 9);
  });

  it('un pan qui désigne un module introuvable est laissé tel quel', () => {
    const doc = ecrireModulesDansDocument(document(10, 4), {
      catalogue: [module({ id: 'produit-1', pmaxWc: 580 })],
      parPan: { 'pan-est': 'produit-1', 'pan-ouest': 'mod-fantome' },
    });
    expect(doc.zones[1].geometry?.moduleId).toBeUndefined();
    expect(doc.zones[1].geometry?.kwc).toBeCloseTo((4 * PANEL2_WATT) / 1000, 9);
  });
});

// ── LE CÂBLAGE RÉEL : le document et les totaux affichés ────────────────────────────
// `serializeLayout` est le SEUL point d'écriture du document (leçon CAL60 : ce qui n'y
// voyage pas est perdu au rechargement) et `computePanStats` la seule source des totaux
// affichés. Les deux sont éprouvés ICI, pas seulement la fonction pure qu'ils appellent.

const SOMMETS: [number, number][] = [
  [-7.6, 33.59], [-7.599, 33.59], [-7.599, 33.591], [-7.6, 33.591],
];

function planDe(nombre: number) {
  return {
    pack: { origin: [-7.6, 33.59] as [number, number], azimuthDeg: 180 },
    grid: { panels: Array.from({ length: nombre }, (_, i) => ({ cx: i * 1.2, cy: 0 })), kwc: nombre * 0.72 },
    tiltDeg: 15,
    family: 'south',
    flush: false,
    count: nombre,
  } as unknown as AreaRecord['renderPlan'];
}

function pan(id: string, nombre: number): AreaRecord {
  return {
    id,
    label: `Pan ${id}`,
    vertices: SOMMETS.map(([lng, lat]) => [lng, lat] as [number, number]),
    obstacles: [],
    roofType: 'pitched',
    pitchDeg: 22,
    facingAzimuthDeg: 180,
    facingManual: false,
    neededPanels: nombre,
    neededAuto: true,
    result: null,
    renderPlan: planDe(nombre),
  } as unknown as AreaRecord;
}

function contexte(areas: AreaRecord[]): Ctx {
  const actif = areas[0];
  return {
    areas,
    activeAreaId: actif.id,
    vertices: actif.vertices,
    obstacles: actif.obstacles,
    roofType: actif.roofType,
    pitchDeg: actif.pitchDeg,
    facingAzimuthDeg: actif.facingAzimuthDeg,
    facingManual: false,
    neededPanels: actif.neededPanels,
    neededAuto: actif.neededAuto,
    layoutPlan: null,
    layoutOptimalCount: 0,
  } as unknown as Ctx;
}

describe('CALX110 — le document écrit par `serializeLayout`', () => {
  const grand = module({ id: 'produit-1', libelle: 'Module 580 Wc', pmaxWc: 580 });
  const petit = module({ id: 'produit-2', libelle: 'Module 440 Wc', pmaxWc: 440 });
  const areas = [pan('z1', 10), pan('z2', 4)];

  it('sans catalogue, le document est IDENTIQUE à celui d’aujourd’hui', () => {
    const hier = serializeLayout(contexte(areas));
    const aujourdHui = serializeLayout(contexte(areas), null, { modules: null });
    expect(JSON.stringify(aujourdHui)).toBe(JSON.stringify(hier));
    expect('modules' in hier).toBe(false);
    expect(hier.panelWatt).toBe(PANEL2_WATT);
  });

  it('deux pans, deux modèles : le catalogue et les moduleId voyagent', () => {
    const doc = serializeLayout(contexte(areas), null, {
      modules: { catalogue: [grand, petit], parPan: { z1: 'produit-1', z2: 'produit-2' } },
    });
    expect(doc.modules?.map((m) => m.id)).toEqual(['produit-1', 'produit-2']);
    expect(doc.zones[0].geometry?.moduleId).toBe('produit-1');
    expect(doc.zones[1].geometry?.moduleId).toBe('produit-2');
  });

  it('le kWc total du document est la SOMME des kWc de pan', () => {
    const doc = serializeLayout(contexte(areas), null, {
      modules: { catalogue: [grand, petit], parPan: { z1: 'produit-1', z2: 'produit-2' } },
    });
    expect(doc.zones[0].geometry?.kwc).toBeCloseTo((10 * 580) / 1000, 9);
    expect(doc.zones[1].geometry?.kwc).toBeCloseTo((4 * 440) / 1000, 9);
    expect(doc.result?.kwc).toBeCloseTo((10 * 580 + 4 * 440) / 1000, 9);
    expect(doc.panelWatt).toBe(580); // le majoritaire, servi pour les lecteurs existants
  });
});

describe('CALX110 — les totaux affichés par `computePanStats`', () => {
  const grand = module({ id: 'produit-1', libelle: 'Module 580 Wc', pmaxWc: 580 });
  const petit = module({ id: 'produit-2', libelle: 'Module 440 Wc', pmaxWc: 440 });
  const areas = [pan('z1', 10), pan('z2', 4)];
  const resultat = (a: AreaRecord) => ({
    panels: a.id === 'z1' ? 10 : 4,
    kwc: ((a.id === 'z1' ? 10 : 4) * PANEL2_WATT) / 1000,
    annualKwh: 0,
    savingsLow: 0,
    savingsHigh: 0,
  });

  it('sans résolveur de module, les chiffres sont ceux d’aujourd’hui', () => {
    const stats = computePanStats(areas, resultat);
    expect(stats.site.kwc).toBeCloseTo((14 * PANEL2_WATT) / 1000, 9);
    expect(stats.pans.every((p) => p.moduleId === null)).toBe(true);
    expect(stats.modules.plusieursModeles).toBe(false);
  });

  it('deux modèles : chaque pan porte SON kWc, le site en est la somme', () => {
    const stats = computePanStats(areas, resultat, (a) => (a.id === 'z1' ? grand : petit));
    expect(stats.pans[0].kwc).toBeCloseTo((10 * 580) / 1000, 9);
    expect(stats.pans[1].kwc).toBeCloseTo((4 * 440) / 1000, 9);
    expect(stats.site.kwc).toBeCloseTo((10 * 580 + 4 * 440) / 1000, 9);
  });

  it('l’affichage NOMME les deux modèles', () => {
    const stats = computePanStats(areas, resultat, (a) => (a.id === 'z1' ? grand : petit));
    expect(stats.modules.plusieursModeles).toBe(true);
    expect(stats.modules.mention).toContain('Module 580 Wc');
    expect(stats.modules.mention).toContain('Module 440 Wc');
    expect(stats.pans.map((p) => p.moduleLibelle)).toEqual(['Module 580 Wc', 'Module 440 Wc']);
  });

  it('un seul modèle : aucune mention « plusieurs », le total reste simple', () => {
    const stats = computePanStats(areas, resultat, () => grand);
    expect(stats.modules.plusieursModeles).toBe(false);
    expect(stats.modules.watt).toBe(580);
    expect(stats.site.kwc).toBeCloseTo((14 * 580) / 1000, 9);
  });

  it('le taux d’occupation se mesure sur l’empreinte RÉELLE du module posé', () => {
    const stats = computePanStats(areas, resultat, () => grand);
    const p = stats.pans[0];
    const empreinte = (grand.longueurMm! * grand.largeurMm!) / 1e6;
    expect(p.occupancyRate).toBeCloseTo((p.panels * empreinte) / p.areaM2, 9);
  });
});
