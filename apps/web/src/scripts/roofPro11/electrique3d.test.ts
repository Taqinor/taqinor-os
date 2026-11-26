/* ============================================================================
   CALX219 — LA COUCHE ÉLECTRIQUE DE L'ATELIER, vérifiée hors navigateur.
   ----------------------------------------------------------------------------
   LA FIXTURE N'EST PAS ÉCRITE ICI. Elle est LUE dans l'échantillon de contrat
   committé (`apps/calepinage/contract_samples/electrique_equipements.json`,
   CALX201) — le fichier que la moitié serveur affirme et que l'atelier lit. Un
   mock écrit à la main serait une deuxième source de vérité : c'est exactement
   le défaut que le contrat d'abord (PACT10) supprime. Si la forme du document
   change, ce test casse tout seul.

   Ce que ce fichier prouve :
     * les HUIT types produisent HUIT objets distincts, un par type ;
     * une entrée sans `lng`/`lat` est IGNORÉE sans jeter, et NOMMÉE ;
     * un `type` hors de l'énumération fermée est IGNORÉ et NOMMÉ ;
     * un document sans `electrical` rend un groupe VIDE ;
     * aucune dimension numérique n'est lue ailleurs que dans le document : la
       position d'un marqueur est EXACTEMENT la projection de ses `lng`/`lat`,
       et sa taille vient des seules conventions de dessin du module.
   ========================================================================== */

import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import * as THREE from 'three';
import type { LngLat } from '../../lib/roof'; // ACAL1944
import {
  ID_CALQUE_ELECTRIQUE,
  TYPES_EQUIPEMENT,
  DESSIN_PAR_TYPE,
  NOM_TYPE_FR,
  creerCoucheElectrique,
  creerMarqueur,
  etiquettesChaines, // ACAL1944
  calqueElectriqueVisible, // T4-X7-015
  brancherCalqueElectrique, // T4-X7-015
  estTypeEquipement,
  lireCoucheElectrique,
  versScene,
  PAS_DEPLACEMENT_ORGANE_M, // ACAL1317
  type DocumentElectrique,
  type EquipementElectrique,
  type TypeEquipement,
} from './electrique3d';
import { serialiserDocumentAtelier, appliquerHydratationAuCtx, type EtatSerialisationAtelier } from './hydratation'; // ACAL26
import { hydrateFromDevis, type SerializedLayout } from './prefill'; // ACAL26
import { uniformSetbacks } from '../../lib/roofPro2'; // ACAL26
import { type Ctx } from './context'; // ACAL26
import { racineDepot } from './harnaisAtelier';

// ───────────────────────────────────────────── l'échantillon de contrat committé


function contrat(nom: string): Record<string, unknown> {
  const chemin = join(
    racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
    'contract_samples', `${nom}.json`,
  );
  if (!existsSync(chemin)) {
    throw new Error(`Échantillon de contrat introuvable : ${chemin} — le contrat part EN PREMIER (PACT10).`);
  }
  return JSON.parse(readFileSync(chemin, 'utf8'));
}

const ECHANTILLON = contrat('electrique_equipements');
const DOC_HUIT = (ECHANTILLON.exemple as { electrical: DocumentElectrique }).electrical;
const DOC_VIDE = (ECHANTILLON.exemple_vide as { electrical: DocumentElectrique }).electrical;

/** ACAL26 — un ctx d'atelier minimal (une zone, aucun panneau) : assez pour appeler le
 *  VRAI sérialiseur câblé du constructeur (`serialiserDocumentAtelier`). */
function ctxAtelier(electrical?: DocumentElectrique | null): Ctx & { electrical?: DocumentElectrique | null } {
  const zone = {
    id: 'z1', label: 'Pan', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]] as [number, number][],
    obstacles: [], roofType: 'flat' as const, pitchDeg: 10, facingAzimuthDeg: 180, facingManual: false,
    neededPanels: 0, neededAuto: true, result: null, renderPlan: null,
  };
  return {
    areas: [zone], activeAreaId: 'z1', vertices: zone.vertices, obstacles: [], roofType: 'flat', pitchDeg: 10,
    facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true, layoutPlan: null,
    layoutOptimalCount: 0, shadeObstructions: [], environment: [], shadeFactors: null, sunDay: Number.NaN,
    sunHour: Number.NaN, sceneOrigin: [-7.6, 33.5], ...(electrical !== undefined ? { electrical } : {}),
  } as unknown as Ctx & { electrical?: DocumentElectrique | null };
}

/** ACAL26 — l'état que le wrapper `onApiReady.serializeLayout` passe au sérialiseur câblé. */
function etatConstructeur(
  couche: ReturnType<typeof creerCoucheElectrique>,
  devisOrigin: EtatSerialisationAtelier['devisOrigin'],
): EtatSerialisationAtelier {
  return { devisOrigin, solarAccess: null, setbacks: uniformSetbacks(), horizonProfile: null, modules: null, coucheElectrique: couche };
}

/** L'origine ENU de la scène : le repère du site de l'échantillon. */
const ORIGINE: [number, number] = [-7.6, 33.5];

/** Signature de la silhouette d'un objet : type de géométrie + ses paramètres.
 *  Deux marqueurs de même signature seraient le MÊME dessin. */
function signature(objet: THREE.Object3D): string {
  const maillage = objet as THREE.Mesh;
  const geo = maillage.geometry as THREE.BufferGeometry & { type: string; parameters?: Record<string, unknown> };
  const params = geo.parameters ?? {};
  const cles = Object.keys(params).sort();
  return `${geo.type}|${cles.map((k) => `${k}=${params[k]}`).join(',')}`;
}

describe('CALX219 — huit types, huit objets distincts', () => {
  it('l’échantillon de contrat exerce bien les HUIT types fermés', () => {
    const types = (DOC_HUIT.equipements ?? []).map((e) => e.type);
    expect(new Set(types).size).toBe(TYPES_EQUIPEMENT.length);
    expect([...TYPES_EQUIPEMENT].every((t) => types.includes(t))).toBe(true);
  });

  it('le groupe porte un objet par équipement, et chaque type a SA silhouette', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    expect(couche.groupe.children).toHaveLength(8);
    const parType = new Map<string, string>();
    for (const enfant of couche.groupe.children) {
      const type = String(enfant.userData.type);
      expect(estTypeEquipement(type)).toBe(true);
      parType.set(type, signature(enfant));
    }
    expect(parType.size).toBe(8);
    // Huit silhouettes DIFFÉRENTES : aucun type n'emprunte le dessin d'un autre.
    expect(new Set(parType.values()).size).toBe(8);
  });

  it('chaque marqueur porte son identité et son étiquette flottante', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    const premier = (DOC_HUIT.equipements ?? [])[0];
    const marqueur = couche.groupe.children.find((c) => c.userData.id === premier.id);
    expect(marqueur).toBeTruthy();
    expect(marqueur!.userData.calque).toBe(ID_CALQUE_ELECTRIQUE);
    expect(marqueur!.userData.label).toBe(premier.label);
    const etiquette = marqueur!.children.find((c) => c.userData.role === 'etiquette');
    expect(etiquette).toBeTruthy();
    expect(etiquette!.userData.texte).toBe(premier.label);
  });

  it('un libellé vide retombe sur le NOM FRANÇAIS du type, jamais sur un code', () => {
    const doc: DocumentElectrique = {
      equipements: [
        { id: 'eq1', type: 'tgbt', label: '', lng: -7.6, lat: 33.5, source: 'saisie' },
      ],
    };
    const couche = creerCoucheElectrique({ electrical: doc, sceneOrigin: ORIGINE });
    const etiquette = couche.groupe.children[0].children.find((c) => c.userData.role === 'etiquette');
    expect(etiquette!.userData.texte).toBe(NOM_TYPE_FR.tgbt);
  });
});

