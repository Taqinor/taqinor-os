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
