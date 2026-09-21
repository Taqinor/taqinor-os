/* ============================================================================
   CALX219 / CALX220 / CALX223 / CALX221 — LA COUCHE ÉLECTRIQUE DE L'ATELIER 3D.
   ----------------------------------------------------------------------------
   Constat : la seule chose « électrique » de la scène était la TEINTE des
   modules (`scene3d.ts`, coloration par chaîne) — l'atelier n'était donc pas un
   outil de conception électrique : aucun organe posable, aucun cheminement de
   câble, rien à déplacer, rien à persister. Ce module ajoute cette couche, et
   RIEN d'autre : il ne touche aucun fichier de la scène existante.

   CE QUE CE MODULE PORTE, ET CE QU'IL NE PORTE PAS
   ------------------------------------------------
   Il porte de la TOPOLOGIE et de la POSITION : où sont les organes, par quels
   points passent les câbles. Il ne porte AUCUNE grandeur électrique — pas une
   puissance, pas un calibre, pas une section, pas une chute, pas un prix. Ces
   caractéristiques se lisent sur la fiche produit désignée par `produitId`, ou
   sur la norme retenue côté serveur ; un organe sans fiche n'est pas un défaut à
   combler, c'est un organe dont les calculs qui en dépendent S'OMETTENT en
   nommant la fiche manquante.

   AUCUNE DIMENSION N'EST LUE AILLEURS QUE DANS LE DOCUMENT. Les tailles des
   symboles posés dans la scène (`DESSIN_PAR_TYPE` ci-dessous) sont des
   CONVENTIONS DE DESSIN : elles servent à voir le marqueur, jamais à mesurer
   quoi que ce soit. Aucune longueur, aucune distance, aucun métré n'en est
   dérivé — la longueur d'un cheminement se calcule côté serveur depuis les
   `points` et/ou la longueur SAISIE, et publie toujours son origine.

   CE QUI EST IGNORÉ, ET COMMENT ON LE SAIT
   -----------------------------------------
   Une entrée sans `lng`/`lat` est IGNORÉE — jamais posée au centre du toit,
   jamais à (0, 0) : un organe sans point ne porte aucune longueur mesurable. Un
   `type` hors de l'énumération FERMÉE est IGNORÉ lui aussi. Dans les deux cas
   l'entrée est NOMMÉE dans un avertissement rendu (`avertissements()`), jamais
   avalée en silence et jamais transformée en exception : un document importé
   d'ailleurs ne doit pas faire tomber l'atelier.

   LE DOCUMENT RESTE VALIDE APRÈS CHAQUE GESTE. Toute entrée écrite ici a la
   forme EXACTE que le schéma `roof_layout_v2.schema.json` impose à
   `electrical.equipements[]` / `electrical.cheminements[]` (clés obligatoires
   présentes, énumérations tenues, aucune clé numérique inventée) — le test
   co-localisé épingle cette forme contre les échantillons de contrat committés.
   ========================================================================== */

import * as THREE from 'three';
import { type LngLat } from '../../lib/roof';

/** CALX221 — l'identifiant du calque, DÉCLARÉ ICI ET UNE SEULE FOIS côté
 *  constructeur. Le panneau de calques de l'ERP le relit pour proposer sa
 *  bascule ; son test jumeau relit ce source pour l'affirmer. */
export const ID_CALQUE_ELECTRIQUE = 'electrique';

/** Les HUIT organes que l'atelier sait poser — énumération FERMÉE du document.
 *  Un type hors de cette liste n'a ni géométrie ici ni bloc au schéma
 *  unifilaire : il n'aurait qu'une existence de papier. */
export const TYPES_EQUIPEMENT = [
  'onduleur',
  'coffret_dc',
  'coffret_ac',
  'compteur_production',
  'compteur_reseau',
  'tgbt',
  'batterie',
  'parafoudre',
] as const;
export type TypeEquipement = (typeof TYPES_EQUIPEMENT)[number];

/** D'où vient la position d'un organe — énumération FERMÉE du document. */
export const SOURCES_EQUIPEMENT = ['saisie', 'import'] as const;
export type SourceEquipement = (typeof SOURCES_EQUIPEMENT)[number];