describe('CALX219 — ce qui est ignoré est NOMMÉ, jamais jeté', () => {
  it('une entrée sans `lng`/`lat` est ignorée sans exception, et nommée', () => {
    const doc = {
      equipements: [
        { id: 'eq1', type: 'onduleur', label: 'Onduleur 1 — pan sud', source: 'saisie' },
        ...(DOC_HUIT.equipements ?? []).slice(0, 1),
      ],
    } as unknown as DocumentElectrique;
    let couche!: ReturnType<typeof creerCoucheElectrique>;
    expect(() => {
      couche = creerCoucheElectrique({ electrical: doc, sceneOrigin: ORIGINE });
    }).not.toThrow();
    expect(couche.groupe.children).toHaveLength(1);
    const dits = couche.avertissements();
    expect(dits).toHaveLength(1);
    expect(dits[0]).toContain('Onduleur 1 — pan sud');
    expect(dits[0]).toContain("n'a pas de position");
  });

  it('un `type` hors énumération est ignoré ET nommé avec la liste fermée', () => {
    const doc = {
      equipements: [
        { id: 'eq1', type: 'onduleur_hybride', label: 'X', lng: -7.6, lat: 33.5, source: 'saisie' },
      ],
    } as unknown as DocumentElectrique;
    const couche = creerCoucheElectrique({ electrical: doc, sceneOrigin: ORIGINE });
    expect(couche.groupe.children).toHaveLength(0);
    const dit = couche.avertissements()[0];
    expect(dit).toContain('onduleur_hybride');
    for (const t of TYPES_EQUIPEMENT) expect(dit).toContain(t);
  });

  it('deux entrées de même identifiant : la seconde est écartée et nommée', () => {
    const doc = {
      equipements: [
        { id: 'eq1', type: 'onduleur', label: 'A', lng: -7.6, lat: 33.5, source: 'saisie' },
        { id: 'eq1', type: 'tgbt', label: 'B', lng: -7.601, lat: 33.5, source: 'saisie' },
      ],
    } as unknown as DocumentElectrique;
    const couche = creerCoucheElectrique({ electrical: doc, sceneOrigin: ORIGINE });
    expect(couche.groupe.children).toHaveLength(1);
    expect(couche.avertissements()[0]).toContain('eq1');
  });
});

describe('CALX219 — un document sans couche électrique n’invente rien', () => {
  it('document sans `electrical` ⇒ groupe VIDE, aucun avertissement', () => {
    const couche = creerCoucheElectrique({ sceneOrigin: ORIGINE });
    expect(couche.groupe.children).toHaveLength(0);
    expect(couche.avertissements()).toEqual([]);
    expect(couche.documentElectrique()).toBeNull();
  });

  it('`electrical.equipements` vide ⇒ groupe VIDE (l’exemple vide du contrat)', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_VIDE, sceneOrigin: ORIGINE });
    expect(couche.groupe.children).toHaveLength(0);
    expect(couche.avertissements()).toEqual([]);
  });

  it('`lireCoucheElectrique` d’un document quelconque ne jette jamais', () => {
    for (const brut of [null, undefined, 42, 'texte', {}, { electrical: 7 }, { electrical: { equipements: 3 } }]) {
      expect(() => lireCoucheElectrique(brut)).not.toThrow();
      expect(lireCoucheElectrique(brut).equipements).toEqual([]);
    }
  });
});

// ACAL1944 — sur la carte réelle de l'étape Électrique, ni « Chaîne n » ni pastille « Onduleur » (maquette Electrique).
describe('ACAL1944 — chaîne servie ⇒ étiquette « Chaîne n » et pastille « Onduleur »', () => {
  it('une pilule par chaîne servie, à sa couleur, au nord de ses modules ; aucune chaîne ⇒ rien', () => {
    const bleu = { r: 36 / 255, g: 130 / 255, b: 214 / 255 };
    const groupe = etiquettesChaines([
      { libelle: 'Chaîne 1', couleur: bleu, points: [[0, 0, 7], [2, 0, 7], [0, 2, 7], [2, 2, 7.4]] },
      { libelle: 'Chaîne 2', couleur: { r: 1, g: 0.5, b: 0 }, points: [[10, 0, 7]] },
    ]);
    expect(groupe.children.map((e) => e.userData.texte)).toEqual(['Chaîne 1', 'Chaîne 2']);
    expect(groupe.children[0].userData.pastille).toBe('rgb(36, 130, 214)');
    expect(groupe.children[0].position.x).toBeCloseTo(1, 9);
    expect(groupe.children[0].position.y).toBeGreaterThan(2); // hors des modules, au nord de la rangée la plus haute
    expect(groupe.children[0].position.z).toBeGreaterThan(7.4);
    expect(etiquettesChaines([]).children).toHaveLength(0);
  });
  it('l’onduleur posé porte la pastille « Onduleur » ; les autres organes gardent leur cartouche', () => {
    const base = { lng: -7.6002, lat: 33.5001, altitudeM: null, source: 'saisie' as const };
    const ond = creerMarqueur({ ...base, id: 'o1', type: 'onduleur', label: '' }, ORIGINE).children[0];
    expect([ond.userData.texte, ond.userData.pastille]).toEqual(['Onduleur', '#0c1335']);
    expect(creerMarqueur({ ...base, id: 't1', type: 'tgbt', label: 'TGBT' }, ORIGINE).children[0].userData.pastille).toBeUndefined();
  });
  it('la couche hydratée avant la première scène se redessine à l’origine de la scène (l’onduleur revient sur la carte)', () => {
    const ctx: { electrical: DocumentElectrique; sceneOrigin: LngLat | null } = {
      electrical: { equipements: [{ id: 'o1', type: 'onduleur', label: 'Onduleur', lng: -7.6002, lat: 33.5001, altitudeM: null, source: 'saisie' }] },
      sceneOrigin: null,
    };
    const couche = creerCoucheElectrique(ctx as never);
    couche.rafraichir(); // hydratation : aucune origine de scène encore
    expect(Math.abs(couche.groupe.children[0].position.x)).toBeGreaterThan(1e5); // dessinée autour de [0, 0] : hors carte
    ctx.sceneOrigin = ORIGINE;
    (couche.groupe.userData.siOrigineChange as () => void)(); // la scène se rattache après son rendu
    const [est, nord] = versScene(-7.6002, 33.5001, ORIGINE);
    expect(couche.groupe.children[0].position.x).toBeCloseTo(est, 9);
    expect(couche.groupe.children[0].position.y).toBeCloseTo(nord, 9);
  });
});

describe('CALX219 — aucune dimension lue ailleurs que dans le document', () => {
  it('la position du marqueur est EXACTEMENT la projection de ses lng/lat', () => {
    const equipement: EquipementElectrique = {
      id: 'eq1', type: 'onduleur', label: 'Onduleur', lng: -7.6002, lat: 33.5001,
      altitudeM: 3.2, source: 'saisie',
    };
    const marqueur = creerMarqueur(equipement, ORIGINE);
    const [est, nord] = versScene(equipement.lng, equipement.lat, ORIGINE);
    expect(marqueur.position.x).toBeCloseTo(est, 9);
    expect(marqueur.position.y).toBeCloseTo(nord, 9);
    // La seule constante qui entre dans le z est la HAUTEUR DE DESSIN du type.
    expect(marqueur.position.z).toBeCloseTo(3.2 + DESSIN_PAR_TYPE.onduleur.hauteurM / 2, 9);
  });

  it('une altitude absente n’est PAS zéro : le marqueur le déclare', () => {
    const sansAltitude: EquipementElectrique = {
      id: 'eq7', type: 'tgbt', label: 'TGBT existant', lng: -7.601, lat: 33.4996,
      altitudeM: null, source: 'import',
    };
    const marqueur = creerMarqueur(sansAltitude, ORIGINE);
    expect(marqueur.userData.altitudeRenseignee).toBe(false);
    const avecAltitude = creerMarqueur({ ...sansAltitude, altitudeM: 4 }, ORIGINE);
    expect(avecAltitude.userData.altitudeRenseignee).toBe(true);
  });

  it('les tailles de dessin couvrent les huit types, et elles seules', () => {
    const cles = Object.keys(DESSIN_PAR_TYPE).sort();
    expect(cles).toEqual([...TYPES_EQUIPEMENT].sort());
    for (const type of TYPES_EQUIPEMENT as readonly TypeEquipement[]) {
      expect(DESSIN_PAR_TYPE[type].hauteurM).toBeGreaterThan(0);
    }
  });

  it('déplacer le point du document déplace le marqueur d’autant, et de rien d’autre', () => {
    const base: EquipementElectrique = {
      id: 'eq1', type: 'coffret_dc', label: 'Coffret', lng: -7.6, lat: 33.5, source: 'saisie',
    };
    const a = creerMarqueur(base, ORIGINE);
    const b = creerMarqueur({ ...base, lng: -7.599 }, ORIGINE);
    const [estA] = versScene(base.lng, base.lat, ORIGINE);
    const [estB] = versScene(-7.599, base.lat, ORIGINE);
    expect(b.position.x - a.position.x).toBeCloseTo(estB - estA, 9);
    expect(b.position.y).toBeCloseTo(a.position.y, 9);
    expect(b.position.z).toBeCloseTo(a.position.z, 9);
  });
});

