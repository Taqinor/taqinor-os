// CALX111 — numérotation STABLE des modules. Ce fichier garde les trois promesses du plan :
// retirer le module nº3 ne touche aucun de ses voisins, ajouter un module donne le premier
// numéro libre AU-DELÀ du maximum, et la bascule éteinte laisse le document et le rendu
// exactement tels qu'ils sont aujourd'hui.
//
// Tout est testé HORS Three et hors carte : l'attribution est PURE (des centres entrent, des
// numéros sortent), et les deux décisions d'affichage (3D, vue plan) le sont aussi.
import { beforeEach, describe, expect, it } from 'vitest';
import {
  ECHELLE_MIN_ETIQUETTE_PX_PAR_M,
  HISTORIQUE_VIDE,
  ZOOM_MIN_ETIQUETTES,
  attribuerNumeros,
  cleEmplacement,
  conventionDuPan,
  creerRegistre,
  definirSaisie,
  etiquette,
  etiquettes3d,
  etiquettesPlan,
  nomRangee,
  numeroterDocument,
  ordreAttribution,
  rangeesDeModules,
  registreAtelier,
  reinitialiserNumerotation,
  saisieCourante,
  type ConventionNumerotation,
  type ModuleNumerote,
  type ModulePose,
} from './numerotation';

/** Pan orienté plein sud : le repère de pose se confond alors avec (cx, cy) — rangées = cy. */
const SUD = 180;
/** La convention SAISIE des tests (valeurs d'exemple, jamais un défaut du module). */
const CONVENTION: ConventionNumerotation = { prefixe: 'PV', depart: 1, sens: 'ligne' };

/** Deux rangées de deux modules : A = (0,0) et (1.2,0) ; B = (0,1.8) et (1.2,1.8). */
const QUATRE: ModulePose[] = [
  { cx: 0, cy: 0 },
  { cx: 1.2, cy: 0 },
  { cx: 0, cy: 1.8 },
  { cx: 1.2, cy: 1.8 },
];

const numerosDe = (modules: readonly ModuleNumerote[]) => modules.map((m) => m.n);

beforeEach(() => {
  reinitialiserNumerotation();
});

describe('CALX111 — rangées et ordre d’attribution', () => {
  it('nomme les rangées A, B, … puis AA au-delà de Z', () => {
    expect(nomRangee(0)).toBe('A');
    expect(nomRangee(1)).toBe('B');
    expect(nomRangee(25)).toBe('Z');
    expect(nomRangee(26)).toBe('AA');
    expect(nomRangee(27)).toBe('AB');
  });

  it('regroupe les modules par rangée du pavage, de la plus proche à la plus lointaine', () => {
    const rangees = rangeesDeModules(QUATRE, SUD);
    expect(rangees.map((r) => r.nom)).toEqual(['A', 'B']);
    expect(rangees[0].modules.map((m) => m.cx)).toEqual([0, 1.2]);
    expect(rangees[1].modules.map((m) => m.cx)).toEqual([0, 1.2]);
  });

  it('`ligne` parcourt chaque rangée dans le même sens, `serpentin` une sur deux à l’envers', () => {
    expect(ordreAttribution(QUATRE, SUD, 'ligne').map((e) => e.module.cx)).toEqual([0, 1.2, 0, 1.2]);
    expect(ordreAttribution(QUATRE, SUD, 'serpentin').map((e) => e.module.cx)).toEqual([0, 1.2, 1.2, 0]);
  });
});

