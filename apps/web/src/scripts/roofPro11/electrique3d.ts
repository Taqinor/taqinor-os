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
import { createValueHistory, type ValueHistory } from './layoutHistory';
import { type LngLat } from '../../lib/roof';
import { proposerPointsCheminement, type Pt } from './cheminementAuto'; // ACAL472

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
/** ACAL1944 — largeur d'une PASTILLE (« Chaîne n », « Onduleur ») : lisible sur la carte d'un toit entier (≈ 70 px au cadrage de l'atelier). */
const PASTILLE_LARGEUR_M = 3.2;

/** CONVENTION DE DESSIN : l'altitude d'un point NON RENSEIGNÉE est dessinée au
 *  niveau de référence de la scène. C'est un choix d'affichage — il ne dit pas
 *  que l'organe est au sol, et aucune longueur n'en est tirée. */
const ALTITUDE_DESSIN_PAR_DEFAUT_M = 0;

/** ACAL1317 — PAS D'UNE FLÈCHE quand l'onduleur se déplace au clavier ou par les boutons fléchés (m). Incrément
 *  d'interface, jamais un chiffre montré ni mesuré : le pas fin du placement libre des modules (`FREE_STEP_M`, 1 cm)
 *  demanderait cent appuis pour un mètre, et un organe électrique n'a ni rangée ni lattice dont reprendre le pas. */
export const PAS_DEPLACEMENT_ORGANE_M = 0.25;

/** ACAL1317 — un tracé « aboutit » à un organe quand son bout tombe à moins de ce rayon du point posé (m). Seuil
 *  d'une PHRASE (« le tracé n'aboutit plus à l'onduleur »), aucune longueur n'en est tirée. */
const TOLERANCE_ABOUTISSEMENT_M = 0.5;

/** ACAL1317 — deux tracés sont le MÊME tracé quand, une fois retirés leurs sommets alignés, chaque sommet de l'un
 *  tombe à moins de ce rayon du sommet correspondant de l'autre (m). Le recalcul du plus court chemin garde un sommet
 *  aligné de plus quand une rangée change de longueur : ce sommet ne change pas le trajet. */
const TOLERANCE_MEME_TRACE_M = 0.01;

/** Distance (m) du point `m` au segment [a, b]. */
function distanceAuSegment(m: readonly [number, number], a: readonly [number, number], b: readonly [number, number]): number {
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  const l2 = dx * dx + dy * dy;
  const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, ((m[0] - a[0]) * dx + (m[1] - a[1]) * dy) / l2));
  return Math.hypot(m[0] - (a[0] + t * dx), m[1] - (a[1] + t * dy));
}

/** La polyligne sans ses sommets REDONDANTS : doublons et sommets posés sur le segment de leurs voisins (un sommet
 *  aligné mais hors du segment — un aller-retour — reste : il change le trajet). */
export function sommetsUtiles(points: readonly (readonly [number, number])[]): [number, number][] {
  const out: [number, number][] = [];
  for (const p of points) {
    const q: [number, number] = [p[0], p[1]];
    const dernier = out[out.length - 1];
    if (dernier && Math.hypot(q[0] - dernier[0], q[1] - dernier[1]) <= TOLERANCE_MEME_TRACE_M) continue;
    while (out.length >= 2 && distanceAuSegment(out[out.length - 1], out[out.length - 2], q) <= TOLERANCE_MEME_TRACE_M) out.pop();
    out.push(q);
  }
  return out;
}

/** Deux polylignes (m) décrivent-elles le même trajet, à `TOLERANCE_MEME_TRACE_M` près ? */
export function memeTrajet(a: readonly (readonly [number, number])[], b: readonly (readonly [number, number])[]): boolean {
  const [ua, ub] = [sommetsUtiles(a), sommetsUtiles(b)];
  return ua.length === ub.length
    && ua.every((p, i) => Math.hypot(p[0] - ub[i][0], p[1] - ub[i][1]) <= TOLERANCE_MEME_TRACE_M);
}

const DEG2RAD = Math.PI / 180;
import { WGS84_RADIUS as RAYON_TERRE_M } from '../../lib/geo';
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
export function etiquetteFlottante(texte: string, pastille: string | null = null): THREE.Sprite {
  const materiau = new THREE.SpriteMaterial({ transparent: true, depthTest: false, depthWrite: false });
  let ratio = 0.25;
  const docGlobal = typeof globalThis !== 'undefined'
    ? (globalThis as { document?: { createElement?: (tag: string) => unknown } }).document
    : undefined;
  if (docGlobal && typeof docGlobal.createElement === 'function') {
    const canvas = docGlobal.createElement('canvas') as HTMLCanvasElement;
    canvas.width = pastille ? 320 : 512; // ACAL1944 — pastille : texte gros dans une pilule courte (maquette)
    canvas.height = pastille ? 96 : 128;
    const c2d = canvas.getContext ? canvas.getContext('2d') : null;
    if (c2d) {
      c2d.font = '600 44px system-ui, sans-serif';
      c2d.textAlign = 'center';
      c2d.textBaseline = 'middle';
      if (pastille) { // ACAL1944 — pilule blanche, point à la couleur (maquette Electrique : « ● Chaîne 1 », « ● Onduleur »)
        c2d.fillStyle = '#ffffff';
        c2d.beginPath();
        c2d.roundRect?.(2, 2, canvas.width - 4, canvas.height - 4, 46);
        c2d.fill();
        c2d.fillStyle = pastille;
        c2d.beginPath();
        c2d.arc(44, canvas.height / 2, 14, 0, Math.PI * 2);
        c2d.fill();
        c2d.fillStyle = '#0c1335';
        c2d.font = '700 46px system-ui, sans-serif';
        c2d.textAlign = 'left';
        c2d.fillText(texte, 72, canvas.height / 2 + 2);
      } else {
        c2d.fillStyle = 'rgba(7, 11, 29, 0.84)';
        c2d.fillRect(0, 0, canvas.width, canvas.height);
        c2d.fillStyle = '#ffffff';
        c2d.fillText(texte, canvas.width / 2, canvas.height / 2);
      }
      const texture = new THREE.CanvasTexture(canvas);
      texture.needsUpdate = true;
      if (pastille) texture.colorSpace = THREE.SRGBColorSpace; // ACAL1944 — blanc pur, texte encre (pas délavés)
      materiau.map = texture;
    }
    ratio = canvas.height / canvas.width;
  }
  if (pastille) materiau.toneMapped = false;
  const sprite = new THREE.Sprite(materiau);
  const largeur = pastille ? PASTILLE_LARGEUR_M : ETIQUETTE_LARGEUR_M;
  sprite.scale.set(largeur, largeur * ratio, 1);
  sprite.renderOrder = 20;
  sprite.userData = { role: 'etiquette', texte, ...(pastille ? { pastille } : {}) };
  return sprite;
}