/* ============================================================================
   CALX220 — POSER, DÉPLACER, RETIRER, ET LE PERSISTER.
   ----------------------------------------------------------------------------
   Le document est la seule source de vérité : chaque geste l'écrit, le groupe
   est reconstruit depuis lui, et l'annulation restaure l'état d'AVANT — y
   compris « le plan ne portait encore aucune couche électrique », qui n'est pas
   la même chose qu'une couche vide.
   ========================================================================== */

/** La forme EXACTE d'une entrée : ses clés et le type de chacune. C'est ainsi
 *  qu'on épingle une entrée écrite contre l'échantillon committé — `jsonschema`
 *  n'existe pas côté vitest. */
function formeDe(entree: Record<string, unknown>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const cle of Object.keys(entree).sort()) {
    const v = entree[cle];
    out[cle] = v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v;
  }
  return out;
}

describe('CALX220 — la pose écrit le document, et sa forme est celle du contrat', () => {
  it('poser écrit une entrée dans `electrical.equipements[]`, et le sérialiseur CÂBLÉ du constructeur la porte (ACAL26)', () => {
    // ACAL26 — réécrit : l'ancien test appelait `couche.ecrireDansDocument` directement et
    // passait donc à côté du wrapper `onApiReady.serializeLayout`, qui ne transmettait PAS
    // la couche (leçon D). On pose via la vraie couche puis on sérialise par la VRAIE meta.
    const ctx = ctxAtelier();
    const couche = creerCoucheElectrique(ctx);
    expect(couche.documentElectrique()).toBeNull();
    couche.armerPose('onduleur');
    const pose = couche.poser([-7.6002, 33.5001]);
    expect(pose.ok).toBe(true);
    const doc = couche.documentElectrique();
    expect(doc?.equipements).toHaveLength(1);
    expect(doc?.equipements?.[0].lng).toBe(-7.6002);
    expect(couche.groupe.children).toHaveLength(1);
    for (const devisOrigin of [null, { devisId: 7, panelWatt: null, scenario: null }]) {
      const document3d = serialiserDocumentAtelier(ctx, null, etatConstructeur(couche, devisOrigin));
      expect(document3d.electrical?.equipements, devisOrigin ? 'branche devis' : 'branche lead').toHaveLength(1);
      // ... et ne partage AUCUNE référence avec l'état vivant.
      expect(document3d.electrical).not.toBe(doc);
    }
  });

  it('rien n’est écrit tant qu’aucun organe n’est posé : le document reste intact', () => {
    const couche = creerCoucheElectrique({ sceneOrigin: ORIGINE });
    const avant = { version: 2, zones: [], setbacksM: { lateralM: 0.4 } };
    expect(couche.ecrireDansDocument(avant)).toEqual(avant);
  });

  it('l’entrée écrite a EXACTEMENT la forme de l’échantillon de contrat', () => {
    const ctx: { electrical?: DocumentElectrique | null; sceneOrigin: [number, number] } = {
      sceneOrigin: ORIGINE,
    };
    const couche = creerCoucheElectrique(ctx);
    couche.armerPose('coffret_dc');
    couche.poser([-7.6003, 33.5002], { label: 'Coffret DC toiture', altitudeM: 3.2, rotationDeg: 0 });
    const ecrite = couche.documentElectrique()!.equipements![0] as unknown as Record<string, unknown>;
    // L'échantillon `eq2` est le même organe : mêmes clés, mêmes types.
    const modele = (DOC_HUIT.equipements ?? []).find((e) => e.id === 'eq2') as unknown as Record<string, unknown>;
    const formeModele = formeDe(modele);
    const formeEcrite = formeDe(ecrite);
    // Toute clé écrite existe au contrat, avec le MÊME type (les clés optionnelles
    // non renseignées sont ABSENTES, jamais écrites à null ou à zéro).
    for (const [cle, type] of Object.entries(formeEcrite)) {
      expect(Object.keys(formeModele)).toContain(cle);
      if (formeModele[cle] !== 'null') expect(type).toBe(formeModele[cle]);
    }
    // Les six clés OBLIGATOIRES du schéma sont toutes là.
    for (const cle of ['id', 'type', 'label', 'lng', 'lat', 'source']) {
      expect(Object.keys(formeEcrite)).toContain(cle);
    }
    expect(ecrite.source).toBe('saisie');
    expect(ecrite.type).toBe('coffret_dc');
  });

  it('les identifiants posés ne rejouent jamais un identifiant déjà pris', () => {
    const ctx: { electrical?: DocumentElectrique | null; sceneOrigin: [number, number] } = {
      electrical: { equipements: [...(DOC_HUIT.equipements ?? []).map((e) => ({ ...e }))] },
      sceneOrigin: ORIGINE,
    };
    const couche = creerCoucheElectrique(ctx);
    couche.armerPose('batterie');
    const pose = couche.poser([-7.6007, 33.4999]);
    expect(pose.ok).toBe(true);
    const ids = couche.documentElectrique()!.equipements!.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids[ids.length - 1]).toBe('eq9');
  });

  it('sans type armé, la pose est REFUSÉE en nommant le champ', () => {
    const couche = creerCoucheElectrique({ sceneOrigin: ORIGINE });
    const refus = couche.poser([-7.6, 33.5]);
    expect(refus.ok).toBe(false);
    expect(couche.dernierRefus()?.champ).toBe('electrical.equipements.type');
    expect(couche.dernierRefus()?.message).toContain('onduleur');
    expect(couche.documentElectrique()).toBeNull();
  });
});

describe('CALX222 — « Armer la pose » puis un clic sur la carte pose l’organe armé', () => {
  it('clicCarte pose le type armé au point cliqué, puis désarme ; sans type armé le clic n’est pas consommé', () => {
    const couche = creerCoucheElectrique(ctxAtelier());
    expect(couche.clicCarte([-7.6002, 33.5001])).toBe(false);
    expect(couche.documentElectrique()).toBeNull();
    couche.armerPose('onduleur');
    expect(couche.clicCarte([-7.6002, 33.5001])).toBe(true);
    const eq = couche.documentElectrique()?.equipements ?? [];
    expect(eq).toHaveLength(1);
    expect(eq[0].type).toBe('onduleur');
    expect(eq[0].lng).toBe(-7.6002);
    expect(couche.typeArme()).toBeNull();
    expect(couche.clicCarte([-7.6003, 33.5002])).toBe(false);
    expect(couche.documentElectrique()?.equipements).toHaveLength(1);
  });
});

describe('CALX220 — déplacer, retirer, annuler', () => {
  function couchePosee() {
    const ctx: { electrical?: DocumentElectrique | null; sceneOrigin: [number, number] } = {
      sceneOrigin: ORIGINE,
    };
    const couche = creerCoucheElectrique(ctx);
    couche.armerPose('onduleur');
    couche.poser([-7.6002, 33.5001], { label: 'Onduleur 1' });
    return couche;
  }

  it('le glissé met à jour les coordonnées, et le marqueur suit', () => {
    const couche = couchePosee();
    const avant = couche.groupe.children[0].position.x;
    const deplace = couche.deplacer('eq1', [-7.5995, 33.5004]);
    expect(deplace.ok).toBe(true);
    const ecrit = couche.documentElectrique()!.equipements![0];
    expect(ecrit.lng).toBe(-7.5995);
    expect(ecrit.lat).toBe(33.5004);
    expect(couche.groupe.children[0].position.x).not.toBe(avant);
  });

  it('déplacer un organe inexistant est refusé en le nommant, sans rien changer', () => {
    const couche = couchePosee();
    const refus = couche.deplacer('eq42', [-7.6, 33.5]);
    expect(refus.ok).toBe(false);
    expect(couche.dernierRefus()?.message).toContain('eq42');
    expect(couche.documentElectrique()!.equipements).toHaveLength(1);
  });

  it('Suppr retire l’organe SÉLECTIONNÉ (la pose le sélectionne)', () => {
    const couche = couchePosee();
    expect(couche.selection()).toBe('eq1');
    expect(couche.retirer()).toBe(true);
    expect(couche.documentElectrique()!.equipements).toHaveLength(0);
    expect(couche.groupe.children).toHaveLength(0);
    expect(couche.retirer()).toBe(false);
  });

  it('Ctrl+Z restitue l’état d’AVANT le geste — pose, déplacement, retrait', () => {
    const couche = couchePosee();
    couche.deplacer('eq1', [-7.5995, 33.5004]);
    expect(couche.annuler()).toBe(true);
    expect(couche.documentElectrique()!.equipements![0].lng).toBe(-7.6002);
    // Un cran de plus : avant la pose, le plan ne portait AUCUNE couche
    // électrique — ce n'est pas une couche vide, c'est pas de couche.
    expect(couche.annuler()).toBe(true);
    expect(couche.documentElectrique()).toBeNull();
    expect(couche.groupe.children).toHaveLength(0);
    expect(couche.annuler()).toBe(false);
    // Et « rétablir » rejoue les deux gestes dans l'ordre.
    expect(couche.retablir()).toBe(true);
    expect(couche.documentElectrique()!.equipements).toHaveLength(1);
    expect(couche.retablir()).toBe(true);
    expect(couche.documentElectrique()!.equipements![0].lng).toBe(-7.5995);
  });

  it('un retrait annulé remet l’organe, à sa place', () => {
    const couche = couchePosee();
    couche.retirer('eq1');
    expect(couche.annuler()).toBe(true);
    const revenu = couche.documentElectrique()!.equipements![0];
    expect(revenu.id).toBe('eq1');
    expect(revenu.lng).toBe(-7.6002);
    expect(couche.groupe.children).toHaveLength(1);
  });
});