describe('CALX111 — attribution PURE', () => {
  it('numérote depuis le départ SAISI, dans l’ordre du sens choisi', () => {
    const ligne = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    expect(numerosDe(ligne.modules)).toEqual([1, 2, 3, 4]);
    expect(ligne.modules.map((m) => m.rangee)).toEqual(['A', 'A', 'B', 'B']);

    const serpentin = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, { ...CONVENTION, sens: 'serpentin' }, SUD);
    // La rangée B est parcourue à l'envers : le module le plus à l'est y prend le nº 3.
    expect(numerosDe(serpentin.modules)).toEqual([1, 2, 4, 3]);
  });

  it('respecte un départ SAISI autre que 1', () => {
    const res = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, { ...CONVENTION, depart: 101 }, SUD);
    expect(numerosDe(res.modules)).toEqual([101, 102, 103, 104]);
  });

  it('rend les modules dans l’ORDRE D’ENTRÉE (CAL248 aligne `solarAccess` dessus)', () => {
    const melange: ModulePose[] = [QUATRE[3], QUATRE[0], QUATRE[2], QUATRE[1]];
    const res = attribuerNumeros(melange, HISTORIQUE_VIDE, CONVENTION, SUD);
    expect(res.modules.map((m) => [m.cx, m.cy])).toEqual(melange.map((m) => [m.cx, m.cy]));
    expect(numerosDe(res.modules)).toEqual([4, 1, 3, 2]);
  });

  it('DONE — retirer le module nº3 laisse tous les autres numéros inchangés', () => {
    const pose = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    expect(numerosDe(pose.modules)).toEqual([1, 2, 3, 4]);

    const restants = [QUATRE[0], QUATRE[1], QUATRE[3]]; // le nº 3 est retiré
    const apres = attribuerNumeros(restants, pose.historique, CONVENTION, SUD);
    expect(numerosDe(apres.modules)).toEqual([1, 2, 4]);
    expect(apres.modules.map((m) => m.n)).not.toContain(3);
  });

  it('DONE — ajouter un module lui donne le premier numéro libre AU-DELÀ du maximum', () => {
    const pose = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    const retire = attribuerNumeros([QUATRE[0], QUATRE[1], QUATRE[3]], pose.historique, CONVENTION, SUD);
    const ajoute = attribuerNumeros(
      [QUATRE[0], QUATRE[1], QUATRE[3], { cx: 2.4, cy: 0 }],
      retire.historique,
      CONVENTION,
      SUD,
    );
    // 3 reste VACANT : un numéro libéré par un retrait n'est jamais redonné.
    expect(numerosDe(ajoute.modules)).toEqual([1, 2, 4, 5]);
  });

  it('un module reposé au MÊME emplacement retrouve SON numéro', () => {
    const pose = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    const retire = attribuerNumeros([QUATRE[0], QUATRE[1], QUATRE[3]], pose.historique, CONVENTION, SUD);
    const repose = attribuerNumeros(QUATRE, retire.historique, CONVENTION, SUD);
    expect(numerosDe(repose.modules)).toEqual([1, 2, 3, 4]);
  });

  it('un décalage sous le centimètre reste le MÊME emplacement', () => {
    const pose = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    const bouge = attribuerNumeros([{ cx: 0.002, cy: 0 }], pose.historique, CONVENTION, SUD);
    expect(cleEmplacement(0.002, 0)).toBe(cleEmplacement(0, 0));
    expect(numerosDe(bouge.modules)).toEqual([1]);
  });

  it('trace `attribution: initiale` au PREMIER passage, et ne la réécrit jamais', () => {
    const pose = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, CONVENTION, SUD);
    expect(pose.numerotation).toEqual({ prefixe: 'PV', depart: 1, sens: 'ligne', attribution: 'initiale' });
    const suite = attribuerNumeros(QUATRE, pose.historique, pose.numerotation!, SUD);
    expect(suite.numerotation?.attribution).toBe('initiale');
  });

  it('des numéros venus d’AILLEURS ne reçoivent aucune trace inventée', () => {
    const historique = { numeros: new Map([[cleEmplacement(0, 0), 7]]), plafond: 7 };
    const res = attribuerNumeros([QUATRE[0], QUATRE[1]], historique, { sens: 'ligne' }, SUD);
    expect(numerosDe(res.modules)).toEqual([7, 8]);
    expect(res.numerotation?.attribution).toBeUndefined();
  });

  it('REFUS nommé : sans sens saisi, aucun numéro n’est attribué', () => {
    const res = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, { depart: 1 }, SUD);
    expect(res.refus?.champ).toBe('numerotation.sens');
    expect(numerosDe(res.modules)).toEqual([undefined, undefined, undefined, undefined]);
    expect(res.numerotation).toBeNull();
  });

  it('REFUS nommé : sans premier numéro saisi, aucun numéro n’est attribué', () => {
    const res = attribuerNumeros(QUATRE, HISTORIQUE_VIDE, { sens: 'ligne' }, SUD);
    expect(res.refus?.champ).toBe('numerotation.depart');
    expect(numerosDe(res.modules)).toEqual([undefined, undefined, undefined, undefined]);
  });
});

describe('CALX111 — étiquette lue depuis `n`', () => {
  it('lit le numéro du document, jamais la place dans le tableau', () => {
    expect(etiquette({ cx: 0, cy: 0, n: 4 })).toBe('nº4');
    expect(etiquette({ cx: 0, cy: 0, n: 4 }, { prefixe: 'PV' })).toBe('PV nº4');
  });

  it('un module sans numéro n’en reçoit pas un de circonstance', () => {
    expect(etiquette({ cx: 0, cy: 0 })).toBe('');
    expect(etiquette(null)).toBe('');
    expect(etiquette({ cx: 0, cy: 0, n: 0 })).toBe('');
  });
});

// ─────────────────────────── Le document, seule source des numéros ───────────────────────────

/** Un document à UN pan, dans la forme que `serializeLayout` émet. */
function documentUnPan(panels: ModuleNumerote[] = QUATRE.map((m) => ({ ...m }))) {
  return {
    version: 2,
    zones: [{ id: 'z1', geometry: { azimuthDeg: SUD, count: panels.length, panels } }],
  };
}