/** ACAL1944 — une chaîne SERVIE à poser sur la carte : son libellé (« Chaîne 1 »), sa couleur servie (0–1) et les points
 *  (repère de la scène, m) du dessus de ses modules. */
export interface ChaineAPoser { libelle: string; couleur: { r: number; g: number; b: number }; points: readonly (readonly [number, number, number])[] }

/** ACAL1944 — les étiquettes « Chaîne n » de l'étape Électrique : une pilule par chaîne, au nord de ses modules,
 *  point à sa couleur servie. Aucune chaîne servie : un groupe VIDE (rien d'inventé). */
export function etiquettesChaines(chaines: readonly ChaineAPoser[]): THREE.Group {
  const groupe = new THREE.Group();
  groupe.userData = { role: 'etiquettes-chaines' };
  for (const c of chaines) {
    if (!c.points.length) continue;
    const n = c.points.length;
    const x = c.points.reduce((a, p) => a + p[0] / n, 0);
    const y = Math.max(...c.points.map((p) => p[1])) + 1.4; // au nord de sa rangée la plus haute, hors des modules (maquette)
    const z = Math.max(...c.points.map((p) => p[2]));
    const css = `rgb(${[c.couleur.r, c.couleur.g, c.couleur.b].map((v) => Math.round(Math.min(1, Math.max(0, v)) * 255)).join(', ')})`;
    const etiquette = etiquetteFlottante(c.libelle, css);
    etiquette.position.set(x, y, z + ETIQUETTE_HAUTEUR_M * 2);
    groupe.add(etiquette);
  }
  return groupe;
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
  const etiquette = etiquetteFlottante(equipement.label || NOM_TYPE_FR[equipement.type], equipement.type === 'onduleur' ? '#0c1335' : null); // ACAL1944 — pastille « Onduleur »
  etiquette.position.set(0, 0, hauteurDessin(forme) / 2 + ETIQUETTE_HAUTEUR_M);
  maillage.add(etiquette);
  return maillage;
}

/** Le tracé 3D d'UN cheminement. `null` quand le plan ne porte pas le tracé
 *  (tronçon SAISI au clavier) : il n'y a rien à dessiner, et rien n'est deviné. */
export function creerTraceCheminement(
  cheminement: CheminementElectrique,
  origine: LngLat,
): THREE.Object3D | null {
  const points = cheminement.points ?? [];
  if (points.length < 2) return null;
  const sommets: number[] = [];
  for (const p of points) {
    const [est, nord] = versScene(p.lng, p.lat, origine);
    sommets.push(est, nord, nombreFini(p.altitudeM) ? p.altitudeM : ALTITUDE_DESSIN_PAR_DEFAUT_M);
  }
  const geometrie = new THREE.BufferGeometry();
  geometrie.setAttribute('position', new THREE.Float32BufferAttribute(sommets, 3));
  const ligne = new THREE.Line(
    geometrie,
    new THREE.LineBasicMaterial({ color: TEINTE_COTE[cheminement.cote], transparent: true, opacity: 1 }),
  );
  ligne.userData = {
    calque: ID_CALQUE_ELECTRIQUE,
    id: cheminement.id,
    cote: cheminement.cote,
    de: cheminement.de,
    vers: cheminement.vers,
    origine: cheminement.origine,
  };
  return ligne;
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
  /** T4-X7-015 (calque Électrique) — la table d'affectation SERVIE (ACAL286) : des chaînes formées sont, elles aussi, de l'électrique à montrer ou
   *  à masquer, même quand aucun organe n'est encore posé. Lecture seule ; absente (estimateur public) ⇒ rien de plus. */
  affectationColoration?: { labelByModule?: { readonly size: number } } | null;
  /** Les pans de l'atelier : une extrémité de cheminement peut les désigner. */
  areas?: ReadonlyArray<{
    id: string;
    /** ACAL510 — « Pan existant » : modules déjà en place, hors de la vente (ACAL1317 : aucun câble neuf n'en part). */
    existant?: boolean;
    /** ACAL472 — la pose du pan (rive + rangées de modules) : sans elle, aucun tracé n'est proposé. */
    renderPlan?: {
      pack: { origin: LngLat; azimuthDeg: number; ringENU: [number, number][] };
      grid: { rowWidthM: number; panels: ReadonlyArray<{ cx: number; cy: number }> };
    } | null;
  }>;
  activeAreaId?: string;
}

/** Un geste REFUSÉ : le champ EXACT en cause, et le message affiché SOUS lui. */
export interface RefusElectrique {
  ok: false;
  champ: string;
  message: string;
}

export interface PoseReussie {
  ok: true;
  equipement: EquipementElectrique;
}

export interface CheminementReussi {
  ok: true;
  cheminement: CheminementElectrique;
}

/** ACAL1317 — ce que le geste a fait du tracé : les tracés (re)proposés, et le refus s'il n'a pu l'être. */
export interface SuiviTrace {
  traces: string[];
  refusTrace: RefusElectrique | null;
}

/** ACAL1317 — les tracés d'un organe : PROPOSÉS (reproposés quand il bouge), AUTRES (jamais touchés) et, parmi
 *  ceux-ci, ceux dont le bout ne tombe plus sur l'organe. */
export interface EtatTracesOrgane {
  proposes: string[];
  /** Les tracés NON reconnus comme le tracé proposé d'aujourd'hui (on ne sait pas qui les a tracés). */
  autres: string[];
  decales: string[];
  /** Les pans à modules qui n'ont encore aucun tracé vers l'organe (le tracé est alors PARTIEL). */
  pansSansTrace: string[];
}

export interface EtatCalque {
  visible: boolean;
  opacite: number;
}