/** Le côté électrique d'un tronçon — énumération FERMÉE du document. */
export const COTES_CHEMINEMENT = ['dc', 'ac', 'terre'] as const;
export type CoteCheminement = (typeof COTES_CHEMINEMENT)[number];

/** D'où vient la longueur d'un tronçon — énumération FERMÉE du document. */
export const ORIGINES_CHEMINEMENT = ['plan', 'saisie', 'mixte'] as const;
export type OrigineCheminement = (typeof ORIGINES_CHEMINEMENT)[number];

/** Le nom FRANÇAIS de chaque organe : libellé par défaut d'une pose et
 *  vocabulaire des messages de refus. Aucun de ces textes n'est une donnée. */
export const NOM_TYPE_FR: Readonly<Record<TypeEquipement, string>> = {
  onduleur: 'Onduleur',
  coffret_dc: 'Coffret DC',
  coffret_ac: 'Coffret AC',
  compteur_production: 'Compteur de production',
  compteur_reseau: 'Compteur réseau',
  tgbt: 'TGBT',
  batterie: 'Batterie',
  parafoudre: 'Parafoudre',
};

// ───────────────────────────────────────────── le document (formes du schéma)

export interface EquipementElectrique {
  id: string;
  type: TypeEquipement;
  label: string;
  lng: number;
  lat: number;
  /** Altitude SAISIE (m). Absente ou `null` = NON RENSEIGNÉE — jamais « au sol ». */
  altitudeM?: number | null;
  /** Orientation du marqueur (degrés, 0 = nord). Purement visuelle. */
  rotationDeg?: number;
  /** Fiche `stock.Produit` qui porte les caractéristiques, ou `null`. */
  produitId?: number | null;
  source: SourceEquipement;
}

export interface PointCheminement {
  lng: number;
  lat: number;
  altitudeM?: number | null;
}

export interface CheminementElectrique {
  id: string;
  cote: CoteCheminement;
  de: string;
  vers: string;
  points?: PointCheminement[];
  /** Longueur SAISIE (m) pour la part que le plan ne porte pas. Absente ou
   *  `null` = rien n'a été saisi, et non « zéro mètre ». */
  longueurSaisieM?: number | null;
  origine: OrigineCheminement;
}

export interface DocumentElectrique {
  equipements?: EquipementElectrique[];
  cheminements?: CheminementElectrique[];
}

// ───────────────────────────────────────────────────── conventions de dessin

/**
 * CONVENTION DE DESSIN — et rien d'autre.
 *
 * Ces tailles (mètres) et ces teintes ne décrivent AUCUN organe réel : elles
 * donnent au marqueur une silhouette reconnaissable dans la scène. Aucune
 * longueur de câble, aucune emprise, aucun encombrement d'armoire n'en est
 * dérivé — l'encombrement réel, quand il compte, se lit sur la fiche produit.
 * Les changer change le DESSIN, jamais un chiffre publié.
 */
export type FormeDessin =
  | { forme: 'boite'; largeurM: number; profondeurM: number; hauteurM: number; teinte: number }
  | { forme: 'cylindre'; rayonM: number; hauteurM: number; teinte: number }
  | { forme: 'cone'; rayonM: number; hauteurM: number; teinte: number };

/** CONVENTION DE DESSIN : une silhouette DISTINCTE par type — huit types, huit
 *  marqueurs qu'on ne confond pas d'un coup d'œil. */
export const DESSIN_PAR_TYPE: Readonly<Record<TypeEquipement, FormeDessin>> = {
  onduleur: { forme: 'boite', largeurM: 0.6, profondeurM: 0.25, hauteurM: 0.9, teinte: 0x2482d6 },
  coffret_dc: { forme: 'boite', largeurM: 0.4, profondeurM: 0.2, hauteurM: 0.5, teinte: 0xe4a11b },
  coffret_ac: { forme: 'boite', largeurM: 0.45, profondeurM: 0.22, hauteurM: 0.55, teinte: 0x2fb673 },
  compteur_production: { forme: 'cylindre', rayonM: 0.18, hauteurM: 0.4, teinte: 0xb06fd0 },
  compteur_reseau: { forme: 'cylindre', rayonM: 0.22, hauteurM: 0.46, teinte: 0x6f7fd0 },
  tgbt: { forme: 'boite', largeurM: 0.8, profondeurM: 0.4, hauteurM: 1.8, teinte: 0x8a8f99 },
  batterie: { forme: 'boite', largeurM: 0.7, profondeurM: 0.35, hauteurM: 1.2, teinte: 0xd05f5f },
  parafoudre: { forme: 'cone', rayonM: 0.16, hauteurM: 0.45, teinte: 0xf3cc66 },
};