describe('CALX111 — crochet document (serializeLayout)', () => {
  it('DONE — bascule ÉTEINTE : le document ressort inchangé', () => {
    const document = documentUnPan();
    const temoin = JSON.parse(JSON.stringify(document));
    expect(numeroterDocument(document)).toBeNull();
    expect(document).toEqual(temoin);
  });

  it('bascule allumée : écrit `n`, `rangee` et la convention du pan', () => {
    definirSaisie({ actif: true, prefixe: 'PV', depart: 1, sens: 'ligne' });
    const document = documentUnPan();
    expect(numeroterDocument(document)).toBeNull();
    const geometrie = document.zones[0].geometry;
    expect(numerosDe(geometrie.panels)).toEqual([1, 2, 3, 4]);
    expect(geometrie.panels.map((m) => m.rangee)).toEqual(['A', 'A', 'B', 'B']);
    expect((geometrie as { numerotation?: ConventionNumerotation }).numerotation).toEqual({
      prefixe: 'PV',
      depart: 1,
      sens: 'ligne',
      attribution: 'initiale',
    });
  });

  it('CALX83 — deux modules d’un même pan ne partagent jamais un numéro', () => {
    definirSaisie({ actif: true, depart: 1, sens: 'serpentin' });
    const document = documentUnPan();
    numeroterDocument(document);
    const numeros = document.zones[0].geometry.panels.map((m) => m.n);
    expect(new Set(numeros).size).toBe(numeros.length);
    for (const n of numeros) expect(Number.isInteger(n) && (n as number) >= 1).toBe(true);
  });

  it('bascule allumée sans sens saisi : rien n’est écrit et le champ est nommé', () => {
    definirSaisie({ actif: true, depart: 1 });
    const document = documentUnPan();
    const temoin = JSON.parse(JSON.stringify(document));
    expect(numeroterDocument(document)?.champ).toBe('numerotation.sens');
    expect(document).toEqual(temoin);
  });

  it('un document qui porte DÉJÀ des numéros les garde, et le suivant prend le maximum + 1', () => {
    // La forme de `EXEMPLE_MODULES_NUMEROTES` (CALX83) : 1, 2 et 4 — le nº 3 est vacant.
    const registre = creerRegistre();
    const dejaNumerote = documentUnPan([
      { cx: 0, cy: 0, n: 1, rangee: 'A' },
      { cx: 1.2, cy: 0, n: 2, rangee: 'A' },
      { cx: 0, cy: 1.8, n: 4, rangee: 'B' },
    ]);
    dejaNumerote.zones[0].geometry.numerotation = { prefixe: 'PV', depart: 1, sens: 'ligne' };
    registre.absorberDocument(dejaNumerote);

    const suivant = documentUnPan([...QUATRE.map((m) => ({ ...m }))]);
    numeroterDocument(suivant, { ...saisieCourante(), actif: true, depart: 1, sens: 'ligne' }, registre);
    // Le module (1.2, 1.8) est NEUF : il prend 5, et 3 reste vacant pour toujours.
    expect(numerosDe(suivant.zones[0].geometry.panels)).toEqual([1, 2, 4, 5]);
  });

  it('bascule éteinte : les numéros absorbés sont réécrits (ACAL31 — lecture seule, aucune attribution)', () => {
    const registre = creerRegistre();
    const relu = documentUnPan([
      { cx: 0, cy: 0, n: 1, rangee: 'A' },
      { cx: 1.2, cy: 0, n: 2, rangee: 'A' },
      { cx: 0, cy: 1.8, n: 4, rangee: 'B' },
    ]);
    relu.zones[0].geometry.numerotation = { prefixe: 'PV', depart: 1, sens: 'ligne' };
    registre.absorberDocument(relu);
    // Le pan actif re-pavé ressort SANS numéros : la bascule éteinte les réécrit à l'identique,
    // et le module neuf (1.2, 1.8) n'en reçoit AUCUN (jamais d'attribution bascule éteinte).
    const repave = documentUnPan(QUATRE.map((m) => ({ ...m })));
    expect(numeroterDocument(repave, { ...saisieCourante(), actif: false }, registre)).toBeNull();
    const geometrie = repave.zones[0].geometry;
    expect(numerosDe(geometrie.panels)).toEqual([1, 2, 4, undefined]);
    expect(geometrie.panels.map((m) => m.rangee)).toEqual(['A', 'A', 'B', undefined]);
    expect((geometrie as { numerotation?: ConventionNumerotation }).numerotation).toEqual({ prefixe: 'PV', depart: 1, sens: 'ligne' });
  });

  it('CALX83 — l’unicité est par PAN : deux pans portent chacun leur nº 1', () => {
    definirSaisie({ actif: true, depart: 1, sens: 'ligne' });
    const document = {
      version: 2,
      zones: [
        { id: 'z1', geometry: { azimuthDeg: SUD, panels: QUATRE.map((m) => ({ ...m })) } },
        { id: 'z2', geometry: { azimuthDeg: SUD, panels: QUATRE.map((m) => ({ ...m })) } },
      ],
    };
    numeroterDocument(document);
    expect(numerosDe(document.zones[0].geometry.panels)).toEqual([1, 2, 3, 4]);
    expect(numerosDe(document.zones[1].geometry.panels)).toEqual([1, 2, 3, 4]);
  });

  it('la convention DÉJÀ inscrite gagne sur la saisie (un écran rouvert reprend la même main)', () => {
    const deja: ConventionNumerotation = { depart: 50, sens: 'serpentin' };
    const fusion = conventionDuPan(deja, { ...saisieCourante(), depart: 1, sens: 'ligne' });
    expect(fusion.depart).toBe(50);
    expect(fusion.sens).toBe('serpentin');
  });
});