/* ============================================================================
   CALX223 — TRACER UN CHEMINEMENT DE CÂBLE PAR POINTS DE PASSAGE.
   ----------------------------------------------------------------------------
   Le tracé est la SOURCE de la longueur que le serveur publiera : un tronçon
   qui ne relie rien, ou qui n'a ni tracé ni longueur saisie, est REFUSÉ en
   nommant l'extrémité ou le champ fautif — jamais accepté puis oublié.

   Les cas du tracé et leur forme sont LUS dans l'échantillon committé
   `apps/calepinage/contract_samples/electrique_cheminements.json` (CALX202),
   comme ceux des équipements plus haut : pas de seconde fixture écrite ici.
   ========================================================================== */

const ECHANTILLON_CHEMINS = contrat('electrique_cheminements');
const DOC_CHEMINS = (ECHANTILLON_CHEMINS.exemple as { electrical: DocumentElectrique }).electrical;

describe('CALX223 — le tracé par points de passage', () => {
  /** Un atelier avec les huit organes de l'échantillon et un pan « z1 ». */
  function atelier() {
    const ctx = {
      electrical: { equipements: (DOC_HUIT.equipements ?? []).map((e) => ({ ...e })) } as DocumentElectrique,
      sceneOrigin: ORIGINE,
      areas: [{ id: 'z1' }],
      activeAreaId: 'z1',
    };
    return creerCoucheElectrique(ctx);
  }

  it('trois points tracés produisent un cheminement à trois points, origine `plan`', () => {
    const couche = atelier();
    expect(couche.demarrerCheminement({ cote: 'dc', de: 'z1' })).toBe(true);
    expect(couche.ajouterPointCheminement([-7.6001, 33.5003], 3.2)).toBe(1);
    couche.ajouterPointCheminement([-7.6002, 33.5003], 3.2);
    couche.ajouterPointCheminement([-7.6003, 33.5002], 3.2);
    expect(couche.pointsEnCours()).toHaveLength(3);
    const fin = couche.terminerCheminement('eq2');
    expect(fin.ok).toBe(true);
    const ecrit = couche.documentElectrique()!.cheminements![0];
    expect(ecrit.points).toHaveLength(3);
    expect(ecrit.origine).toBe('plan');
    expect(ecrit.de).toBe('z1');
    expect(ecrit.vers).toBe('eq2');
    expect(ecrit.cote).toBe('dc');
    // Le tracé est DESSINÉ : une polyligne de trois sommets dans le groupe.
    const ligne = couche.groupe.children.find((c) => c.userData.id === ecrit.id) as THREE.Line;
    expect(ligne).toBeTruthy();
    expect(ligne.geometry.getAttribute('position').count).toBe(3);
  });

  it('l’entrée écrite a la forme de l’échantillon de contrat CALX202', () => {
    const couche = atelier();
    couche.demarrerCheminement({ cote: 'dc', de: 'eq2' });
    couche.ajouterPointCheminement([-7.6003, 33.5002], 3.2);
    couche.ajouterPointCheminement([-7.6002, 33.5001], 3.2);
    couche.terminerCheminement('eq1');
    const ecrit = couche.documentElectrique()!.cheminements![0] as unknown as Record<string, unknown>;
    const modele = (DOC_CHEMINS.cheminements ?? []).find((c) => c.id === 'ch2') as unknown as Record<string, unknown>;
    const formeModele = formeDe(modele);
    for (const [cle, type] of Object.entries(formeDe(ecrit))) {
      expect(Object.keys(formeModele)).toContain(cle);
      expect(type).toBe(formeModele[cle]);
    }
    for (const cle of ['id', 'cote', 'de', 'vers', 'origine']) {
      expect(Object.keys(ecrit)).toContain(cle);
    }
    // Chaque point porte les mêmes clés que ceux du contrat.
    const pointModele = formeDe((modele.points as Record<string, unknown>[])[0]);
    const pointEcrit = formeDe((ecrit.points as Record<string, unknown>[])[0]);
    expect(Object.keys(pointEcrit)).toEqual(Object.keys(pointModele));
  });

  it('une extrémité qui n’atterrit pas sur un organe est REFUSÉE en la nommant', () => {
    const couche = atelier();
    couche.demarrerCheminement({ cote: 'dc', de: 'z1' });
    couche.ajouterPointCheminement([-7.6001, 33.5003]);
    couche.ajouterPointCheminement([-7.6003, 33.5002]);
    const refus = couche.terminerCheminement('eq9');
    expect(refus.ok).toBe(false);
    expect(couche.dernierRefus()?.champ).toBe('electrical.cheminements.vers');
    expect(couche.dernierRefus()?.message).toContain('eq9');
    expect(couche.documentElectrique()!.cheminements ?? []).toHaveLength(0);
  });

  it('un départ qui ne résout ni un organe ni un pan est refusé avant le premier point', () => {
    const couche = atelier();
    const refus = couche.demarrerCheminement({ cote: 'dc', de: 'z7' });
    expect(refus).not.toBe(true);
    expect(couche.dernierRefus()?.champ).toBe('electrical.cheminements.de');
    expect(couche.dernierRefus()?.message).toContain('z7');
    expect(couche.ajouterPointCheminement([-7.6, 33.5])).toBe(0);
  });

  it('un tracé d’UN SEUL point est refusé : il n’a aucune longueur mesurable', () => {
    const couche = atelier();
    couche.demarrerCheminement({ cote: 'ac', de: 'eq1' });
    couche.ajouterPointCheminement([-7.6002, 33.5001]);
    const refus = couche.terminerCheminement('eq4');
    expect(refus.ok).toBe(false);
    expect(couche.dernierRefus()?.champ).toBe('electrical.cheminements.points');
    expect(couche.dernierRefus()?.message).toContain('deux points');
  });

  it('Échap abandonne le tracé en cours sans rien écrire', () => {
    const couche = atelier();
    couche.demarrerCheminement({ cote: 'dc', de: 'z1' });
    couche.ajouterPointCheminement([-7.6001, 33.5003]);
    expect(couche.abandonnerCheminement()).toBe(true);
    expect(couche.pointsEnCours()).toEqual([]);
    expect(couche.documentElectrique()!.cheminements ?? []).toHaveLength(0);
    expect(couche.abandonnerCheminement()).toBe(false);
  });

  it('la pile d’annulation couvre le geste', () => {
    const couche = atelier();
    couche.demarrerCheminement({ cote: 'dc', de: 'z1' });
    couche.ajouterPointCheminement([-7.6001, 33.5003]);
    couche.ajouterPointCheminement([-7.6003, 33.5002]);
    couche.terminerCheminement('eq2');
    expect(couche.documentElectrique()!.cheminements).toHaveLength(1);
    expect(couche.annuler()).toBe(true);
    expect(couche.documentElectrique()!.cheminements ?? []).toHaveLength(0);
    expect(couche.retablir()).toBe(true);
    expect(couche.documentElectrique()!.cheminements).toHaveLength(1);
  });
});

