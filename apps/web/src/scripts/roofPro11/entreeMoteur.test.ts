/* ============================================================================
   CALX3 — l'entrée du moteur composée depuis la scène, et son chemin retour.
   ----------------------------------------------------------------------------
   Ce que ces tests tiennent :
     * un tracé fermé à deux zones produit un document que la porte moteur
       accepte — chaque section déclarée présente, au type déclaré ;
     * un tracé vide produit `null`, jamais un document creux ;
     * les huit actions de raccourci existent et sont des fonctions ;
     * `calquesDisponibles()` ne rend que du vocabulaire de calque d'atelier ;
     * les neuf clés d'API déjà exposées par le constructeur sont toujours là.
   ========================================================================== */
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  composerEntreeMoteur,
  centresDepuisPlan,
  versRepereDuPack,
  rangeesDuResultat,
  calquesDisponibles,
  construireRaccourcis,
  ACTIONS_RACCOURCIS,
  axeRangeeImpose,
  versRepereRangee,
  versEstNord,
  SCHEMA_VERSION_MOTEUR,
  type SceneMoteur,
  type DocumentMoteur,
} from './entreeMoteur';
import { ORDRE_RENDU_CALQUES, MAPLIBRE_LAYERS_PAR_CALQUE } from './mapDraw';
import { type LngLat } from '../../lib/roof';

// ── Le CONTRÔLE DE FORME de la porte moteur ────────────────────────────────
// Les neuf sections que `POST /calepinage/moteur/calculer/` déclare accepter,
// avec le type de chacune. Un document qui passe ici est un document que la
// porte sait lire ; il n'est pas question ici de ce que le moteur en fera.
function refusDeLaPorte(doc: unknown): string[] {
  const refus: string[] = [];
  if (!doc || typeof doc !== 'object') return ['le corps n’est pas un objet'];
  const d = doc as Record<string, unknown>;
  if (!Number.isInteger(d.schema_version)) refus.push('schema_version');
  if (typeof d.repere !== 'string') refus.push('repere');
  const listeDePoints = (v: unknown) =>
    Array.isArray(v) && v.every((p) => Array.isArray(p) && p.every((n) => typeof n === 'number' && Number.isFinite(n)));
  if (!listeDePoints(d.contour)) refus.push('contour');
  const listeDObjets = (v: unknown) =>
    Array.isArray(v) && v.every((o) => !!o && typeof o === 'object' && !Array.isArray(o));
  if (!listeDObjets(d.surfaces)) refus.push('surfaces');
  if (!listeDObjets(d.kits)) refus.push('kits');
  if (!d.parametres || typeof d.parametres !== 'object' || Array.isArray(d.parametres)) refus.push('parametres');
  if (!listeDObjets(d.obstacles)) refus.push('obstacles');
  if (!listeDObjets(d.zones)) refus.push('zones');
  if (!Array.isArray(d.engagements)) refus.push('engagements');
  return refus;
}

// ── Une scène d'essai : un carré d'environ 12 m de côté près de Casablanca ──
const CARRE: LngLat[] = [
  [-7.6, 33.55],
  [-7.59987, 33.55],
  [-7.59987, 33.55011],
  [-7.6, 33.55011],
];

const KIT = {
  code: 'ATELIER-720',
  libelle: 'Module de l’atelier',
  moduleLongM: 2.384,
  moduleCourtM: 1.303,
  puissanceModuleWc: 720,
  inclinaisonDeg: 13,
  orientation: 'PORTRAIT' as const,
  modulesParTable: 1,
};

function scene(overrides: Partial<SceneMoteur> = {}): SceneMoteur {
  return {
    repere: 'CAL-ESSAI',
    pans: [
      {
        id: 'PAN-A',
        label: 'Pan A',
        vertices: CARRE,
        obstacles: [
          {
            id: 'obs-1',
            centerLng: -7.59995,
            centerLat: 33.55005,
            lengthM: 1.2,
            widthM: 0.8,
            type: 'cheminee',
            heightM: 1.5,
          },
        ],
        pitchDeg: 0,
        facingAzimuthDeg: 180,
        neededPanels: 18,
        neededAuto: false,
      },
    ],
    zonesExclusion: [
      {
        id: 'zone-interdite',
        nature: 'INTERDITE',
        vertices: [
          [-7.59998, 33.55002],
          [-7.59996, 33.55002],
          [-7.59996, 33.55004],
          [-7.59998, 33.55004],
        ],
        setbackM: 0.4,
        heightM: 0.9,
      },
      {
        id: 'zone-preferee',
        nature: 'PREFEREE',
        vertices: [
          [-7.59992, 33.55006],
          [-7.5999, 33.55006],
          [-7.5999, 33.55008],
          [-7.59992, 33.55008],
        ],
        setbackM: 0,
      },
    ],
    retraits: { lateralM: 0.5, extremityM: 0.5, parapetM: 0.5, jointM: 0 },
    kit: KIT,
    ...overrides,
  };
}