/** CONVENTION DE DESSIN : teinte du tracé par côté électrique. */
export const TEINTE_COTE: Readonly<Record<CoteCheminement, number>> = {
  dc: 0xe4a11b,
  ac: 0x2fb673,
  terre: 0x8a8f99,
};

/** CONVENTION DE DESSIN : hauteur de l'étiquette AU-DESSUS du marqueur (m) et
 *  largeur du cartouche (m). Confort de lecture, aucune donnée. */
const ETIQUETTE_HAUTEUR_M = 0.55;
const ETIQUETTE_LARGEUR_M = 1.9;

/** CONVENTION DE DESSIN : l'altitude d'un point NON RENSEIGNÉE est dessinée au
 *  niveau de référence de la scène. C'est un choix d'affichage — il ne dit pas
 *  que l'organe est au sol, et aucune longueur n'en est tirée. */
const ALTITUDE_DESSIN_PAR_DEFAUT_M = 0;

const DEG2RAD = Math.PI / 180;
const RAYON_TERRE_M = 6378137;
const DEG2M = DEG2RAD * RAYON_TERRE_M;

// ──────────────────────────────────────────────────────── lecture du document

export interface LectureElectrique {
  equipements: EquipementElectrique[];
  cheminements: CheminementElectrique[];
  /** Ce qui a été IGNORÉ, nommé en français — jamais une exception. */
  avertissements: string[];
}

export function estTypeEquipement(v: unknown): v is TypeEquipement {
  return typeof v === 'string' && (TYPES_EQUIPEMENT as readonly string[]).includes(v);
}

function estCote(v: unknown): v is CoteCheminement {
  return typeof v === 'string' && (COTES_CHEMINEMENT as readonly string[]).includes(v);
}

function nombreFini(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v);
}

function texteOuVide(v: unknown): string {
  return typeof v === 'string' ? v : '';
}

/** Désignation d'une entrée dans un message : son libellé s'il existe, sinon
 *  son identifiant, sinon son rang — l'utilisateur doit pouvoir la retrouver. */
function designation(entree: { label?: unknown; id?: unknown }, rang: number): string {
  const label = texteOuVide(entree?.label).trim();
  if (label) return `« ${label} »`;
  const id = texteOuVide(entree?.id).trim();
  if (id) return `« ${id} »`;
  return `n° ${rang + 1}`;
}

/**
 * CALX219 — lit la couche électrique d'un document `roof_layout` v2. Ce qui
 * n'est pas exploitable est ÉCARTÉ et NOMMÉ ; rien n'est jamais complété par un
 * défaut. Un document sans `electrical` rend deux listes vides, sans un mot :
 * c'est le comportement d'aujourd'hui, pas une anomalie.
 */