describe('CALX223 — le tronçon que le plan ne porte pas se SAISIT', () => {
  function atelier() {
    return creerCoucheElectrique({
      electrical: { equipements: (DOC_HUIT.equipements ?? []).map((e) => ({ ...e })) } as DocumentElectrique,
      sceneOrigin: ORIGINE,
      areas: [{ id: 'z1' }],
    });
  }

  it('une descente verticale saisie porte `origine: saisie` et aucun tracé', () => {
    const couche = atelier();
    const fait = couche.saisirCheminement({ cote: 'ac', de: 'eq4', vers: 'eq7', longueurM: 12 });
    expect(fait.ok).toBe(true);
    const ecrit = couche.documentElectrique()!.cheminements![0];
    expect(ecrit.origine).toBe('saisie');
    expect(ecrit.longueurSaisieM).toBe(12);
    expect(ecrit.points).toEqual([]);
    // Rien à dessiner : le plan ne porte pas ce tronçon, et rien n'est deviné.
    expect(couche.groupe.children.find((c) => c.userData.id === ecrit.id)).toBeUndefined();
  });

  it('sans longueur saisie, le tronçon est refusé en nommant le champ', () => {
    const couche = atelier();
    const refus = couche.saisirCheminement({ cote: 'ac', de: 'eq4', vers: 'eq7', longueurM: 0 });
    expect(refus.ok).toBe(false);
    expect(couche.dernierRefus()?.champ).toBe('electrical.cheminements.longueurSaisieM');
    expect(couche.documentElectrique()!.cheminements ?? []).toHaveLength(0);
  });

  it('l’échantillon de contrat committé se relit sans un seul avertissement', () => {
    const couche = creerCoucheElectrique({
      electrical: {
        equipements: (DOC_HUIT.equipements ?? []).map((e) => ({ ...e })),
        cheminements: (DOC_CHEMINS.cheminements ?? []).map((c) => ({ ...c })),
      },
      sceneOrigin: ORIGINE,
      areas: [{ id: 'z1' }],
    });
    expect(couche.avertissements()).toEqual([]);
    // Huit marqueurs + les quatre cheminements TRACÉS (`ch4` est saisi : aucun tracé).
    expect(couche.groupe.children).toHaveLength(12);
  });
});

/* ============================================================================
   CALX221 — LE CALQUE « ÉLECTRIQUE », UN CALQUE COMME LES AUTRES.
   ----------------------------------------------------------------------------
   Même porte que les dix calques de la carte (`setLayerState(id, état)`), même
   règle : il n'est PROPOSÉ que s'il existe — un plan sans couche électrique n'a
   rien à allumer.
   ========================================================================== */

describe('CALX221 — le calque électrique', () => {
  it('l’identifiant est déclaré UNE seule fois, et la couche le porte', () => {
    expect(ID_CALQUE_ELECTRIQUE).toBe('electrique');
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    expect(couche.idCalque).toBe(ID_CALQUE_ELECTRIQUE);
    expect(couche.groupe.name).toBe(ID_CALQUE_ELECTRIQUE);
    // ACAL342 — RÉÉCRIT sans lecture du source : le calque proposé par la couche (celui que
    // l'ERP pilote) EST l'identifiant exporté, et lui seul.
    expect(couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: true })).toBe(true);
    expect(couche.setLayerState(`${ID_CALQUE_ELECTRIQUE}-autre`, { visible: true })).toBe(false);
  });

  it('`setLayerState` masque le groupe et rend `true`', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    expect(couche.groupe.visible).toBe(true);
    expect(couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: false })).toBe(true);
    expect(couche.groupe.visible).toBe(false);
    expect(couche.etatCalque().visible).toBe(false);
    expect(couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: true })).toBe(true);
    expect(couche.groupe.visible).toBe(true);
  });

  it('l’opacité descend sur les matériaux du SEUL groupe électrique', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: true, opacite: 0.4 });
    expect(couche.etatCalque().opacite).toBe(0.4);
    const maillage = couche.groupe.children[0] as THREE.Mesh;
    expect((maillage.material as THREE.Material & { opacity: number }).opacity).toBe(0.4);
    // L'état survit à un rafraîchissement (un geste reconstruit le groupe).
    couche.rafraichir();
    expect(couche.groupe.visible).toBe(true);
    const apres = couche.groupe.children[0] as THREE.Mesh;
    expect((apres.material as THREE.Material & { opacity: number }).opacity).toBe(0.4);
  });

  it('un AUTRE identifiant de calque n’est pas le sien : refus net, rien ne bouge', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    expect(couche.setLayerState('zones', { visible: false })).toBe(false);
    expect(couche.setLayerState('panneaux', { visible: false })).toBe(false);
    expect(couche.groupe.visible).toBe(true);
  });

  it('le calque n’est disponible QUE si le document porte une couche électrique', () => {
    const ctx: { electrical?: DocumentElectrique | null; sceneOrigin: [number, number] } = {
      sceneOrigin: ORIGINE,
    };
    const couche = creerCoucheElectrique(ctx);
    expect(couche.calqueDisponible()).toBe(false);
    couche.armerPose('onduleur');
    couche.poser([-7.6002, 33.5001]);
    expect(couche.calqueDisponible()).toBe(true);
    // Annuler la première pose retire la couche : le calque disparaît avec elle.
    couche.annuler();
    expect(couche.calqueDisponible()).toBe(false);
  });
});

describe('T4-X7-015 (calque Électrique) — une seule case pour tout l’électrique de la scène', () => {
  const chainesServies = { labelByModule: new Map([['PAN-A#1', 'chaîne 1'], ['PAN-A#2', 'chaîne 1']]) };

  it('des chaînes formées SANS organe posé suffisent à proposer le calque ; pas de chaîne, pas d’organe : rien', () => {
    const avec = creerCoucheElectrique({ sceneOrigin: ORIGINE, affectationColoration: chainesServies });
    expect(avec.documentElectrique()).toBeNull();
    expect(avec.calqueDisponible()).toBe(true);
    for (const rien of [undefined, null, { labelByModule: new Map() }]) {
      expect(creerCoucheElectrique({ sceneOrigin: ORIGINE, affectationColoration: rien }).calqueDisponible()).toBe(false);
    }
    expect(creerCoucheElectrique({ sceneOrigin: ORIGINE }).calqueDisponible()).toBe(false); // estimateur public : aucun contexte ERP
  });

  it('la case est UN seul état : le groupe, l’état relu par la scène et le crochet de la scène bougent ensemble', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    expect(calqueElectriqueVisible(couche.groupe)).toBe(true);
    let appels = 0;
    couche.groupe.userData.siEtatChange = () => { appels += 1; };
    couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: false });
    expect([calqueElectriqueVisible(couche.groupe), couche.groupe.visible, couche.etatCalque().visible, appels]).toEqual([false, false, false, 1]);
    couche.rafraichir(); // un geste reconstruit le groupe : la case décochée le reste
    expect([calqueElectriqueVisible(couche.groupe), couche.groupe.visible]).toEqual([false, false]);
    couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: true });
    expect([calqueElectriqueVisible(couche.groupe), couche.groupe.visible, appels]).toEqual([true, true, 2]);
    couche.setLayerState('zones', { visible: false }); // le calque d’un autre : ni l’état ni la scène ne bougent
    expect([calqueElectriqueVisible(couche.groupe), appels]).toEqual([true, 2]);
  });

  it('préférence de VUE : masquer la couche n’écrit rien au document (octet-identique), couche posée ou non', () => {
    const avant = JSON.stringify(creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE }).ecrireDansDocument({}));
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: false, opacite: 0.3 });
    expect(JSON.stringify(couche.ecrireDansDocument({}))).toBe(avant);
    const seule = creerCoucheElectrique({ sceneOrigin: ORIGINE, affectationColoration: chainesServies });
    seule.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: false });
    expect(seule.ecrireDansDocument({ a: 1 })).toEqual({ a: 1 }); // des chaînes seules : toujours pas de clé `electrical`
    expect(seule.documentElectrique()).toBeNull();
  });

  it('sans couche (estimateur public, page client) : rien n’est masqué et le branchement ne fait que rattacher', () => {
    expect(calqueElectriqueVisible(null)).toBe(true);
    expect(calqueElectriqueVisible({ userData: {} })).toBe(true);
    const journal: string[] = [];
    brancherCalqueElectrique(null, () => journal.push('rattache'), () => journal.push('apres'));
    expect(journal).toEqual(['rattache']);
  });

  it('branché : rattache aussitôt ; à chaque changement de la case, rattache puis redit les chaînes', () => {
    const couche = creerCoucheElectrique({ electrical: DOC_HUIT, sceneOrigin: ORIGINE });
    const journal: string[] = [];
    brancherCalqueElectrique(couche.groupe, () => journal.push('rattache'), () => journal.push('chaines'));
    expect(journal).toEqual(['rattache']);
    couche.setLayerState(ID_CALQUE_ELECTRIQUE, { visible: false });
    expect(journal).toEqual(['rattache', 'rattache', 'chaines']);
  });
});