// ─────────────────────────── Décisions d'affichage (pures) ───────────────────────────

describe('CALX111 — étiquettes 3D', () => {
  const numeros = new Map([
    [cleEmplacement(0, 0), 1],
    [cleEmplacement(1.2, 0), 2],
    [cleEmplacement(0, 1.8), 4],
  ]);
  const poses: ModulePose[] = [QUATRE[0], QUATRE[1], QUATRE[2]];

  it('DONE — bascule éteinte : aucune étiquette, donc rendu identique à aujourd’hui', () => {
    expect(etiquettes3d(poses, numeros, null, 20, saisieCourante())).toEqual([]);
  });

  it('sous le zoom saisi : aucune étiquette', () => {
    const etat = { ...saisieCourante(), actif: true };
    expect(etiquettes3d(poses, numeros, null, ZOOM_MIN_ETIQUETTES - 0.1, etat)).toEqual([]);
    expect(etiquettes3d(poses, numeros, null, null, etat)).toEqual([]);
  });

  it('au-delà du zoom saisi : le TEXTE vient de `n`, avec le trou du nº 3', () => {
    const etat = { ...saisieCourante(), actif: true };
    const posees = etiquettes3d(poses, numeros, { prefixe: 'PV' }, ZOOM_MIN_ETIQUETTES, etat);
    expect(posees).toEqual([
      { index: 0, texte: 'PV nº1' },
      { index: 1, texte: 'PV nº2' },
      { index: 2, texte: 'PV nº4' },
    ]);
  });

  it('un module que le document ne numérote pas n’est pas étiqueté', () => {
    const etat = { ...saisieCourante(), actif: true };
    const posees = etiquettes3d([{ cx: 9, cy: 9 }], numeros, null, 21, etat);
    expect(posees).toEqual([]);
  });
});