export function lireCoucheElectrique(document: unknown): LectureElectrique {
  const avertissements: string[] = [];
  const equipements: EquipementElectrique[] = [];
  const cheminements: CheminementElectrique[] = [];
  const racine = (document ?? null) as { electrical?: unknown } | null;
  const couche = (racine && typeof racine === 'object' ? racine.electrical : null) as
    | DocumentElectrique
    | null
    | undefined;
  if (!couche || typeof couche !== 'object') {
    return { equipements, cheminements, avertissements };
  }

  const bruts = Array.isArray(couche.equipements) ? couche.equipements : [];
  const idsVus = new Set<string>();
  bruts.forEach((brut, i) => {
    const entree = (brut ?? {}) as Partial<EquipementElectrique>;
    const id = texteOuVide(entree.id).trim();
    if (!id) {
      avertissements.push(
        `Équipement ${designation(entree, i)} sans identifiant : il ne peut être ni relié `
        + 'ni déplacé — il n’est pas affiché.',
      );
      return;
    }
    if (idsVus.has(id)) {
      avertissements.push(
        `Équipement « ${id} » en double : le second est ignoré — un identifiant désigne `
        + 'UN organe, sinon les cheminements qui le citent deviennent ambigus.',
      );
      return;
    }
    if (!estTypeEquipement(entree.type)) {
      avertissements.push(
        `Type d'équipement « ${texteOuVide(entree.type) || '(vide)'} » inconnu : les seuls `
        + `types posables sont ${TYPES_EQUIPEMENT.join(', ')}.`,
      );
      return;
    }
    if (!nombreFini(entree.lng) || !nombreFini(entree.lat)) {
      avertissements.push(
        `L'équipement ${designation(entree, i)} n'a pas de position : renseignez sa latitude `
        + 'et sa longitude, ou retirez-le du plan — un organe sans point ne porte aucune '
        + 'longueur de câble mesurable.',
      );
      return;
    }
    idsVus.add(id);
    equipements.push(normaliserEquipement({ ...entree, id, type: entree.type }));
  });

  const brutsChemins = Array.isArray(couche.cheminements) ? couche.cheminements : [];
  const idsChemins = new Set<string>();
  brutsChemins.forEach((brut, i) => {
    const entree = (brut ?? {}) as Partial<CheminementElectrique>;
    const id = texteOuVide(entree.id).trim();
    if (!id || idsChemins.has(id)) {
      avertissements.push(
        `Cheminement ${designation(entree, i)} sans identifiant exploitable : il n'est pas tracé.`,
      );
      return;
    }
    if (!estCote(entree.cote)) {
      avertissements.push(
        `Cheminement « ${id} » : côté « ${texteOuVide(entree.cote) || '(vide)'} » inconnu — `
        + `les seuls côtés admis sont ${COTES_CHEMINEMENT.join(', ')}.`,
      );
      return;
    }
    const points = pointsExploitables(entree.points);
    const longueur = nombreFini(entree.longueurSaisieM) && entree.longueurSaisieM > 0
      ? entree.longueurSaisieM
      : null;
    if (points.length < 2 && longueur == null) {
      avertissements.push(
        `Le cheminement « ${id} » n'a ni tracé (deux points minimum) ni longueur saisie : `
        + 'tracez-le sur le plan, ou saisissez sa longueur en mètres — elle ne peut pas '
        + 'être devinée.',
      );
      return;
    }
    idsChemins.add(id);
    cheminements.push({
      id,
      cote: entree.cote,
      de: texteOuVide(entree.de),
      vers: texteOuVide(entree.vers),
      points,
      ...(longueur != null ? { longueurSaisieM: longueur } : {}),
      origine: origineDe(points.length, longueur),
    });
  });

  return { equipements, cheminements, avertissements };
}

/** L'origine DÉCLARÉE d'un tronçon : tracé seul, saisie seule, ou les deux. */
function origineDe(nbPoints: number, longueurSaisieM: number | null): OrigineCheminement {
  if (nbPoints >= 2 && longueurSaisieM != null) return 'mixte';
  if (nbPoints >= 2) return 'plan';
  return 'saisie';
}

/** Les points EXPLOITABLES d'un tracé : un point sans `lng`/`lat` n'est pas un
 *  point (0, 0), il n'existe pas. `altitudeM` absente reste absente. */
function pointsExploitables(bruts: unknown): PointCheminement[] {
  if (!Array.isArray(bruts)) return [];
  const out: PointCheminement[] = [];
  for (const b of bruts) {
    const p = (b ?? {}) as Partial<PointCheminement>;
    if (!nombreFini(p.lng) || !nombreFini(p.lat)) continue;
    out.push({
      lng: p.lng,
      lat: p.lat,
      ...(nombreFini(p.altitudeM) ? { altitudeM: p.altitudeM } : {}),
    });
  }
  return out;
}

/** Une entrée d'équipement RÉDUITE aux clés du schéma : les clés optionnelles
 *  ne sont écrites que si elles portent une valeur (absence ≠ zéro). */
function normaliserEquipement(e: Partial<EquipementElectrique> & { id: string; type: TypeEquipement }): EquipementElectrique {
  const source: SourceEquipement = e.source === 'import' ? 'import' : 'saisie';
  return {
    id: e.id,
    type: e.type,
    label: texteOuVide(e.label),
    lng: e.lng as number,
    lat: e.lat as number,
    ...(nombreFini(e.altitudeM) ? { altitudeM: e.altitudeM } : {}),
    ...(nombreFini(e.rotationDeg) ? { rotationDeg: ((e.rotationDeg % 360) + 360) % 360 } : {}),
    ...(typeof e.produitId === 'number' && Number.isInteger(e.produitId) ? { produitId: e.produitId } : {}),
    source,
  };
}