describe('CALX220 / ACAL26 — l’attache dans le constructeur passe par le sérialiseur câblé', () => {
  // ACAL26 — réécrit : l'ancien bloc lisait roof-tool-pro11.ts par readFileSync et
  // cherchait des chaînes dans le SOURCE ; il restait vert alors que le wrapper perdait la
  // couche électrique. Ce bloc rejoue le comportement : document → boot → sérialiseur.
  it('document semé → hydrateFromDevis → appliquerHydratationAuCtx → sérialiseur câblé : `electrical` identique', () => {
    const documentSeme = {
      version: 2, pin: null, outline: [], billKwh: null, activeAreaId: 'z1',
      zones: [{
        id: 'z1', label: 'Pan', vertices: [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]], obstacles: [],
        roofType: 'flat', pitchDeg: 10, facingAzimuthDeg: 180, facingManual: false, neededPanels: 0, neededAuto: true,
      }],
      electrical: DOC_HUIT,
    } as unknown as SerializedLayout;
    const h = hydrateFromDevis({ id: 7, geometrie: { roof_layout: documentSeme }, cibleVendue: false });
    const ctx = ctxAtelier();
    appliquerHydratationAuCtx(ctx, h);
    const couche = creerCoucheElectrique(ctx);
    // Le calque relu est proposé dès l'ouverture (la liste « Équipements électriques »).
    expect(couche.calqueDisponible()).toBe(true);
    const sortie = serialiserDocumentAtelier(ctx, null, etatConstructeur(couche, { devisId: 7, panelWatt: null, scenario: null }));
    // Le document relu passe par l'UNIQUE lecteur (`lireCoucheElectrique`) : ce qui en
    // sort est ce qui repart, sans perte ni ajout.
    const lu = lireCoucheElectrique({ electrical: DOC_HUIT });
    expect(lu.equipements.length).toBeGreaterThan(0);
    expect(sortie.electrical).toEqual({ equipements: lu.equipements, cheminements: lu.cheminements });
  });

  it('les DEUX branches de la meta (devis et lead) portent la couche ; sans couche, aucune clé', () => {
    const ctx = ctxAtelier(DOC_VIDE);
    const couche = creerCoucheElectrique(ctx);
    couche.armerPose('onduleur');
    couche.poser([-7.6002, 33.5001]);
    const lead = serialiserDocumentAtelier(ctx, null, etatConstructeur(couche, null));
    const devis = serialiserDocumentAtelier(ctx, null, etatConstructeur(couche, { devisId: 7, panelWatt: null, scenario: null }));
    expect(lead.electrical?.equipements).toHaveLength(1);
    expect(devis.electrical?.equipements).toHaveLength(1);
    const sansCouche = serialiserDocumentAtelier(ctx, null, { ...etatConstructeur(couche, null), coucheElectrique: null });
    expect('electrical' in sansCouche).toBe(false);
  });
});

/* ACAL472 — proposer le tracé d'un câble le long des rangées et de la rive. Géométrie en
   mètres ENU autour de ORIGINE : toit 20 × 10 m, une rangée de modules sur l'axe y = 5
   (x de 2 à 18), azimut 180° (rangées le long de l'est). */
describe('ACAL472 — cheminement proposé (plus court chemin rangées + rive)', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137; // le rayon de lib/geo (WGS84_RADIUS)
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const RIVE: [number, number][] = [[0, 0], [20, 0], [20, 10], [0, 10]];
  const plan = (rive = RIVE) => ({
    pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: rive },
    grid: { rowWidthM: 2, panels: [3, 5, 7, 9, 11, 13, 15, 17].map((cx) => ({ cx, cy: 5 })) },
  });
  const organe = (id: string, e: number, n: number): EquipementElectrique => {
    const [lng, lat] = lngLat(e, n);
    return { ...(DOC_HUIT.equipements![0] as EquipementElectrique), id, lng, lat };
  };
  const atelier = (a: [number, number], b: [number, number], rive = RIVE) => creerCoucheElectrique({
    electrical: { equipements: [organe('eqA', ...a), organe('eqB', ...b)] },
    sceneOrigin: ORIGINE,
    areas: [{ id: 'z1', renderPlan: plan(rive) }],
    activeAreaId: 'z1',
  });
  const enu = (p: { lng: number; lat: number }): [number, number] => [(p.lng - ORIGINE[0]) * M * COS, (p.lat - ORIGINE[1]) * M];
  const surRive = ([x, y]: [number, number]) => Math.min(Math.abs(x), Math.abs(x - 20), Math.abs(y), Math.abs(y - 10)) < 1e-6;

  it('suit l\'axe de la rangée plutôt que de contourner : tous les points sont sur la rangée ou la rive', () => {
    const couche = atelier([1, 5], [19, 5]);
    const res = couche.proposerCheminement({ cote: 'dc', de: 'eqA', vers: 'eqB' });
    expect(res.ok).toBe(true);
    const ch = couche.documentElectrique()!.cheminements![0];
    expect(ch.origine).toBe('plan');
    const pts = ch.points!.map(enu);
    expect(pts.length).toBeGreaterThan(2); // jamais une droite à deux points
    for (const p of pts) expect(Math.abs(p[1] - 5) < 1e-6 || surRive(p)).toBe(true);
    expect(pts.some(([x]) => Math.abs(x - 18) < 1e-6)).toBe(true); // passe par le bout de la rangée
  });

  it('contourne par la rive quand aucune rangée ne passe', () => {
    const couche = atelier([0.5, 3], [0.5, 7]);
    expect(couche.proposerCheminement({ cote: 'ac', de: 'eqA', vers: 'eqB' }).ok).toBe(true);
    const pts = couche.documentElectrique()!.cheminements![0].points!.map(enu);
    expect(pts.length).toBeGreaterThan(2);
    expect(pts.slice(1, -1).every(([x]) => Math.abs(x) < 1e-6)).toBe(true); // longe la rive ouest
  });

  it('re-proposable (un seul tracé par liaison) et supprimable ; chemin impossible nommé', () => {
    const couche = atelier([1, 5], [19, 5]);
    couche.proposerCheminement({ cote: 'dc', de: 'eqA', vers: 'eqB' });
    couche.proposerCheminement({ cote: 'dc', de: 'eqA', vers: 'eqB' });
    const liste = couche.documentElectrique()!.cheminements!;
    expect(liste).toHaveLength(1);
    expect(couche.retirer(liste[0].id)).toBe(true);
    expect(couche.documentElectrique()!.cheminements).toHaveLength(0);

    const sansRive = atelier([1, 5], [19, 5], []).proposerCheminement({ cote: 'dc', de: 'eqA', vers: 'eqB' });
    expect(sansRive.ok).toBe(false);
    expect((sansRive as { message?: string }).message).toMatch(/Aucune rive de toit exploitable/);
    const sansPan = creerCoucheElectrique({ electrical: { equipements: [] }, sceneOrigin: ORIGINE, areas: [{ id: 'z1' }] })
      .proposerCheminement({ cote: 'dc', de: 'z1', vers: 'z1' });
    expect(sansPan.ok).toBe(false);
  });
});

/* ACAL1317 (D-ACAL-70) — l'onduleur se pose et se DÉPLACE depuis l'étape Électrique ; son tracé PROPOSÉ suit, un tracé
   dessiné à la main n'est jamais remplacé. Même toit que ACAL472 : 20 × 10 m, une rangée sur y = 5. */