describe('CALX3 — composerEntreeMoteur', () => {
  it('un tracé fermé à deux zones produit un document que la porte accepte', () => {
    const doc = composerEntreeMoteur(scene()) as DocumentMoteur;
    expect(doc).not.toBeNull();
    expect(refusDeLaPorte(doc)).toEqual([]);

    expect(doc.schema_version).toBe(SCHEMA_VERSION_MOTEUR);
    expect(doc.repere).toBe('CAL-ESSAI');
    expect(doc.surfaces).toHaveLength(1);
    expect(doc.surfaces[0].repere).toBe('PAN-A');
    expect(doc.surfaces[0].type).toBe('polygone');
    expect(doc.surfaces[0].contour).toHaveLength(4);
    expect(doc.zones.map((z) => z.repere)).toEqual(['zone-interdite', 'zone-preferee']);
    expect(doc.zones[0].nature).toBe('INTERDITE');
    expect(doc.zones[0].sommets).toHaveLength(4);
    expect(doc.obstacles).toHaveLength(1);
    expect(doc.kits).toHaveLength(1);
    expect(doc.parametres.kits).toEqual([KIT.code]);
    // L'axe est le MÊME sur la surface et dans les paramètres : le moteur
    // refuse un document où les deux divergent.
    expect(doc.surfaces[0].axe_rangee).toBe(doc.parametres.axe_rangee);
  });

  it('les quatre retraits saisis sortent sur les quatre rives du moteur', () => {
    const doc = composerEntreeMoteur(
      scene({ retraits: { lateralM: 0.35, extremityM: 0.6, parapetM: 0.2, jointM: 0.05 } }),
    ) as DocumentMoteur;
    expect(doc.parametres.rives).toEqual({
      laterale_m: 0.35,
      extremite_m: 0.6,
      acrotere_m: 0.2,
      joint_m: 0.05,
    });
  });

  it('une hauteur d’obstacle non renseignée sort à null, jamais à zéro', () => {
    const s = scene();
    const sansHauteur: SceneMoteur = {
      ...s,
      pans: [{ ...s.pans[0], obstacles: [{ ...s.pans[0].obstacles![0], heightM: undefined }] }],
    };
    const doc = composerEntreeMoteur(sansHauteur) as DocumentMoteur;
    expect(doc.obstacles[0].hauteur_m).toBeNull();
    expect(doc.obstacles[0].degagement_m).toBeGreaterThan(0);
  });

  it('un engagement n’existe que là où la cible a été saisie', () => {
    const s = scene();
    const auto: SceneMoteur = { ...s, pans: [{ ...s.pans[0], neededAuto: true }] };
    expect((composerEntreeMoteur(s) as DocumentMoteur).engagements).toEqual([['PAN-A', 18]]);
    expect((composerEntreeMoteur(auto) as DocumentMoteur).engagements).toEqual([]);
  });

  it('un tracé vide produit null', () => {
    expect(composerEntreeMoteur(scene({ pans: [] }))).toBeNull();
    expect(
      composerEntreeMoteur(
        scene({ pans: [{ id: 'PAN-A', vertices: [CARRE[0], CARRE[1]], pitchDeg: 0, facingAzimuthDeg: 180 }] }),
      ),
    ).toBeNull();
  });
});

describe('CALX3 — repère des rangées', () => {
  it('l’axe est dérivé du kit et de la visée, jamais saisi', () => {
    expect(axeRangeeImpose(2, 180)).toBe('NORD_SUD');
    expect(axeRangeeImpose(1, 180)).toBe('EST_OUEST');
    expect(axeRangeeImpose(1, 90)).toBe('NORD_SUD');
  });

  it('la conversion (est, nord) → (x, y) est réversible sur les deux axes', () => {
    for (const axe of ['NORD_SUD', 'EST_OUEST'] as const) {
      const [x, y] = versRepereRangee(3, -7, axe);
      expect(versEstNord(x, y, axe)).toEqual([3, -7]);
    }
  });
});