// ─────────────────────────────────────────────────────────── le groupe 3D

/** `[lng, lat]` → mètres (est, nord) autour de l'origine de la scène — même
 *  repère que la scène de l'atelier (x = est, y = nord, z = hauteur). */
export function versScene(lng: number, lat: number, origine: LngLat): [number, number] {
  const cosLat = Math.cos(origine[1] * DEG2RAD);
  return [(lng - origine[0]) * DEG2M * cosLat, (lat - origine[1]) * DEG2M];
}

function geometrieDe(forme: FormeDessin): THREE.BufferGeometry {
  if (forme.forme === 'cylindre') {
    return new THREE.CylinderGeometry(forme.rayonM, forme.rayonM, forme.hauteurM, 16);
  }
  if (forme.forme === 'cone') {
    return new THREE.ConeGeometry(forme.rayonM, forme.hauteurM, 16);
  }
  return new THREE.BoxGeometry(forme.largeurM, forme.profondeurM, forme.hauteurM);
}

function hauteurDessin(forme: FormeDessin): number {
  return forme.hauteurM;
}

/**
 * L'étiquette FLOTTANTE qui porte le `label` de l'organe. Hors navigateur
 * (tests, rendu hors écran sans DOM) le cartouche n'est pas peint : le sprite
 * existe quand même et porte son texte dans `userData`, si bien que la scène a
 * TOUJOURS la même structure — un test n'observe jamais un arbre différent de
 * celui que l'utilisateur voit.
 */
export function etiquetteFlottante(texte: string): THREE.Sprite {
  const materiau = new THREE.SpriteMaterial({ transparent: true, depthTest: false, depthWrite: false });
  let ratio = 0.25;
  const docGlobal = typeof globalThis !== 'undefined'
    ? (globalThis as { document?: { createElement?: (tag: string) => unknown } }).document
    : undefined;
  if (docGlobal && typeof docGlobal.createElement === 'function') {
    const canvas = docGlobal.createElement('canvas') as HTMLCanvasElement;
    canvas.width = 512;
    canvas.height = 128;
    const c2d = canvas.getContext ? canvas.getContext('2d') : null;
    if (c2d) {
      c2d.font = '600 44px system-ui, sans-serif';
      c2d.textAlign = 'center';
      c2d.textBaseline = 'middle';
      c2d.fillStyle = 'rgba(7, 11, 29, 0.84)';
      c2d.fillRect(0, 0, canvas.width, canvas.height);
      c2d.fillStyle = '#ffffff';
      c2d.fillText(texte, canvas.width / 2, canvas.height / 2);
      const texture = new THREE.CanvasTexture(canvas);
      texture.needsUpdate = true;
      materiau.map = texture;
    }
    ratio = canvas.height / canvas.width;
  }
  const sprite = new THREE.Sprite(materiau);
  sprite.scale.set(ETIQUETTE_LARGEUR_M, ETIQUETTE_LARGEUR_M * ratio, 1);
  sprite.renderOrder = 20;
  sprite.userData = { role: 'etiquette', texte };
  return sprite;
}

/** Le marqueur 3D d'UN organe : sa silhouette de type, son étiquette flottante,
 *  et son identité dans `userData` (c'est elle que le clic relit). */