export interface CoucheElectrique {
  /** CALX221 — l'identifiant de calque de cette couche. */
  readonly idCalque: string;
  /** Le SEUL groupe 3D de la couche (à ajouter à la scène de l'atelier). */
  readonly groupe: THREE.Group;
  /** Reconstruit le groupe depuis le document courant. */
  rafraichir: () => void;
  /** Ce qui a été ignoré au dernier rafraîchissement, nommé en français. */
  avertissements: () => string[];
  /** CALX221 — le calque n'existe QUE si le document porte `electrical` (T4-X7-015 : ou si des chaînes sont formées). */
  calqueDisponible: () => boolean;
  /** CALX221 — visibilité + opacité, comme les autres calques de l'atelier. */
  setLayerState: (id: string, etat: { visible: boolean; opacite?: number }) => boolean;
  etatCalque: () => EtatCalque;
  // — CALX220 : poser, déplacer, retirer —
  /** ACAL1317 — `{ suivreTrace: true }` : la pose propose aussi le tracé DC depuis le pan (un seul cran d'annulation). */
  armerPose: (type: TypeEquipement | null, options?: { suivreTrace?: boolean }) => boolean;
  typeArme: () => TypeEquipement | null;
  /** ACAL1317 — le prochain clic sur la carte DÉPLACE l'organe `id` (au lieu d'en poser un) et son tracé proposé
   *  suit ; `null` désarme. Rend `false` pour un organe absent du plan. */
  armerDeplacement: (id: string | null) => boolean;
  deplacementArme: () => string | null;
  /** ACAL1317 — le pas d'une flèche (`PAS_DEPLACEMENT_ORGANE_M`), relu par l'écran de l'ERP. */
  readonly pasDeplacementM: number;
  /** ACAL1317 — déplace de (est, nord) mètres, le tracé proposé suit (flèches du clavier ou boutons fléchés). */
  pousser:(id: string, dEstM: number, dNordM: number) => (PoseReussie & SuiviTrace) | RefusElectrique;
  /** ACAL1317 — retire l'organe et ses tracés proposés en un cran ; les autres tracés restent. */
  retirerAvecTraces: (id: string) => { ok: boolean; tracesGardees: string[] };
  /** ACAL1317 — l'état des tracés d'un organe (lecture seule). */
  etatTraces: (id: string) => EtatTracesOrgane;
  /** ACAL1317 — appelé après chaque changement du document (clic sur la carte compris) ; rend le désabonnement. */
  ecouter: (f: () => void) => () => void;
  /** ACAL1317 — lecture seule : désarme tout, puis refuse pose, déplacement, retrait, tracé et annulation. */
  definirLectureSeule: (oui: boolean) => void;
  lectureSeule: () => boolean;
  poser: (lngLat: LngLat, options?: { label?: string; altitudeM?: number | null; rotationDeg?: number; produitId?: number | null }) => PoseReussie | RefusElectrique;
  /** CALX222 — un clic sur la carte pose l'organe armé (« Armer la pose ») puis désarme ;
   *  rend `true` si le clic est consommé (un type était armé), `false` sinon. */
  clicCarte: (lngLat: LngLat) => boolean;
  selectionner: (id: string | null) => boolean;
  selection: () => string | null;
  deplacer: (id: string, lngLat: LngLat) => PoseReussie | RefusElectrique;
  retirer: (id?: string) => boolean;
  // — CALX223 : tracer un cheminement —
  demarrerCheminement: (depart: { cote: CoteCheminement; de: string }) => true | RefusElectrique;
  ajouterPointCheminement: (lngLat: LngLat, altitudeM?: number | null) => number;
  /** ACAL472 — propose le tracé de `de` à `vers` le long des rangées et de la rive (plus court chemin), `origine: 'plan'`. */
  proposerCheminement: (depart: { cote: CoteCheminement; de: string; vers: string }) => CheminementReussi | RefusElectrique;
  pointsEnCours: () => PointCheminement[];
  terminerCheminement: (vers: string) => CheminementReussi | RefusElectrique;
  abandonnerCheminement: () => boolean;
  saisirCheminement: (saisie: { cote: CoteCheminement; de: string; vers: string; longueurM: number }) => CheminementReussi | RefusElectrique;
  dernierRefus: () => RefusElectrique | null;
  // — l'annulation —
  annuler: () => boolean;
  retablir: () => boolean;
  profondeurHistorique: () => { undo: number; redo: number };
  /** Le document électrique courant, ou `null` s'il n'y en a pas. */
  documentElectrique: () => DocumentElectrique | null;
  /** Écrit la couche électrique dans un document sérialisé (crochet d'export). */
  ecrireDansDocument: <T extends object>(document: T) => T;
}

/** Copie PROFONDE de la couche électrique — l'historique ne partage jamais une
 *  référence avec l'état vivant. */
function copieDocument(d: DocumentElectrique | null): DocumentElectrique | null {
  if (!d) return null;
  return {
    ...(d.equipements ? { equipements: d.equipements.map((e) => ({ ...e })) } : {}),
    ...(d.cheminements
      ? {
        cheminements: d.cheminements.map((c) => ({
          ...c,
          ...(c.points ? { points: c.points.map((p) => ({ ...p })) } : {}),
        })),
      }
      : {}),
  };
}

/** Le prochain identifiant libre d'une famille (`eq`, `ch`) — jamais un doublon. */
function prochainId(prefixe: string, existants: readonly { id: string }[]): string {
  let max = 0;
  for (const e of existants) {
    const m = /^([a-z]+)(\d+)$/.exec(e.id ?? '');
    if (m && m[1] === prefixe) max = Math.max(max, Number(m[2]));
  }
  return `${prefixe}${max + 1}`;
}

/** T4-X7-015 (calque Électrique) — la case « Électrique » est-elle cochée ? Un seul état : celui de `setLayerState`, que la
 *  couche inscrit sur son groupe. Sans couche (estimateur public) ⇒ vrai : rien n'est masqué. */
export const calqueElectriqueVisible = (groupe: { userData: Record<string, unknown> } | null | undefined): boolean =>
  groupe?.userData.calqueVisible !== false;

/** T4-X7-015 — la scène s'inscrit auprès de la couche : à chaque changement de la case, `siChange` puis `apres` (étiquettes
 *  et teintes redites). Rattache aussitôt (`siChange`) ; sans couche, rattache seulement. */