describe('CALX3 — centresDepuisPlan (le retour du plan)', () => {
  const resultat = {
    plan: {
      rangees: [
        { surface: 'PAN-A', y0: 0.5, emprise_m: 2.28, modules: 3, kit: 'ATELIER-720', troncons: [[0.5, 4.5]] },
        { surface: 'PAN-A', y0: 3.3, emprise_m: 2.28, modules: 2, kit: 'ATELIER-720', troncons: [[0.5, 3.2]] },
      ],
    },
  };

  it('lit les rangées quelle que soit la forme publiée', () => {
    expect(rangeesDuResultat(resultat)).toHaveLength(2);
    expect(rangeesDuResultat({ plans: [{ rangees: resultat.plan.rangees }] })).toHaveLength(2);
    expect(rangeesDuResultat({ rangees: resultat.plan.rangees })).toHaveLength(2);
    expect(rangeesDuResultat(null)).toEqual([]);
    expect(rangeesDuResultat({})).toEqual([]);
  });

  it('rend autant de centres que le moteur a compté de modules', () => {
    const sortie = centresDepuisPlan(resultat, scene());
    expect(sortie).not.toBeNull();
    expect(sortie!.centres).toHaveLength(5);
    for (const c of sortie!.centres) {
      expect(Number.isFinite(c.cx)).toBe(true);
      expect(Number.isFinite(c.cy)).toBe(true);
    }
  });

  it('un résultat sans rangée ne pose rien', () => {
    expect(centresDepuisPlan({ plan: { rangees: [] } }, scene())).toBeNull();
    expect(centresDepuisPlan(resultat, scene({ pans: [] }))).toBeNull();
  });

  it('changer d’origine translate les centres, sans les tourner', () => {
    const sortie = centresDepuisPlan(resultat, scene())!;
    const memeOrigine = versRepereDuPack(sortie.centres, sortie.ancrage, [
      sortie.ancrage.lng0,
      sortie.ancrage.lat0,
    ]);
    memeOrigine.forEach((c, i) => {
      expect(c.cx).toBeCloseTo(sortie.centres[i].cx, 9);
      expect(c.cy).toBeCloseTo(sortie.centres[i].cy, 9);
    });
    const decale = versRepereDuPack(sortie.centres, sortie.ancrage, [
      sortie.ancrage.lng0 - 0.001,
      sortie.ancrage.lat0,
    ]);
    const dx = decale[0].cx - sortie.centres[0].cx;
    decale.forEach((c, i) => {
      expect(c.cx - sortie.centres[i].cx).toBeCloseTo(dx, 9);
      expect(c.cy).toBeCloseTo(sortie.centres[i].cy, 9);
    });
    expect(dx).toBeGreaterThan(0);
  });
});

describe('CALX3 — raccourcis', () => {
  it('les huit actions existent et sont des fonctions', () => {
    const raccourcis = construireRaccourcis({});
    expect(Object.keys(raccourcis).sort()).toEqual([...ACTIONS_RACCOURCIS].sort());
    expect(ACTIONS_RACCOURCIS).toHaveLength(8);
    for (const action of ACTIONS_RACCOURCIS) {
      expect(typeof raccourcis[action]).toBe('function');
      expect(() => raccourcis[action]()).not.toThrow();
    }
  });

  it('chaque clé appelle le geste qu’on lui a branché', () => {
    const appels: string[] = [];
    const raccourcis = construireRaccourcis({
      outilTrace: () => appels.push('outilTrace'),
      supprimer: () => appels.push('supprimer'),
    });
    raccourcis.outilTrace();
    raccourcis.supprimer();
    raccourcis.dupliquer();
    expect(appels).toEqual(['outilTrace', 'supprimer']);
  });
});

describe('CALX3 — calquesDisponibles', () => {
  /** Le vocabulaire des calques de l'atelier, du fond vers le dessus. */
  const CALQUES_ATELIER = [
    'imagerie',
    'cadastre',
    'photo',
    'plan',
    'trace_client',
    'obstacles',
    'zones',
    'panneaux',
    'ombres',
    'mesures',
  ];

  it('le constructeur et l’atelier parlent du même jeu d’identifiants', () => {
    expect([...ORDRE_RENDU_CALQUES]).toEqual(CALQUES_ATELIER);
  });

  it('ne rend que des identifiants de calque, dans l’ordre de rendu', () => {
    const installees = new Set([
      ...MAPLIBRE_LAYERS_PAR_CALQUE.zones,
      ...MAPLIBRE_LAYERS_PAR_CALQUE.obstacles,
      'une-couche-qui-n-est-pas-un-calque',
    ]);
    const carte = { getLayer: (id: string) => (installees.has(id) ? { id, type: 'fill' } : undefined) };
    const dispo = calquesDisponibles(carte);
    expect(dispo).toEqual(['obstacles', 'zones']);
    for (const id of dispo) expect(CALQUES_ATELIER).toContain(id);
  });

  it('aucune carte, ou aucune couche posée, ne rend aucun calque — jamais une exception', () => {
    expect(calquesDisponibles(null)).toEqual([]);
    expect(calquesDisponibles(undefined)).toEqual([]);
    expect(calquesDisponibles({})).toEqual([]);
    expect(calquesDisponibles({ getLayer: () => undefined })).toEqual([]);
    expect(
      calquesDisponibles({
        getLayer: () => {
          throw new Error('style pas encore chargé');
        },
      }),
    ).toEqual([]);
  });
});

describe('CALX3 — l’API du constructeur', () => {
  const source = readFileSync(
    fileURLToPath(new URL('../roof-tool-pro11.ts', import.meta.url)),
    'utf8',
  );
  const bloc = source.slice(source.indexOf('opts.onApiReady?.({'));

  it('les neuf clés déjà exposées sont toujours là', () => {
    expect(bloc.length).toBeGreaterThan(0);
    for (const cle of [
      'serializeLayout',
      'snapshot',
      'renderImageHd',
      'planView',
      'setLayerState',
      'setReferenceContourVisible',
      'recommencerDepuisTraceClient',
      'setHorizonProfile',
      'horizonStatus',
    ]) {
      expect(bloc).toContain(`${cle}:`);
    }
  });

  it('les quatre clés de CALX3 s’y ajoutent', () => {
    for (const cle of ['entreeMoteur', 'appliquerPlan', 'raccourcis', 'calquesDisponibles']) {
      expect(bloc).toContain(`${cle}:`);
    }
  });
});