export function creerMarqueur(equipement: EquipementElectrique, origine: LngLat): THREE.Object3D {
  const forme = DESSIN_PAR_TYPE[equipement.type];
  const maillage = new THREE.Mesh(
    geometrieDe(forme),
    new THREE.MeshLambertMaterial({ color: forme.teinte, transparent: true, opacity: 1 }),
  );
  // Les géométries de Three sont dressées sur l'axe Y ; la scène de l'atelier
  // est en Z vers le haut — d'où le quart de tour sur X pour les volumes de
  // révolution (cylindre, cône). Convention de dessin, sans effet sur le document.
  if (forme.forme !== 'boite') maillage.rotation.x = Math.PI / 2;
  const [est, nord] = versScene(equipement.lng, equipement.lat, origine);
  const z = nombreFini(equipement.altitudeM) ? equipement.altitudeM : ALTITUDE_DESSIN_PAR_DEFAUT_M;
  maillage.position.set(est, nord, z + hauteurDessin(forme) / 2);
  // `rotationDeg` est compté depuis le nord dans le sens horaire ; la scène
  // tourne en sens trigonométrique autour de Z.
  if (nombreFini(equipement.rotationDeg)) maillage.rotation.z = -equipement.rotationDeg * DEG2RAD;
  maillage.userData = {
    calque: ID_CALQUE_ELECTRIQUE,
    id: equipement.id,
    type: equipement.type,
    label: equipement.label,
    // L'altitude NON RENSEIGNÉE est dessinée au niveau de référence : le
    // marqueur le dit, pour que personne ne lise « 0 m » comme une mesure.
    altitudeRenseignee: nombreFini(equipement.altitudeM),
  };
  const etiquette = etiquetteFlottante(equipement.label || NOM_TYPE_FR[equipement.type]);
  etiquette.position.set(0, 0, hauteurDessin(forme) / 2 + ETIQUETTE_HAUTEUR_M);
  maillage.add(etiquette);
  return maillage;
}

/** Vide un groupe et rend la mémoire GPU de ce qu'il portait. */
function viderGroupe(groupe: THREE.Group): void {
  for (const enfant of [...groupe.children]) {
    enfant.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.geometry && typeof m.geometry.dispose === 'function') m.geometry.dispose();
      const mat = (o as { material?: THREE.Material | THREE.Material[] }).material;
      if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
      else if (mat && typeof mat.dispose === 'function') mat.dispose();
    });
    groupe.remove(enfant);
  }
}

// ───────────────────────────────────────────────────────────── la couche

/** Ce que la couche a besoin de savoir de l'atelier. Tout est OPTIONNEL : un
 *  `ctx` qui ne porte pas encore de couche électrique n'est pas un `ctx`
 *  invalide, c'est un plan sans organe. */
export interface ContexteCoucheElectrique {
  /** La couche électrique du document `roof_layout` v2, écrite par les gestes. */
  electrical?: DocumentElectrique | null;
  /** Origine géographique du repère de la scène 3D. */
  sceneOrigin?: LngLat;
  /** Les pans de l'atelier : une extrémité de cheminement peut les désigner. */
  areas?: ReadonlyArray<{ id: string }>;
  activeAreaId?: string;
}

export interface CoucheElectrique {
  /** Le SEUL groupe 3D de la couche (à ajouter à la scène de l'atelier). */
  readonly groupe: THREE.Group;
  /** Reconstruit le groupe depuis le document courant. */
  rafraichir: () => void;
  /** Ce qui a été ignoré au dernier rafraîchissement, nommé en français. */
  avertissements: () => string[];
  /** Le document électrique courant, ou `null` s'il n'y en a pas. */
  documentElectrique: () => DocumentElectrique | null;
}


/**
 * CALX219/220/223/221 — la couche électrique de l'atelier : un groupe 3D bâti
 * depuis le document, les gestes qui l'écrivent, et son entrée de calque.
 *
 * Le document est la SEULE source de vérité : chaque geste l'écrit, puis le
 * groupe est reconstruit depuis lui. Aucun état parallèle ne peut donc diverger
 * de ce qui sera enregistré.
 */
export function creerCoucheElectrique(ctx: ContexteCoucheElectrique): CoucheElectrique {
  const groupe = new THREE.Group();
  groupe.name = ID_CALQUE_ELECTRIQUE;
  let ignores: string[] = [];

  const origine = (): LngLat => (ctx.sceneOrigin ?? [0, 0]) as LngLat;

  const document = (): DocumentElectrique | null => (ctx.electrical ?? null);

  function rafraichir(): void {
    viderGroupe(groupe);
    const lu = lireCoucheElectrique({ electrical: document() });
    ignores = lu.avertissements;
    const o = origine();
    for (const e of lu.equipements) groupe.add(creerMarqueur(e, o));
  }

  rafraichir();

  return {
    groupe,
    rafraichir,
    avertissements: () => [...ignores],
    documentElectrique: () => document(),
  };
}