describe('ACAL1317 — déplacer l’onduleur, le tracé suit', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137;
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const enu = (p: { lng: number; lat: number }): [number, number] => [(p.lng - ORIGINE[0]) * M * COS, (p.lat - ORIGINE[1]) * M];
  const RIVE: [number, number][] = [[0, 0], [20, 0], [20, 10], [0, 10]];
  const plan = {
    pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: RIVE },
    grid: { rowWidthM: 2, panels: [3, 5, 7, 9, 11, 13, 15, 17].map((cx) => ({ cx, cy: 5 })) },
  };
  const onduleur = (e: number, n: number): EquipementElectrique => {
    const [lng, lat] = lngLat(e, n);
    return { id: 'eqA', type: 'onduleur', label: 'Onduleur 1', lng, lat, source: 'saisie' };
  };
  const atelier = (electrical: DocumentElectrique | null = { equipements: [onduleur(19, 5)] }) => creerCoucheElectrique({
    electrical, sceneOrigin: ORIGINE, areas: [{ id: 'z1', renderPlan: plan }], activeAreaId: 'z1',
  });
  const traces = (c: ReturnType<typeof atelier>) => c.documentElectrique()?.cheminements ?? [];
  const pres = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-6;

  it('« Déplacer » armé : le clic sur la carte DÉPLACE l’onduleur, n’en ajoute pas, puis désarme', () => {
    const couche = atelier();
    expect(couche.armerDeplacement('eqX')).toBe(false); // organe absent : rien d'armé
    expect(couche.armerDeplacement('eqA')).toBe(true);
    expect(couche.deplacementArme()).toBe('eqA');
    expect(couche.clicCarte(lngLat(1, 5))).toBe(true);
    const eq = couche.documentElectrique()!.equipements!;
    expect(eq).toHaveLength(1);
    expect(pres(enu(eq[0]), [1, 5])).toBe(true);
    expect(couche.deplacementArme()).toBeNull();
    expect(couche.clicCarte(lngLat(3, 5))).toBe(false); // désarmé : le clic suivant n'est plus consommé
  });

  it('le tracé DC pan → onduleur est proposé au premier déplacement, puis SUIT l’onduleur (un seul tracé)', () => {
    const couche = atelier();
    couche.armerDeplacement('eqA');
    couche.clicCarte(lngLat(19, 5));
    expect(traces(couche)).toHaveLength(1);
    const avant = traces(couche)[0];
    expect([avant.cote, avant.de, avant.vers, avant.origine]).toEqual(['dc', 'z1', 'eqA', 'plan']);
    expect(couche.etatTraces('eqA').proposes).toEqual([avant.id]);
    couche.armerDeplacement('eqA');
    couche.clicCarte(lngLat(1, 5));
    const apres = traces(couche);
    expect(apres).toHaveLength(1);
    const bout = apres[0].points![apres[0].points!.length - 1];
    expect(pres(enu(bout), [1, 5])).toBe(true); // le tracé aboutit à la NOUVELLE position
    expect(couche.etatTraces('eqA')).toEqual({ proposes: [apres[0].id], autres: [], decales: [], pansSansTrace: [] });
  });

  it('un déplacement et son tracé sont UN cran d’annulation', () => {
    const couche = atelier();
    couche.armerDeplacement('eqA');
    couche.clicCarte(lngLat(1, 5));
    expect(couche.annuler()).toBe(true);
    expect(pres(enu(couche.documentElectrique()!.equipements![0]), [19, 5])).toBe(true);
    expect(traces(couche)).toHaveLength(0);
    expect(couche.retablir()).toBe(true);
    expect(traces(couche)).toHaveLength(1);
  });

  it('les flèches poussent l’onduleur d’un pas nommé, le tracé suit', () => {
    const couche = atelier();
    const r = couche.pousser('eqA', 0, PAS_DEPLACEMENT_ORGANE_M);
    expect(r.ok).toBe(true);
    const [e, n] = enu(couche.documentElectrique()!.equipements![0]);
    expect(Math.abs(e - 19)).toBeLessThan(1e-6);
    expect(Math.abs(n - (5 + PAS_DEPLACEMENT_ORGANE_M))).toBeLessThan(1e-6);
    expect(couche.etatTraces('eqA').proposes).toHaveLength(1);
    expect(couche.pousser('eqX', 1, 0).ok).toBe(false);
  });

  it('un tracé NON reconnu (ici tracé point par point) n’est jamais remplacé ; il est dit décalé quand il n’aboutit plus', () => {
    const couche = atelier();
    expect(couche.demarrerCheminement({ cote: 'dc', de: 'z1' })).toBe(true);
    couche.ajouterPointCheminement(lngLat(10, 5));
    couche.ajouterPointCheminement(lngLat(19, 5));
    expect(couche.terminerCheminement('eqA').ok).toBe(true);
    const main = JSON.stringify(traces(couche));
    expect(couche.etatTraces('eqA')).toEqual({ proposes: [], autres: ['ch1'], decales: [], pansSansTrace: [] });
    couche.armerDeplacement('eqA');
    couche.clicCarte(lngLat(1, 5));
    expect(JSON.stringify(traces(couche))).toBe(main); // ni remplacé, ni doublé d'un tracé proposé
    expect(couche.etatTraces('eqA').decales).toEqual(['ch1']);
  });

  it('« Placer » avec suivi : une pose = l’onduleur + son tracé, en un cran ; retirer emporte le tracé proposé seul', () => {
    const couche = atelier(null);
    couche.armerPose('onduleur', { suivreTrace: true });
    expect(couche.clicCarte(lngLat(19, 5))).toBe(true);
    expect(couche.documentElectrique()!.equipements).toHaveLength(1);
    expect(traces(couche)).toHaveLength(1);
    expect(couche.typeArme()).toBeNull();
    expect(couche.annuler()).toBe(true);
    expect(couche.documentElectrique()).toBeNull();
    couche.retablir();
    const id = couche.documentElectrique()!.equipements![0].id;
    couche.saisirCheminement({ cote: 'ac', de: id, vers: 'z1', longueurM: 12 });
    const r = couche.retirerAvecTraces(id);
    expect(r).toEqual({ ok: true, tracesGardees: ['ch2'] });
    expect(couche.documentElectrique()!.equipements).toHaveLength(0);
    expect(traces(couche).map((c) => c.id)).toEqual(['ch2']);
  });

  it('l’écran est prévenu UNE fois par geste, le geste déjà désarmé (pose comme déplacement)', () => {
    const couche = atelier(null);
    const vus: Array<[string | null, string | null, number]> = [];
    couche.ecouter(() => vus.push([couche.typeArme(), couche.deplacementArme(), couche.documentElectrique()?.equipements?.length ?? 0]));
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(19, 5));
    expect(vus).toEqual([[null, null, 1]]);
    couche.armerDeplacement('eq1');
    couche.clicCarte(lngLat(1, 5));
    expect(vus).toHaveLength(2);
    expect(vus[1]).toEqual([null, null, 1]);
  });

  it('sans geste, rien n’est écrit : le document repart identique octet pour octet', () => {
    const source = { equipements: [onduleur(19, 5)], cheminements: [] };
    const avant = JSON.stringify(source);
    const couche = atelier(JSON.parse(avant));
    const appels: number[] = [];
    const fin = couche.ecouter(() => appels.push(1));
    couche.etatTraces('eqA');
    couche.armerDeplacement('eqA');
    couche.armerDeplacement(null);
    couche.rafraichir();
    fin();
    expect(JSON.stringify(couche.ecrireDansDocument({}).electrical)).toBe(avant);
    expect(appels).toHaveLength(1); // le rafraîchissement prévient l'écran, sans rien écrire
  });
});

/* ACAL1317 (revue) — le tracé proposé se RECONNAÎT après une retouche du toit (sommets alignés retirés, au
   centimètre), chaque pan à modules reçoit son tracé, et la couche refuse elle-même d'écrire en lecture seule. */