describe('CALX111 — étiquettes de la vue plan', () => {
  const modules: ModuleNumerote[] = [
    { cx: 0, cy: 0, n: 1 },
    { cx: 1.2, cy: 0, n: 4 },
  ];
  const plan = {
    pxPerM: 20,
    panels: [
      [
        [0, 0],
        [10, 0],
        [10, 20],
        [0, 20],
      ],
      [
        [30, 0],
        [40, 0],
        [40, 20],
        [30, 20],
      ],
    ] as ReadonlyArray<ReadonlyArray<readonly [number, number]>>,
  };

  it('bascule éteinte : aucune étiquette', () => {
    expect(etiquettesPlan(plan, modules, null, saisieCourante())).toEqual([]);
  });

  it('pose le numéro au centre du rectangle projeté', () => {
    const etat = { ...saisieCourante(), actif: true };
    expect(etiquettesPlan(plan, modules, null, etat)).toEqual([
      { index: 0, texte: 'nº1', x: 5, y: 10 },
      { index: 1, texte: 'nº4', x: 35, y: 10 },
    ]);
  });

  it('échelle trop petite pour qu’un chiffre soit lisible : aucune étiquette', () => {
    const etat = { ...saisieCourante(), actif: true };
    const petit = { ...plan, pxPerM: ECHELLE_MIN_ETIQUETTE_PX_PAR_M - 1 };
    expect(etiquettesPlan(petit, modules, null, etat)).toEqual([]);
  });

  it('projection et modules qui ne se correspondent pas : aucun appariement deviné', () => {
    const etat = { ...saisieCourante(), actif: true };
    expect(etiquettesPlan(plan, [modules[0]], null, etat)).toEqual([]);
    expect(etiquettesPlan(null, modules, null, etat)).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// ACAL307 — numérotation STABLE d'office : chaque pan PAVÉ reçoit ses numéros sans geste
// de numérotation ; un repavage garde les `n` des modules gardés ; un document ancien
// enregistré sans geste n'en reçoit aucun. Chemin réel : `serializeLayout`.
// ═══════════════════════════════════════════════════════════════════════════════
import { hydrateFromDevis, serializeLayout } from './prefill';
import { type Ctx } from './context';
import { type AreaRecord } from './types';

const VERTS: [number, number][] = [[-7.6, 33.59], [-7.599, 33.59], [-7.599, 33.591], [-7.6, 33.591]];
function plan(cellules: ModulePose[]) {
  return {
    pack: { origin: [-7.6, 33.59] as [number, number], azimuthDeg: SUD },
    grid: { panels: cellules, kwc: cellules.length * 0.72 },
    tiltDeg: 10, family: 'south', flush: false, count: cellules.length,
  } as unknown as AreaRecord['renderPlan'];
}
function ctxPave(cellules: ModulePose[], documentRelu?: Record<string, unknown>): Ctx {
  const zone = {
    id: 'z1', label: 'Pan', vertices: VERTS, obstacles: [], roofType: 'flat', pitchDeg: 10, facingAzimuthDeg: 180,
    facingManual: false, neededPanels: cellules.length, neededAuto: false, result: null, renderPlan: plan(cellules),
  } as unknown as AreaRecord;
  return {
    areas: [zone], activeAreaId: 'z2', vertices: [], obstacles: [], roofType: 'flat', pitchDeg: 10,
    facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, layoutPlan: null,
    layoutOptimalCount: 0, ...(documentRelu ? { documentRelu } : {}),
  } as unknown as Ctx;
}

describe('ACAL307 — numérotation d’office', () => {
  it('pavage d’un pan neuf : numéros attribués sans geste', () => {
    const doc = serializeLayout(ctxPave(QUATRE));
    const g = doc.zones[0].geometry!;
    expect((g.panels as ModuleNumerote[]).map((m) => m.n)).toEqual([1, 2, 3, 4]);
    expect((g as { numerotation?: ConventionNumerotation }).numerotation).toMatchObject({ depart: 1, sens: 'ligne' });
  });

  it('repavage : n conservé pour les modules gardés', () => {
    const premier = serializeLayout(ctxPave(QUATRE));
    reinitialiserNumerotation();
    // Rouvert puis repavé avec un module en moins : les trois gardés gardent LEUR numéro.
    const relu = JSON.parse(JSON.stringify(premier));
    // Le boot sème la mémoire depuis le document relu (`deserializeLayout`), comme ici :
    hydrateFromDevis({ id: 1, geometrie: { roof_layout: relu }, cibleVendue: false });
    const repave = serializeLayout(ctxPave([QUATRE[0], QUATRE[2], QUATRE[3]], relu));
    expect((repave.zones[0].geometry!.panels as ModuleNumerote[]).map((m) => m.n)).toEqual([1, 3, 4]);
  });

  it('enregistrement sans geste d’un document ancien : aucun numéro ajouté', () => {
    const ancien = serializeLayout(ctxPave(QUATRE, undefined));
    reinitialiserNumerotation();
    // Un document ANCIEN non numéroté : mêmes positions, aucun `n`.
    const sansNumeros = JSON.parse(JSON.stringify(ancien));
    for (const p of sansNumeros.zones[0].geometry.panels) {
      delete p.n;
      delete p.rangee;
    }
    delete sansNumeros.zones[0].geometry.numerotation;
    const sortie = serializeLayout(ctxPave(QUATRE, sansNumeros));
    expect((sortie.zones[0].geometry!.panels as ModuleNumerote[]).some((m) => m.n !== undefined)).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// Numérotation stable (suite ACAL1720) — un numéro n'est attribué QUE par un enregistrement. Le sondage
// « modifié ? » de la page (1,5 s), la capture du pan quitté et l'accès solaire sérialisent sans cesse : chaque
// pose intermédiaire d'un glissement d'inclinaison dépensait 40 numéros (des calepinages réels portaient
// n = 2236…2275 pour 40 modules). Chemin réel : `serializeLayout` (+ `engagerNumeros` pour l'enregistrement).
// ═══════════════════════════════════════════════════════════════════════════════
describe('Numérotation stable — seul l’enregistrement engage des numéros', () => {
  /** 40 modules (10 × 4), décalés de `dx` mètres le long des rangées. */
  const grille = (dx = 0): ModulePose[] => Array.from({ length: 40 }, (_, i) => ({ cx: (i % 10) * 1.2 + dx, cy: Math.floor(i / 10) * 2.1 }));
  const numeros = (doc: ReturnType<typeof serializeLayout>) => (doc.zones[0].geometry!.panels as ModuleNumerote[]).map((m) => m.n);
  const plage = (debut: number, compte = 40) => Array.from({ length: compte }, (_, i) => debut + i);
  /** Le document stocké (n = 1…40), relu au boot comme le fait la page. */
  function rouvrir(): Record<string, unknown> {
    const stocke = JSON.parse(JSON.stringify(serializeLayout(ctxPave(grille()), null, { engagerNumeros: true })));
    reinitialiserNumerotation();
    hydrateFromDevis({ id: 1, geometrie: { roof_layout: stocke }, cibleVendue: false });
    return stocke;
  }

  it('défaut (1) — sondages à 0, 0, 5, 10, 15 cm puis 0 : aucun numéro dépensé, plafond engagé inchangé', () => {
    const relu = rouvrir();
    const vus = [0, 0, 0.05, 0.1, 0.15, 0].map((dx) => numeros(serializeLayout(ctxPave(grille(dx), relu))));
    expect(vus).toEqual([plage(1), plage(1), plage(41), plage(41), plage(41), plage(1)]);
    expect(registreAtelier.historique('z1').plafond).toBe(40);
  });

  it('rien ne bouge : deux sondages successifs rendent le MÊME document (l’empreinte ne bat pas)', () => {
    const relu = rouvrir();
    const a = serializeLayout(ctxPave(grille(0.05), relu));
    const b = serializeLayout(ctxPave(grille(0.05), relu));
    expect(JSON.stringify(b)).toBe(JSON.stringify(a));
  });

  it('l’enregistrement engage ce que l’écran montrait ; le sondage suivant rend le document enregistré', () => {
    const relu = rouvrir();
    const montre = serializeLayout(ctxPave(grille(0.1), relu));
    const enregistre = serializeLayout(ctxPave(grille(0.1), relu), null, { engagerNumeros: true });
    expect(numeros(enregistre)).toEqual(numeros(montre));
    expect(registreAtelier.historique('z1').plafond).toBe(80);
    expect(JSON.stringify(serializeLayout(ctxPave(grille(0.1), relu)))).toBe(JSON.stringify(enregistre));
    // Engagés, 41…80 ne sont plus jamais redonnés : une autre pose neuve part au-delà.
    expect(numeros(serializeLayout(ctxPave(grille(0.05), relu)))).toEqual(plage(81));
    expect(numeros(serializeLayout(ctxPave(grille(0.1), relu)))).toEqual(plage(41));
    expect(numeros(serializeLayout(ctxPave(grille(), relu)))).toEqual(plage(1));
  });

  it('CALX111 tenu AVANT tout enregistrement : retirer un module neuf ne renumérote pas ses voisins', () => {
    expect(numeros(serializeLayout(ctxPave(QUATRE)))).toEqual([1, 2, 3, 4]);
    expect(numeros(serializeLayout(ctxPave([QUATRE[0], QUATRE[1], QUATRE[3]])))).toEqual([1, 2, 4]);
    expect(numeros(serializeLayout(ctxPave([QUATRE[0], QUATRE[1], QUATRE[3], { cx: 2.4, cy: 0 }])))).toEqual([1, 2, 4, 5]);
    expect(numeros(serializeLayout(ctxPave(QUATRE)))).toEqual([1, 2, 3, 4]);
    expect(registreAtelier.historique('z1').plafond).toBe(0); // rien d'engagé : aucun enregistrement
  });

  it('les étiquettes montrent les numéros provisoires, sans les engager', () => {
    const relu = rouvrir();
    serializeLayout(ctxPave(grille(0.05), relu));
    expect(registreAtelier.modules('z1').map((m) => m.n)).toEqual(plage(41));
    expect(registreAtelier.numerosAffiches('z1').get(cleEmplacement(0.05, 0))).toBe(41);
    expect(registreAtelier.historique('z1').numeros.has(cleEmplacement(0.05, 0))).toBe(false);
  });
});

// Numérotation stable (suite ACAL1720) — le document porte le PLAFOND d'un pan dont les modules du haut sont
// retirés (`plafondsNumerotation`) : rouvert, il ne redonne jamais ces numéros à d'autres modules — sinon une
// affectation manuelle de chaîne enregistrée par `<pan>#<n>` (chaines.py) désignait d'autres panneaux.
describe('Numérotation stable — le plafond voyage avec le document', () => {
  const grille20 = (): ModulePose[] => Array.from({ length: 20 }, (_, i) => ({ cx: (i % 10) * 1.2, cy: Math.floor(i / 10) * 2.1 }));
  const numeros = (doc: ReturnType<typeof serializeLayout>) => (doc.zones[0].geometry!.panels as ModuleNumerote[]).map((m) => m.n);
  const enregistrer = (cellules: ModulePose[], relu?: Record<string, unknown>) =>
    JSON.parse(JSON.stringify(serializeLayout(ctxPave(cellules, relu), null, { engagerNumeros: true }))) as Record<string, unknown> & ReturnType<typeof serializeLayout>;
  const rouvrir = (doc: Record<string, unknown>) => {
    reinitialiserNumerotation();
    hydrateFromDevis({ id: 1, geometrie: { roof_layout: JSON.parse(JSON.stringify(doc)) }, cibleVendue: false });
  };

  it('défaut (2) — retirer 15…20, enregistrer, rouvrir : les modules neufs prennent 21…, jamais 15…20', () => {
    const vingt = enregistrer(grille20());
    expect(numeros(vingt)).toEqual(Array.from({ length: 20 }, (_, i) => i + 1));
    expect('plafondsNumerotation' in vingt).toBe(false); // aucun retrait : aucune clé
    rouvrir(vingt);
    const quatorze = enregistrer(grille20().slice(0, 14), vingt);
    expect(quatorze.plafondsNumerotation).toEqual({ z1: 20 });
    rouvrir(quatorze);
    expect(registreAtelier.historique('z1').plafond).toBe(20);
    const neufs = Array.from({ length: 6 }, (_, i) => ({ cx: i * 1.2, cy: 8.4 }));
    const apres = enregistrer([...grille20().slice(0, 14), ...neufs], quatorze);
    expect(numeros(apres)).toEqual([...Array.from({ length: 14 }, (_, i) => i + 1), 21, 22, 23, 24, 25, 26]);
    expect('plafondsNumerotation' in apres).toBe(false); // 26 est posé : le plafond est lisible sans la clé
  });

  it('la lecture (sondage) écrit la MÊME clé que l’enregistrement : l’empreinte ne bat pas', () => {
    const vingt = enregistrer(grille20());
    rouvrir(vingt);
    const lu = serializeLayout(ctxPave(grille20().slice(0, 14), vingt));
    expect(lu.plafondsNumerotation).toEqual({ z1: 20 });
    expect(registreAtelier.historique('z1').plafond).toBe(20);
  });

  it('document qui porte la clé, rouvert et enregistré sans geste : identique, clé comprise', () => {
    const vingt = enregistrer(grille20());
    rouvrir(vingt);
    const quatorze = enregistrer(grille20().slice(0, 14), vingt);
    rouvrir(quatorze);
    expect(JSON.stringify(enregistrer(grille20().slice(0, 14), quatorze))).toBe(JSON.stringify(quatorze));
  });

  it('retirer un module du MILIEU n’écrit aucune clé (le plus haut n posé suffit)', () => {
    const vingt = enregistrer(grille20());
    rouvrir(vingt);
    const troue = enregistrer(grille20().filter((_, i) => i !== 4), vingt);
    expect(numeros(troue)).not.toContain(5);
    expect('plafondsNumerotation' in troue).toBe(false);
  });
});

// Numérotation stable (suite ACAL1720) — C : les numéros DÉJÀ stockés ne sont jamais réécrits. Un calepinage réel
// (n = 2236…2275), une inclinaison changée puis remise, quelques modules ajoutés, enregistré : chaque module gardé
// garde SON n, les neufs passent au-delà du plafond, et les clés serveur `<pan>#<n>` désignent les mêmes places.
import { identifiantsModulesParCellule } from './libellesAffectation';

describe('Numérotation stable — un calepinage stocké n’est jamais renuméroté', () => {
  const quarante = (dx = 0): ModulePose[] => Array.from({ length: 40 }, (_, i) => ({ cx: (i % 10) * 1.2 + dx, cy: Math.floor(i / 10) * 2.1 }));
  const numeros = (doc: { zones: Array<{ geometry?: { panels?: unknown[] } }> }) => (doc.zones[0].geometry!.panels as ModuleNumerote[]).map((m) => m.n);
  /** Le document stocké : les 40 modules portent n = 2236…2275 (le compteur d'avant ce correctif). */
  function stocke(): Record<string, unknown> {
    const doc = JSON.parse(JSON.stringify(serializeLayout(ctxPave(quarante()), null, { engagerNumeros: true })));
    (doc.zones[0].geometry.panels as ModuleNumerote[]).forEach((p, i) => { p.n = 2236 + i; });
    reinitialiserNumerotation();
    hydrateFromDevis({ id: 1, geometrie: { roof_layout: JSON.parse(JSON.stringify(doc)) }, cibleVendue: false });
    return doc;
  }
  /** Clé serveur de chaque module, par emplacement (la lecture de l'atelier, `identifiantsModulesParCellule`). */
  const clesParPlace = (poses: ModulePose[]) => {
    const ids = identifiantsModulesParCellule(poses.map((_, i) => i), 'z1', poses);
    return new Map(poses.map((p, i) => [cleEmplacement(p.cx, p.cy), ids[i]]));
  };

  it('inclinaison changée puis remise, 2 modules ajoutés, enregistré : aucun n réécrit, neufs au-delà de 2275', () => {
    const relu = stocke();
    const avant = clesParPlace(quarante());
    expect(avant.get(cleEmplacement(0, 0))).toBe('z1#2236');
    for (const dx of [0.04, 0.08, 0.12, 0.08, 0.04]) serializeLayout(ctxPave(quarante(dx), relu)); // le glissement
    const ajoutes = [{ cx: 12, cy: 0 }, { cx: 12, cy: 2.1 }];
    const enregistre = serializeLayout(ctxPave([...quarante(), ...ajoutes], relu), null, { engagerNumeros: true });
    expect(numeros(enregistre)).toEqual([...Array.from({ length: 40 }, (_, i) => 2236 + i), 2276, 2277]);
    const apres = clesParPlace([...quarante(), ...ajoutes]);
    for (const [place, cle] of avant) expect(apres.get(place)).toBe(cle); // chaque ligne manuelle vise la même place
    expect(registreAtelier.historique('z1').plafond).toBe(2277);
  });
});

// Revue du lot 8 (suite ACAL1720) — un numéro montré seulement à titre PROVISOIRE ne peut jamais être engagé à une
// SECONDE place. Chemin : la géométrie capturée en quittant un pan (lecture, `geometrieZoneActive`) garde les `n`
// provisoires et est réémise telle quelle (pan non actif, photo d'annulation qui traverse un enregistrement).
describe('Numérotation stable — un numéro engagé désigne une seule place', () => {
  const quarante = (): ModulePose[] => Array.from({ length: 40 }, (_, i) => ({ cx: (i % 10) * 1.2, cy: Math.floor(i / 10) * 2.1 }));
  type Doc = ReturnType<typeof serializeLayout>;
  const panneaux = (doc: Doc) => doc.zones[0].geometry!.panels as ModuleNumerote[];
  const numeros = (doc: Doc) => panneaux(doc).map((m) => m.n);
  const Y = { cx: 12, cy: 0 };
  const X = { cx: 12, cy: 6.3 };
  function rouvrir(): Record<string, unknown> {
    const stocke = JSON.parse(JSON.stringify(serializeLayout(ctxPave(quarante()), null, { engagerNumeros: true })));
    reinitialiserNumerotation();
    hydrateFromDevis({ id: 1, geometrie: { roof_layout: stocke }, cibleVendue: false });
    return stocke;
  }
  /** Le pan z1 réémis TEL QUEL depuis une géométrie capturée (pan non actif ou photo d'annulation). */
  function ctxCapture(geometrie: unknown, relu: Record<string, unknown>): Ctx {
    const ctx = ctxPave(quarante(), relu);
    (ctx.areas[0] as unknown as Record<string, unknown>).geometrieEnregistree = JSON.parse(JSON.stringify(geometrie));
    return ctx;
  }

  it('annulation à travers un enregistrement : Y (capturé à 41) ne reprend pas le 41 engagé par X', () => {
    const relu = rouvrir();
    const capture = serializeLayout(ctxPave([...quarante(), Y], relu)).zones[0].geometry; // Y montré 41, capturé
    expect(panneaux(serializeLayout(ctxPave([...quarante(), X], relu))).at(-1)!.n).toBe(41); // X montré 41
    const s1 = serializeLayout(ctxPave([...quarante(), X], relu), null, { engagerNumeros: true });
    expect(numeros(s1).at(-1)).toBe(41); // X engagé 41
    const montre = serializeLayout(ctxCapture(capture, relu)); // annulation : la photo réémet Y:41
    const s2 = serializeLayout(ctxCapture(capture, relu), null, { engagerNumeros: true });
    expect(numeros(montre).at(-1)).toBe(42); // l'écran montre ce que l'enregistrement engage
    expect(numeros(s2).at(-1)).toBe(42);
    const places41 = [...registreAtelier.historique('z1').numeros].filter(([, n]) => n === 41).map(([place]) => place);
    expect(places41).toEqual([cleEmplacement(X.cx, X.cy)]);
    const s3 = serializeLayout(ctxPave([...quarante(), Y, X], relu), null, { engagerNumeros: true });
    expect(numeros(s3).slice(-2)).toEqual([42, 41]);
    expect(new Set(numeros(s3)).size).toBe(42); // jamais deux fois le même numéro dans le pan
  });

  it('une géométrie qui porte deux fois un numéro provisoire, ou un autre numéro à une place engagée : corrigée', () => {
    const relu = rouvrir();
    const geometrie = JSON.parse(JSON.stringify((relu as { zones: Array<{ geometry: { panels: ModuleNumerote[] } }> }).zones[0].geometry));
    geometrie.panels[0].n = 7; // place engagée au nº1
    geometrie.panels.push({ ...Y, n: 41 }, { ...X, n: 41 });
    const doc = serializeLayout(ctxCapture(geometrie, relu), null, { engagerNumeros: true });
    const n = numeros(doc);
    expect(n[0]).toBe(1);
    expect(n.slice(-2)).toEqual([41, 42]);
    expect(new Set(n).size).toBe(n.length);
  });
});