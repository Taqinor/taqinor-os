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