export function brancherCalqueElectrique(
  groupe: { userData: Record<string, unknown> } | null, siChange: () => void, apres: () => void,
): void {
  if (groupe) groupe.userData.siEtatChange = () => { siChange(); apres(); };
  siChange();
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
  // ACAL1944 — la couche hydratée AVANT le premier rendu était dessinée autour de l'origine [0, 0] (aucune origine de
  // scène encore) : l'onduleur posé tombait hors de la carte. La scène l'appelle à chaque rattachement.
  groupe.userData.siOrigineChange = () => {
    const o = origine();
    if (!origineDessinee || o[0] !== origineDessinee[0] || o[1] !== origineDessinee[1]) rafraichir();
  };
  let ignores: string[] = [];
  let arme: TypeEquipement | null = null;
  let suivreALaPose = false; // ACAL1317
  let deplacementVise: string | null = null; // ACAL1317
  // ACAL1317 — conception en LECTURE SEULE (devis figé, droit de voir seulement) : la couche refuse elle-même toute
  // écriture, pas seulement les boutons de l'écran. Posé par l'ERP (`definirLectureSeule`).
  let lectureSeule = false;
  let selectionne: string | null = null;
  let refus: RefusElectrique | null = null;
  let etat: EtatCalque = { visible: true, opacite: 1 };
  let enCours: { cote: CoteCheminement; de: string; points: PointCheminement[] } | null = null;
  // La MÊME mécanique d'historique que le reste de l'atelier (photo + tampon
  // circulaire) — un seul modèle d'annulation dans le constructeur, pas deux.
  const histoire: ValueHistory<DocumentElectrique | null> = createValueHistory(copieDocument);

  const origine = (): LngLat => (ctx.sceneOrigin ?? [0, 0]) as LngLat;

  const document = (): DocumentElectrique | null => (ctx.electrical ?? null);

  /** Le document, créé au premier geste : tant que rien n'est posé, le plan n'a
   *  PAS de couche électrique (et le calque n'est donc pas proposé). */
  const documentEcrivable = (): DocumentElectrique => {
    if (!ctx.electrical) ctx.electrical = {};
    if (!Array.isArray(ctx.electrical.equipements)) ctx.electrical.equipements = [];
    if (!Array.isArray(ctx.electrical.cheminements)) ctx.electrical.cheminements = [];
    return ctx.electrical;
  };

  // ACAL1317 — un geste COMPOSÉ (déplacer l'onduleur PUIS reproposer son tracé) est UN cran d'annulation : la photo
  // est prise une fois à l'entrée, les gestes élémentaires de l'intérieur n'en reprennent pas.
  let enGeste = 0;
  const ecouteurs = new Set<() => void>();
  const notifier = (): void => { for (const f of [...ecouteurs]) f(); };
  const photographier = (): void => {
    if (enGeste > 0) return;
    histoire.push(copieDocument(document()));
  };
  function enUnGeste<T>(f: () => T): T {
    photographier();
    enGeste += 1;
    try {
      return f();
    } finally {
      enGeste -= 1;
      if (enGeste === 0) notifier();
    }
  }

  let origineDessinee: LngLat | null = null;
  function rafraichir(): void {
    viderGroupe(groupe);
    const lu = lireCoucheElectrique({ electrical: document() });
    ignores = lu.avertissements;
    const o = origine();
    origineDessinee = o;
    for (const c of lu.cheminements) {
      const trace = creerTraceCheminement(c, o);
      if (trace) groupe.add(trace);
    }
    for (const e of lu.equipements) groupe.add(creerMarqueur(e, o));
    appliquerEtat();
    if (enGeste === 0) notifier(); // ACAL1317 — l'écran relit le document après chaque geste (clic sur la carte compris)
  }

  function appliquerEtat(): void {
    groupe.visible = etat.visible;
    groupe.userData.calqueVisible = etat.visible; // T4-X7-015 — l'état du calque : la scène le relit pour les étiquettes et les teintes
    groupe.traverse((o) => {
      const mat = (o as { material?: THREE.Material | THREE.Material[] }).material;
      const liste = Array.isArray(mat) ? mat : mat ? [mat] : [];
      for (const m of liste) {
        m.transparent = true;
        (m as THREE.Material & { opacity: number }).opacity = etat.opacite;
        m.needsUpdate = true;
      }
    });
  }

  /** Les identifiants qu'une extrémité de cheminement peut désigner : les
   *  organes posés ET les pans de l'atelier. */
  const idsResolvables = (): Set<string> => {
    const out = new Set<string>();
    for (const e of document()?.equipements ?? []) if (e?.id) out.add(e.id);
    for (const a of ctx.areas ?? []) if (a?.id) out.add(a.id);
    if (ctx.activeAreaId) out.add(ctx.activeAreaId);
    return out;
  };

  const refuser = (champ: string, message: string): RefusElectrique => {
    const r: RefusElectrique = { ok: false, champ, message };
    refus = r;
    return r;
  };
  const refusLecture = (): RefusElectrique => refuser(
    'electrical', 'Conception en lecture seule : rien n’est posé, déplacé ni retiré.');

  // ── CALX220 — poser / déplacer / retirer ────────────────────────────────

  function poser(
    lngLat: LngLat,
    options?: { label?: string; altitudeM?: number | null; rotationDeg?: number; produitId?: number | null },
  ): PoseReussie | RefusElectrique {
    if (lectureSeule) return refusLecture();
    if (!arme) {
      return refuser(
        'electrical.equipements.type',
        'Aucun type d’équipement n’est armé : choisissez l’organe à poser '
        + `(${TYPES_EQUIPEMENT.join(', ')}) avant de cliquer sur le plan.`,
      );
    }
    if (!Array.isArray(lngLat) || !nombreFini(lngLat[0]) || !nombreFini(lngLat[1])) {
      return refuser(
        'electrical.equipements.lat',
        'Le point cliqué n’a pas de coordonnées : l’équipement n’est pas posé — un organe '
        + 'sans point ne porte aucune longueur de câble mesurable.',
      );
    }
    const type: TypeEquipement = arme;
    photographier();
    const doc = documentEcrivable();
    const liste = doc.equipements as EquipementElectrique[];
    const id = prochainId('eq', liste);
    const rang = liste.filter((e) => e.type === type).length + 1;
    const equipement = normaliserEquipement({
      id,
      type,
      label: (options?.label ?? '').trim() || `${NOM_TYPE_FR[type]} ${rang}`,
      lng: lngLat[0],
      lat: lngLat[1],
      ...(options?.altitudeM != null ? { altitudeM: options.altitudeM } : {}),
      ...(options?.rotationDeg != null ? { rotationDeg: options.rotationDeg } : {}),
      ...(options?.produitId != null ? { produitId: options.produitId } : {}),
      source: 'saisie',
    });
    liste.push(equipement);
    selectionne = equipement.id;
    refus = null;
    rafraichir();
    return { ok: true, equipement };
  }

  function deplacer(id: string, lngLat: LngLat): PoseReussie | RefusElectrique {
    if (lectureSeule) return refusLecture();
    const liste = (document()?.equipements ?? []) as EquipementElectrique[];
    const cible = liste.find((e) => e.id === id);
    if (!cible) {
      return refuser(
        'electrical.equipements.id',
        `Aucun équipement « ${id} » sur ce plan : rien n’a été déplacé.`,
      );
    }
    if (!Array.isArray(lngLat) || !nombreFini(lngLat[0]) || !nombreFini(lngLat[1])) {
      return refuser(
        'electrical.equipements.lat',
        `Le point d’arrivée n’a pas de coordonnées : « ${cible.label || cible.id} » n’a pas bougé.`,
      );
    }
    photographier();
    cible.lng = lngLat[0];
    cible.lat = lngLat[1];
    refus = null;
    rafraichir();
    return { ok: true, equipement: cible };
  }

  function retirer(id?: string): boolean {
    if (lectureSeule) { refusLecture(); return false; }
    const cible = id ?? selectionne;
    if (!cible) return false;
    const doc = document();
    const liste = (doc?.equipements ?? []) as EquipementElectrique[];
    const i = liste.findIndex((e) => e.id === cible);
    const chemins = (doc?.cheminements ?? []) as CheminementElectrique[];
    const ic = i < 0 ? chemins.findIndex((c) => c.id === cible) : -1; // ACAL472 — un tracé est supprimable
    if (i < 0 && ic < 0) return false;
    photographier();
    if (i >= 0) liste.splice(i, 1); else chemins.splice(ic, 1);
    if (selectionne === cible) selectionne = null;
    rafraichir();
    return true;
  }

  // ── CALX223 — tracer un cheminement ─────────────────────────────────────

  function demarrerCheminement(depart: { cote: CoteCheminement; de: string }): true | RefusElectrique {
    if (lectureSeule) return refusLecture();
    if (!estCote(depart?.cote)) {
      return refuser(
        'electrical.cheminements.cote',
        `Côté électrique « ${texteOuVide(depart?.cote) || '(vide)'} » inconnu : les seuls côtés `
        + `admis sont ${COTES_CHEMINEMENT.join(', ')}.`,
      );
    }
    const de = texteOuVide(depart?.de).trim();
    if (!idsResolvables().has(de)) {
      return refuser(
        'electrical.cheminements.de',
        `Le cheminement part de « ${de || '(vide)'} », qui n'existe ni parmi les équipements `
        + 'ni parmi les pans de ce plan : partez d’un organe posé ou d’un pan tracé — un '
        + 'tronçon qui ne relie rien fausse le métré sans jamais se voir.',
      );
    }
    enCours = { cote: depart.cote, de, points: [] };
    refus = null;
    return true;
  }

  function ajouterPointCheminement(lngLat: LngLat, altitudeM?: number | null): number {
    if (!enCours) return 0;
    if (!Array.isArray(lngLat) || !nombreFini(lngLat[0]) || !nombreFini(lngLat[1])) return enCours.points.length;
    enCours.points.push({
      lng: lngLat[0],
      lat: lngLat[1],
      ...(nombreFini(altitudeM) ? { altitudeM } : {}),
    });
    return enCours.points.length;
  }

  function terminerCheminement(vers: string): CheminementReussi | RefusElectrique {
    if (!enCours) {
      return refuser(
        'electrical.cheminements.de',
        'Aucun cheminement n’est en cours de tracé : démarrez-le depuis un organe ou un pan.',
      );
    }
    const arrivee = texteOuVide(vers).trim();
    if (!idsResolvables().has(arrivee)) {
      const courant = enCours;
      return refuser(
        'electrical.cheminements.vers',
        `Le cheminement part de « ${courant.de} » vers « ${arrivee || '(vide)'} », qui n'existe `
        + 'ni parmi les équipements ni parmi les pans de ce plan : reliez-le à un organe posé, '
        + 'ou abandonnez le tracé — un tronçon qui ne relie rien fausse le métré sans jamais '
        + 'se voir.',
      );
    }
    if (enCours.points.length < 2) {
      return refuser(
        'electrical.cheminements.points',
        `Le cheminement de « ${enCours.de} » vers « ${arrivee} » n'a ni tracé (deux points `
        + 'minimum) ni longueur saisie : tracez-le sur le plan, ou saisissez sa longueur en '
        + 'mètres — elle ne peut pas être devinée.',
      );
    }
    photographier();
    const doc = documentEcrivable();
    const liste = doc.cheminements as CheminementElectrique[];
    const cheminement: CheminementElectrique = {
      id: prochainId('ch', liste),
      cote: enCours.cote,
      de: enCours.de,
      vers: arrivee,
      points: enCours.points.map((p) => ({ ...p })),
      origine: 'plan',
    };
    liste.push(cheminement);
    enCours = null;
    refus = null;
    rafraichir();
    return { ok: true, cheminement };
  }

  function abandonnerCheminement(): boolean {
    if (!enCours) return false;
    enCours = null;
    return true;
  }

  /** ACAL472 — les points du tracé PROPOSÉ (`[lng, lat]`), calculés sans rien écrire ; un refus est RENDU, jamais
   *  mémorisé (ACAL1317 : la même fonction juge si un tracé existant EST un tracé proposé). */
  function pointsProposes(depart: { cote: CoteCheminement; de: string; vers: string }): { ok: true; points: LngLat[] } | RefusElectrique {
    const refusPoints = (message: string): RefusElectrique => ({ ok: false, champ: 'electrical.cheminements.points', message });
    const pans = (ctx.areas ?? []).filter((a) => a.renderPlan);
    const pan = pans.find((a) => a.id === depart?.de || a.id === depart?.vers)
      ?? pans.find((a) => a.id === ctx.activeAreaId) ?? pans[0];
    const plan = pan?.renderPlan;
    if (!plan) {
      return refusPoints('Aucun pan posé : la rive et les rangées sont inconnues, le tracé ne peut pas être proposé.');
    }
    const o = plan.pack.origin;
    const enu = (id: string): Pt | null => {
      if (id === pan!.id) {
        const r = plan.pack.ringENU;
        return [r.reduce((t, p) => t + p[0], 0) / r.length, r.reduce((t, p) => t + p[1], 0) / r.length];
      }
      const e = (document()?.equipements ?? []).find((x) => x.id === id);
      return e && nombreFini(e.lng) && nombreFini(e.lat) ? versScene(e.lng, e.lat, o) : null;
    };
    const [de, vers] = [enu(texteOuVide(depart?.de).trim()), enu(texteOuVide(depart?.vers).trim())];
    if (!de || !vers) {
      return refusPoints('Une extrémité du tracé n’a pas de position sur ce pan : posez l’organe ou choisissez le pan.');
    }
    const az = plan.pack.azimuthDeg * DEG2RAD;
    const f: Pt = [Math.sin(az), Math.cos(az)]; // empilement ; l'axe d'une rangée est u = (−f.y, f.x)
    const rangs = new Map<number, { v: number; u: number[] }>();
    for (const p of plan.grid.panels) {
      const v = p.cx * f[0] + p.cy * f[1];
      const rang = rangs.get(Math.round(v * 20)) ?? { v, u: [] };
      rang.u.push(-p.cx * f[1] + p.cy * f[0]);
      rangs.set(Math.round(v * 20), rang);
    }
    const hors = ([u, v]: Pt): Pt => [-u * f[1] + v * f[0], u * f[0] + v * f[1]];
    const rangees = [...rangs.values()].map(({ v, u }) => [
      hors([Math.min(...u) - plan.grid.rowWidthM / 2, v]), hors([Math.max(...u) + plan.grid.rowWidthM / 2, v]),
    ] as [Pt, Pt]);
    const res = proposerPointsCheminement({ de, vers, rangees, rive: plan.pack.ringENU as Pt[] });
    if (!res.ok) return refusPoints(res.motif);
    const cosLat = Math.cos(o[1] * DEG2RAD);
    return { ok: true, points: res.points.map(([e, n]) => [o[0] + e / (DEG2M * cosLat), o[1] + n / DEG2M] as LngLat) };
  }

  /** ACAL472 — le tracé proposé, écrit par les gestes existants ; un tracé `plan` déjà proposé pour la même liaison
   *  est remplacé. */
  function proposerCheminement(depart: { cote: CoteCheminement; de: string; vers: string }): CheminementReussi | RefusElectrique {
    const propose = pointsProposes(depart);
    if (!propose.ok) return refuser(propose.champ, propose.message);
    const anciens = ((document()?.cheminements ?? []) as CheminementElectrique[])
      .filter((c) => c.origine === 'plan' && c.cote === depart.cote && c.de === depart.de && c.vers === depart.vers).map((c) => c.id);
    const d = demarrerCheminement({ cote: depart.cote, de: depart.de });
    if (d !== true) return d;
    for (const p of propose.points) ajouterPointCheminement(p);
    const fin = terminerCheminement(depart.vers);
    if (!fin.ok) enCours = null; // un tracé refusé ne reste pas à moitié ouvert
    if (fin.ok && anciens.length) {
      const liste = document()!.cheminements as CheminementElectrique[];
      for (const id of anciens) liste.splice(liste.findIndex((c) => c.id === id), 1);
      rafraichir();
    }
    return fin;
  }

  // ── ACAL1317 — l'onduleur se pose et se DÉPLACE depuis l'étape Électrique, son tracé suit ──────────────

  /** Les tracés qui touchent l'organe `id` (par `de` ou par `vers`), tels que le document les porte. */
  const tracesDe = (id: string): CheminementElectrique[] => ((document()?.cheminements ?? []) as CheminementElectrique[])
    .filter((c) => c && (c.de === id || c.vers === id));

  /** Un tracé EST le tracé proposé quand il décrit le MÊME trajet (sommets alignés retirés, au centimètre) que celui
   *  que `pointsProposes` rend AUJOURD'HUI pour sa liaison. Tout autre tracé — dessiné point par point, saisi, ou
   *  proposé sur un toit qui a changé depuis au point que le trajet n'est plus le même — n'est pas reconnu : il
   *  n'est jamais remplacé, et l'écran n'en dit que ce qu'il sait (rien sur qui l'a tracé). */
  function estTraceProposee(c: CheminementElectrique): boolean {
    const pts = c.points ?? [];
    if (c.origine !== 'plan' || pts.length < 2 || c.longueurSaisieM != null) return false;
    const p = pointsProposes({ cote: c.cote, de: c.de, vers: c.vers });
    if (!p.ok) return false;
    const o = origine();
    return memeTrajet(p.points.map(([lng, lat]) => versScene(lng, lat, o)), pts.map((q) => versScene(q.lng, q.lat, o)));
  }

  /** Le bout d'un tracé côté organe tombe-t-il sur l'organe ? Un tracé SAISI (sans points) n'a pas de bout à juger. */
  function aboutit(c: CheminementElectrique, organe: EquipementElectrique): boolean {
    const pts = c.points ?? [];
    if (pts.length < 2) return true;
    const bout = c.vers === organe.id ? pts[pts.length - 1] : pts[0];
    const [e, n] = versScene(bout.lng, bout.lat, [organe.lng, organe.lat]);
    return Math.hypot(e, n) <= TOLERANCE_ABOUTISSEMENT_M;
  }

  /** Les pans qui portent des modules VENDUS : chacun envoie son câble DC à l'onduleur (un tracé par pan). Un pan
   *  « existant » (installation déjà en place, ACAL510 — hors de la vente comme dans `calepinage/services/devis.py`)
   *  n'en reçoit pas : ni tracé proposé, ni « tracé partiel ». */
  const pansAModules = (): string[] => (ctx.areas ?? [])
    .filter((a) => a.id && !a.existant && (a.renderPlan?.grid?.panels?.length ?? 0) > 0).map((a) => a.id);

  /** Un pan est SERVI quand un tracé DC le relie à UN onduleur, quel qu'il soit : avec deux onduleurs, le pan câblé
   *  au premier n'envoie pas un second câble au deuxième (deux métrés pour un seul câble). */
  const panServi = (pan: string): boolean => {
    const onduleurs = new Set(((document()?.equipements ?? []) as EquipementElectrique[])
      .filter((e) => e?.type === 'onduleur').map((e) => e.id));
    return ((document()?.cheminements ?? []) as CheminementElectrique[]).some((c) => c && c.cote === 'dc'
      && ((c.de === pan && onduleurs.has(c.vers)) || (c.vers === pan && onduleurs.has(c.de))));
  };

  function etatTraces(id: string): EtatTracesOrgane {
    const organe = ((document()?.equipements ?? []) as EquipementElectrique[]).find((x) => x.id === id) ?? null;
    const proposes: string[] = [];
    const autres: string[] = [];
    const decales: string[] = [];
    const traces = tracesDe(id);
    for (const c of traces) {
      if (estTraceProposee(c)) { proposes.push(c.id); continue; }
      autres.push(c.id);
      if (organe && !aboutit(c, organe)) decales.push(c.id);
    }
    const pansSansTrace = organe ? pansAModules().filter((pan) => !panServi(pan)) : [];
    return { proposes, autres, decales, pansSansTrace };
  }

  /** Repropose les liaisons PROPOSÉES de l'organe déplacé relevées avant le geste (jamais celles d'un autre
   *  onduleur), puis propose le tracé DC de chaque pan à modules qu'AUCUN onduleur ne sert encore. Un tracé non
   *  reconnu n'est jamais touché, ni sa liaison reproposée. */
  function suivreTrace(id: string, proposesAvant: readonly CheminementElectrique[]): SuiviTrace {
    const autres = tracesDe(id).filter((c) => !proposesAvant.some((p) => p.id === c.id));
    const liaisons: { cote: CoteCheminement; de: string; vers: string }[] = proposesAvant
      .map((c) => ({ cote: c.cote, de: c.de, vers: c.vers }))
      .filter((l) => !autres.some((c) => c.cote === l.cote && c.de === l.de && c.vers === l.vers));
    for (const pan of pansAModules()) {
      if (!panServi(pan) && !tracesDe(id).some((c) => c.de === pan || c.vers === pan)) liaisons.push({ cote: 'dc', de: pan, vers: id });
    }
    const traces: string[] = [];
    let refusTrace: RefusElectrique | null = null;
    if (!pansAModules().length && !tracesDe(id).length) {
      refusTrace = refuser('electrical.cheminements.de', 'Aucun pan ne porte de modules : le tracé du câble ne peut pas être proposé.');
    }
    for (const l of liaisons) {
      const r = proposerCheminement(l);
      if (r.ok) traces.push(r.cheminement.id); else refusTrace = r;
    }
    // Un tracé réussi APRÈS un refus effaçait le refus : le geste le garde, pour que le toucher de la carte
    // (`dernierRefus`) et les flèches (`refusTrace`) disent la même chose.
    if (refusTrace) refus = refusTrace;
    return { traces, refusTrace };
  }

  function deplacerEtSuivre(id: string, lngLat: LngLat): (PoseReussie & SuiviTrace) | RefusElectrique {
    if (lectureSeule) return refusLecture();
    const cible = ((document()?.equipements ?? []) as EquipementElectrique[]).find((e) => e.id === id);
    if (!cible || !Array.isArray(lngLat) || !nombreFini(lngLat[0]) || !nombreFini(lngLat[1])) return deplacer(id, lngLat) as RefusElectrique;
    const proposesAvant = tracesDe(id).filter(estTraceProposee).map((c) => ({ ...c }));
    return enUnGeste(() => {
      const d = deplacer(id, lngLat) as PoseReussie;
      return { ...d, ...suivreTrace(id, proposesAvant) };
    });
  }

  function poserEtSuivre(lngLat: LngLat): (PoseReussie & SuiviTrace) | RefusElectrique {
    if (lectureSeule) return refusLecture();
    if (!arme || !Array.isArray(lngLat) || !nombreFini(lngLat[0]) || !nombreFini(lngLat[1])) return poser(lngLat);
    return enUnGeste(() => {
      const p = poser(lngLat) as PoseReussie;
      arme = null; // désarmé AVANT que l'écran soit prévenu (fin du geste) : il lit un geste achevé
      suivreALaPose = false;
      return { ...p, ...suivreTrace(p.equipement.id, []) };
    });
  }

  function pousser(id: string, dEstM: number, dNordM: number): (PoseReussie & SuiviTrace) | RefusElectrique {
    if (lectureSeule) return refusLecture();
    const cible = ((document()?.equipements ?? []) as EquipementElectrique[]).find((e) => e.id === id);
    if (!cible || !nombreFini(dEstM) || !nombreFini(dNordM)) return deplacer(id, [Number.NaN, Number.NaN]) as RefusElectrique;
    const cosLat = Math.cos(cible.lat * DEG2RAD);
    return deplacerEtSuivre(id, [cible.lng + dEstM / (DEG2M * cosLat), cible.lat + dNordM / DEG2M]);
  }

  /** Retire l'organe ET ses tracés PROPOSÉS, en un cran ; les autres tracés restent (rendus par leur id). */
  function retirerAvecTraces(id: string): { ok: boolean; tracesGardees: string[] } {
    if (lectureSeule) { refusLecture(); return { ok: false, tracesGardees: [] }; }
    if (!((document()?.equipements ?? []) as EquipementElectrique[]).some((e) => e.id === id)) return { ok: false, tracesGardees: [] };
    const proposes = tracesDe(id).filter(estTraceProposee).map((c) => c.id);
    const tracesGardees = tracesDe(id).map((c) => c.id).filter((c) => !proposes.includes(c));
    enUnGeste(() => {
      for (const c of proposes) retirer(c);
      retirer(id);
    });
    return { ok: true, tracesGardees };
  }

  function saisirCheminement(saisie: {
    cote: CoteCheminement;
    de: string;
    vers: string;
    longueurM: number;
  }): CheminementReussi | RefusElectrique {
    const demarre = demarrerCheminement({ cote: saisie?.cote, de: saisie?.de });
    if (demarre !== true) return demarre;
    const arrivee = texteOuVide(saisie?.vers).trim();
    if (!idsResolvables().has(arrivee)) {
      const depart = saisie.de;
      enCours = null;
      return refuser(
        'electrical.cheminements.vers',
        `Le cheminement part de « ${depart} » vers « ${arrivee || '(vide)'} », qui n'existe ni `
        + 'parmi les équipements ni parmi les pans de ce plan : reliez-le à un organe posé, ou '
        + 'retirez-le — un tronçon qui ne relie rien fausse le métré sans jamais se voir.',
      );
    }
    if (!nombreFini(saisie?.longueurM) || saisie.longueurM <= 0) {
      enCours = null;
      return refuser(
        'electrical.cheminements.longueurSaisieM',
        'Saisissez la longueur du tronçon en mètres (descente verticale, traversée de mur, '
        + 'passage en gaine) : elle ne peut pas être devinée depuis le plan, qui ne la porte pas.',
      );
    }
    photographier();
    enCours = null;
    const doc = documentEcrivable();
    const liste = doc.cheminements as CheminementElectrique[];
    const cheminement: CheminementElectrique = {
      id: prochainId('ch', liste),
      cote: saisie.cote,
      de: texteOuVide(saisie.de).trim(),
      vers: arrivee,
      points: [],
      longueurSaisieM: saisie.longueurM,
      origine: 'saisie',
    };
    liste.push(cheminement);
    refus = null;
    rafraichir();
    return { ok: true, cheminement };
  }

  // ── l'annulation ────────────────────────────────────────────────────────

  function annuler(): boolean {
    if (lectureSeule) return false;
    // `canUndo()` tranche AVANT l'appel : une photo qui vaut `null` (le plan
    // n'avait pas encore de couche électrique) est un état à restaurer, pas une
    // pile vide — sans cette garde, le tout premier geste serait inannulable.
    if (!histoire.canUndo()) return false;
    ctx.electrical = histoire.undo(copieDocument(document())) ?? null;
    selectionne = null;
    enCours = null;
    deplacementVise = null; // ACAL1317
    rafraichir();
    return true;
  }

  function retablir(): boolean {
    if (lectureSeule) return false;
    if (!histoire.canRedo()) return false;
    ctx.electrical = histoire.redo(copieDocument(document())) ?? null;
    selectionne = null;
    enCours = null;
    deplacementVise = null; // ACAL1317
    rafraichir();
    return true;
  }

  // ── CALX221 — le calque ─────────────────────────────────────────────────

  function setLayerState(id: string, patch: { visible: boolean; opacite?: number }): boolean {
    if (id !== ID_CALQUE_ELECTRIQUE) return false;
    etat = {
      visible: patch?.visible !== false,
      opacite: nombreFini(patch?.opacite) ? Math.max(0, Math.min(1, patch.opacite as number)) : etat.opacite,
    };
    appliquerEtat();
    (groupe.userData.siEtatChange as (() => void) | undefined)?.(); // T4-X7-015 — la scène redit étiquettes « Chaîne n » et teintes
    return true;
  }

  rafraichir();

  return {
    idCalque: ID_CALQUE_ELECTRIQUE,
    groupe,
    rafraichir,
    avertissements: () => [...ignores],
    // CALX221 — un calque n'est PROPOSÉ que s'il existe : sans couche électrique
    // au document, il n'y a rien à allumer ni à éteindre.
    calqueDisponible: () => document() != null || (ctx.affectationColoration?.labelByModule?.size ?? 0) > 0, // T4-X7-015 — ou des chaînes formées
    setLayerState,
    etatCalque: () => ({ ...etat }),
    armerPose: (type, options) => {
      deplacementVise = null; // ACAL1317 — poser et déplacer ne s'arment pas ensemble
      if (type === null) {
        arme = null;
        suivreALaPose = false;
        return true;
      }
      if (!estTypeEquipement(type) || lectureSeule) return false;
      arme = type;
      suivreALaPose = options?.suivreTrace === true;
      return true;
    },
    typeArme: () => arme,
    armerDeplacement: (id) => {
      if (id === null) { deplacementVise = null; return true; }
      if (lectureSeule) return false;
      if (!((document()?.equipements ?? []) as EquipementElectrique[]).some((e) => e.id === id)) return false;
      arme = null;
      suivreALaPose = false;
      deplacementVise = id;
      return true;
    },
    deplacementArme: () => deplacementVise,
    pasDeplacementM: PAS_DEPLACEMENT_ORGANE_M,
    pousser,
    retirerAvecTraces,
    etatTraces,
    ecouter: (f) => { ecouteurs.add(f); return () => { ecouteurs.delete(f); }; },
    definirLectureSeule: (oui) => {
      lectureSeule = oui === true;
      if (lectureSeule) { arme = null; suivreALaPose = false; deplacementVise = null; enCours = null; }
    },
    lectureSeule: () => lectureSeule,
    poser,
    clicCarte: (lngLat) => {
      if (deplacementVise) { // ACAL1317 — le clic déplace l'organe visé, jamais n'en pose un second
        const vise = deplacementVise;
        deplacementVise = null; // désarmé AVANT que l'écran soit prévenu ; un refus réarme (nommé)
        if (!deplacerEtSuivre(vise, lngLat).ok) deplacementVise = vise;
        return true;
      }
      if (!arme) return false;
      if (suivreALaPose) {
        poserEtSuivre(lngLat); // un refus garde l'armement (nommé)
        return true;
      }
      if (poser(lngLat).ok) arme = null; // un clic = un organe ; un refus garde l'armement (nommé)
      return true;
    },
    selectionner: (id) => {
      if (id === null) {
        selectionne = null;
        return true;
      }
      const existe = (document()?.equipements ?? []).some((e) => e.id === id);
      if (existe) selectionne = id;
      return existe;
    },
    selection: () => selectionne,
    deplacer,
    retirer,
    demarrerCheminement,
    ajouterPointCheminement,
    proposerCheminement,
    pointsEnCours: () => (enCours ? enCours.points.map((p) => ({ ...p })) : []),
    terminerCheminement,
    abandonnerCheminement,
    saisirCheminement,
    dernierRefus: () => (refus ? { ...refus } : null),
    annuler,
    retablir,
    profondeurHistorique: () => histoire.size(),
    documentElectrique: () => document(),
    // CROCHET D'EXPORT — le document sérialisé de l'atelier repart avec sa
    // couche électrique. Rien n'est écrit tant qu'aucun organe n'est posé : un
    // document v2 déjà enregistré reste identique, octet pour octet.
    ecrireDansDocument: <T extends object>(doc: T): T => {
      const couche = copieDocument(document());
      if (!couche) return doc;
      return { ...doc, electrical: couche };
    },
  };
}
