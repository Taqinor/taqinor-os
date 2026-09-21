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
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';
import * as THREE from 'three';
import {
  ID_CALQUE_ELECTRIQUE,
  TYPES_EQUIPEMENT,
  DESSIN_PAR_TYPE,
  NOM_TYPE_FR,
  creerCoucheElectrique,
  creerMarqueur,
  estTypeEquipement,
  lireCoucheElectrique,
  versScene,
  type DocumentElectrique,
  type EquipementElectrique,
  type TypeEquipement,
} from './electrique3d';

// ───────────────────────────────────────────── l'échantillon de contrat committé

function racineDepot(): string {
  let dossier = resolve(process.cwd());
  for (let i = 0; i < 6; i += 1) {
    if (existsSync(join(dossier, 'backend', 'django_core'))) return dossier;
    dossier = dirname(dossier);
  }
  throw new Error(`Racine du dépôt introuvable depuis ${process.cwd()}`);
}

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
  it('poser écrit une entrée dans `electrical.equipements[]`, et `serializeLayout` la porte', () => {
    const ctx: { electrical?: DocumentElectrique | null; sceneOrigin: [number, number] } = {
      sceneOrigin: ORIGINE,
    };
    const couche = creerCoucheElectrique(ctx);
    expect(couche.documentElectrique()).toBeNull();
    couche.armerPose('onduleur');
    const pose = couche.poser([-7.6002, 33.5001]);
    expect(pose.ok).toBe(true);
    const doc = couche.documentElectrique();
    expect(doc?.equipements).toHaveLength(1);
    expect(doc?.equipements?.[0].lng).toBe(-7.6002);
    expect(couche.groupe.children).toHaveLength(1);
    // Le CROCHET d'export : un document sérialisé repart avec sa couche.
    const document3d = couche.ecrireDansDocument({ version: 2, zones: [] });
    expect((document3d as { electrical?: DocumentElectrique }).electrical?.equipements).toHaveLength(1);
    // ... et ne partage AUCUNE référence avec l'état vivant.
    expect((document3d as { electrical?: DocumentElectrique }).electrical).not.toBe(doc);
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
    // Le source ne déclare l'identifiant qu'une fois : le panneau de calques de
    // l'ERP relit CE littéral (test jumeau côté frontend).
    const source = readFileSync(fileURLToPath(new URL('./electrique3d.ts', import.meta.url)), 'utf8');
    expect(source.split("ID_CALQUE_ELECTRIQUE = '").length - 1).toBe(1);
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

describe('CALX220 — l’attache dans le constructeur', () => {
  const source = readFileSync(
    fileURLToPath(new URL('../roof-tool-pro11.ts', import.meta.url)),
    'utf8',
  );

  it('UNE ligne d’attache dans l’objet `onApiReady`, et rien d’autre', () => {
    const bloc = source.slice(source.indexOf('opts.onApiReady?.({'));
    expect(bloc).toContain('electrique: creerCoucheElectrique(ctx)');
    // Une seule occurrence dans tout le fichier, hors l'import du module.
    const appels = source.split('creerCoucheElectrique(ctx)').length - 1;
    expect(appels).toBe(1);
  });
});