describe('ACAL1317 — tracé reconnu après retouche, un tracé par pan, lecture seule', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137;
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const enu = (p: { lng: number; lat: number }): [number, number] => [(p.lng - ORIGINE[0]) * M * COS, (p.lat - ORIGINE[1]) * M];
  /** Le cas du relecteur : toit 20 × 12 m, trois rangées (y = 3, 6, 9) de huit modules (cx 3 à 17). */
  const modules = (premier: number, dernier: number) => [3, 6, 9].flatMap((cy) => {
    const out = [];
    for (let cx = premier; cx <= dernier; cx += 2) out.push({ cx, cy });
    return out;
  });
  const pan = (id: string, ring: [number, number][], panels = modules(3, 17)) => ({
    id, renderPlan: { pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: ring }, grid: { rowWidthM: 2, panels } },
  });
  const TOIT: [number, number][] = [[0, 0], [20, 0], [20, 12], [0, 12]];
  const atelier = (areas = [pan('z1', TOIT)]) => {
    const ctx = { electrical: null as DocumentElectrique | null, sceneOrigin: ORIGINE, areas, activeAreaId: 'z1' };
    const couche = creerCoucheElectrique(ctx);
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(20, 2));
    return { ctx, couche };
  };
  const traces = (c: ReturnType<typeof creerCoucheElectrique>) => c.documentElectrique()?.cheminements ?? [];

  it('un module retiré au bout de chaque rangée ajoute un sommet ALIGNÉ : le tracé reste reconnu et suit le déplacement', () => {
    const { ctx, couche } = atelier();
    const id = traces(couche)[0].id;
    ctx.areas[0].renderPlan.grid.panels = modules(5, 15); // la retouche du relecteur
    expect(couche.etatTraces('eq1')).toEqual({ proposes: [id], autres: [], decales: [], pansSansTrace: [] });
    couche.armerDeplacement('eq1');
    couche.clicCarte(lngLat(19, 1));
    expect(traces(couche)).toHaveLength(1);
    const pts = traces(couche)[0].points!;
    const bout = enu(pts[pts.length - 1]);
    expect(Math.hypot(bout[0] - 19, bout[1] - 1)).toBeLessThan(1e-6);
    expect(couche.etatTraces('eq1').proposes).toHaveLength(1);
  });

  it('un toit qui change le TRAJET : le tracé n’est plus reconnu, n’est pas remplacé, et se dit décalé après un déplacement', () => {
    const { ctx, couche } = atelier();
    const avant = JSON.stringify(traces(couche));
    ctx.areas[0].renderPlan.pack.ringENU = [[0, -4], [20, -4], [20, 12], [0, 12]];
    expect(couche.etatTraces('eq1')).toEqual({ proposes: [], autres: ['ch1'], decales: [], pansSansTrace: [] });
    couche.armerDeplacement('eq1');
    couche.clicCarte(lngLat(19, 1));
    expect(JSON.stringify(traces(couche))).toBe(avant);
    expect(couche.etatTraces('eq1').decales).toEqual(['ch1']);
  });

  it('deux pans à modules : un tracé DC par pan vers l’onduleur ; un pan sans module n’en reçoit pas', () => {
    const { couche } = atelier([pan('z1', TOIT), pan('z2', [[0, 14], [20, 14], [20, 26], [0, 26]], []), pan('z3', [[22, 0], [40, 0], [40, 12], [22, 12]])]);
    expect(traces(couche).map((c) => [c.cote, c.de, c.vers])).toEqual([['dc', 'z1', 'eq1'], ['dc', 'z3', 'eq1']]);
    expect(couche.etatTraces('eq1').pansSansTrace).toEqual([]);
    expect(couche.retirer('ch2')).toBe(true);
    expect(couche.etatTraces('eq1').pansSansTrace).toEqual(['z3']); // tracé partiel : l'écran le dit
  });

  it('lecture seule : la COUCHE désarme et refuse pose, déplacement, retrait, tracé et annulation', () => {
    const { couche } = atelier();
    const avant = JSON.stringify(couche.documentElectrique());
    couche.armerDeplacement('eq1');
    couche.definirLectureSeule(true);
    expect(couche.deplacementArme()).toBeNull();
    expect(couche.clicCarte(lngLat(1, 5))).toBe(false);
    expect(couche.armerPose('onduleur')).toBe(false);
    expect(couche.armerDeplacement('eq1')).toBe(false);
    expect(couche.pousser('eq1', 1, 0).ok).toBe(false);
    expect(couche.deplacer('eq1', lngLat(1, 5)).ok).toBe(false);
    expect(couche.retirerAvecTraces('eq1').ok).toBe(false);
    expect(couche.retirer('eq1')).toBe(false);
    expect(couche.proposerCheminement({ cote: 'dc', de: 'z1', vers: 'eq1' }).ok).toBe(false);
    expect(couche.annuler()).toBe(false);
    expect(couche.dernierRefus()?.message).toMatch(/lecture seule/);
    expect(JSON.stringify(couche.documentElectrique())).toBe(avant);
    couche.definirLectureSeule(false);
    expect(couche.pousser('eq1', 1, 0).ok).toBe(true);
  });
});

/* ACAL1317 (revue 2) — deux onduleurs : un pan servi par l'un n'envoie pas un second câble à l'autre. */
describe('ACAL1317 — deux onduleurs, un câble par pan', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137;
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const enu = (p: { lng: number; lat: number }): [number, number] => [(p.lng - ORIGINE[0]) * M * COS, (p.lat - ORIGINE[1]) * M];
  const pan = (id: string, ring: [number, number][]) => ({
    id, renderPlan: { pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: ring }, grid: { rowWidthM: 2, panels: [3, 5, 7].map((cx) => ({ cx, cy: 6 })) } },
  });
  it('z1 câblé à l’onduleur 1 : poser l’onduleur 2 n’ajoute aucun câble depuis z1 ; déplacer l’onduleur 1 ne fait suivre que SON tracé', () => {
    const couche = creerCoucheElectrique({ electrical: null, sceneOrigin: ORIGINE, areas: [pan('z1', [[0, 0], [20, 0], [20, 12], [0, 12]])], activeAreaId: 'z1' });
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(20, 2));
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(0, 2));
    const liaisons = () => (couche.documentElectrique()!.cheminements ?? []).map((c) => [c.de, c.vers]);
    expect(couche.documentElectrique()!.equipements!.map((e) => e.id)).toEqual(['eq1', 'eq2']);
    expect(liaisons()).toEqual([['z1', 'eq1']]);
    couche.armerDeplacement('eq1');
    couche.clicCarte(lngLat(19, 1));
    expect(liaisons()).toEqual([['z1', 'eq1']]);
    const pts = couche.documentElectrique()!.cheminements![0].points!;
    const bout = enu(pts[pts.length - 1]);
    expect(Math.hypot(bout[0] - 19, bout[1] - 1)).toBeLessThan(1e-6);
    expect(couche.etatTraces('eq1').pansSansTrace).toEqual([]);
    expect(couche.etatTraces('eq2').pansSansTrace).toEqual([]);
  });
});

describe('ACAL1317 — un pan « existant » n’envoie aucun câble neuf', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137;
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const pan = (id: string, ring: [number, number][], existant = false) => ({
    id, existant, renderPlan: { pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: ring }, grid: { rowWidthM: 2, panels: [3, 5, 7].map((cx) => ({ cx, cy: 6 })) } },
  });
  it('la pose ne trace que depuis les pans vendus ; le pan existant n’est pas compté « sans tracé »', () => {
    const couche = creerCoucheElectrique({
      electrical: null, sceneOrigin: ORIGINE, activeAreaId: 'z1',
      areas: [pan('z1', [[0, 0], [20, 0], [20, 12], [0, 12]]), pan('z2', [[22, 0], [40, 0], [40, 12], [22, 12]], true)],
    });
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(20, 2));
    expect((couche.documentElectrique()!.cheminements ?? []).map((c) => c.de)).toEqual(['z1']);
    expect(couche.etatTraces('eq1').pansSansTrace).toEqual([]);
  });
});

describe('ACAL1317 — un pan refusé reste dit, même si le suivant réussit', () => {
  const COS = Math.cos((ORIGINE[1] * Math.PI) / 180);
  const M = (Math.PI / 180) * 6378137;
  const lngLat = (e: number, n: number): [number, number] => [ORIGINE[0] + e / (M * COS), ORIGINE[1] + n / M];
  const pan = (id: string, ring: [number, number][]) => ({
    id, renderPlan: { pack: { origin: ORIGINE, azimuthDeg: 180, ringENU: ring }, grid: { rowWidthM: 2, panels: [3, 5, 7].map((cx) => ({ cx, cy: 6 })) } },
  });
  const atelier = () => creerCoucheElectrique({
    electrical: null, sceneOrigin: ORIGINE, activeAreaId: 'z1',
    areas: [pan('z1', []), pan('z3', [[22, 0], [40, 0], [40, 12], [22, 12]])], // z1 sans rive : son tracé est refusé
  });
  it('toucher de la carte : z1 refusé puis z3 tracé ⇒ le refus de z1 est le dernier refus du geste', () => {
    const couche = atelier();
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(20, 2));
    expect((couche.documentElectrique()!.cheminements ?? []).map((c) => c.de)).toEqual(['z3']);
    expect(couche.dernierRefus()?.message).toMatch(/Aucune rive de toit exploitable/);
  });
  it('flèches : même refus, rendu par `refusTrace` ET gardé par `dernierRefus`', () => {
    const couche = atelier();
    couche.armerPose('onduleur', { suivreTrace: true });
    couche.clicCarte(lngLat(20, 2));
    const r = couche.pousser('eq1', 0, 0.25);
    expect(r.ok && r.refusTrace?.message).toMatch(/Aucune rive de toit exploitable/);
    expect(couche.dernierRefus()?.message).toMatch(/Aucune rive de toit exploitable/);
  });
});
