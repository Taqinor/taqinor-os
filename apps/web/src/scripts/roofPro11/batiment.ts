/**
 * CALX100 / CALX101 / CALX102 — LE BÂTIMENT VIENT DU DOCUMENT, PAS D'UNE CONSTANTE.
 *
 * Constat que ces trois tâches corrigent :
 *  - la 3D extrudait TOUJOURS `FLOORS × FLOOR_HEIGHT_M` (6 m), quelle que soit la
 *    hauteur relevée sur place ; la saisie CAL60 vivait dans une `Map` locale de
 *    `shadingUi.ts`, n'influençait QUE l'ombrage et n'était JAMAIS sérialisée —
 *    rouvrir le dossier la perdait ;
 *  - `parapetM` n'était qu'une contrainte de recul : un toit-terrasse à acrotère
 *    haut se dessinait comme une dalle nue, sans relevé ni ombre de rive ;
 *  - un `chien_assis` n'était qu'une boîte POSÉE sur la dalle : aucun percement du
 *    plan de toiture n'existait.
 *
 * CE MODULE EST PUR : aucune lecture DOM, aucun réseau, aucun état global. Il prend
 * ce que le DOCUMENT porte (`buildings[]`, contrat CALX84 — `$defs/building` de
 * `roof_layout_v2.schema.json`) et rend des PARAMÈTRES ou des GÉOMÉTRIES ; `scene3d.ts`
 * ne fait que les attacher, `shadingUi.ts` ne fait que les saisir, `prefill.ts` ne fait
 * que les écrire.
 *
 * DISCIPLINE DES CHIFFRES (D-CALX 7, « checked facts only ») :
 *  - une hauteur de bâtiment est SAISIE et porte obligatoirement sa `source`, ou elle
 *    est ABSENTE. « Absente » n'est ni 0 m ni 6 m ;
 *  - quand elle est absente, la 3D continue de dessiner quelque chose (un volume vide
 *    ne se lit pas), mais à une HAUTEUR DE DESSIN nommée, annoncée comme une hypothèse,
 *    et jamais présentée comme une mesure ;
 *  - `etages` × `hauteurEtageM` est une information d'ÉCRAN : aucune hauteur n'en est
 *    déduite en silence (le schéma CALX84 l'interdit explicitement) ;
 *  - l'épaisseur du bandeau d'acrotère est le retrait d'acrotère DÉJÀ RÉGLÉ (`parapetM`,
 *    CAL76) — aucune épaisseur n'est inventée ;
 *  - la pente d'une lucarne est DÉRIVÉE de deux valeurs saisies (sa hauteur et son
 *    emprise) et la dérivation est NOMMÉE ; aucune pente forfaitaire n'existe ici.
 */
import * as THREE from 'three';
import { FLOORS, FLOOR_HEIGHT_M, DEG2RAD, DEG2M } from './constants';
import { type LngLat } from '../../lib/roof';
import { type Obstacle } from '../../lib/obstacles';

// ═══════════════ CALX84 — LE BÂTIMENT TEL QUE LE DOCUMENT LE DÉCRIT ═══════════════

/**
 * Un bâtiment du site — miroir EXACT de `$defs/building` (contrat CALX84). Il ne porte
 * que ce qu'un humain a RELEVÉ ou SAISI. `null` = non renseigné, ce qui n'est pas 0.
 */
export interface Batiment {
  /** Identifiant STABLE dans ce document — celui que `zones[].buildingId` (CAL59) désigne. */
  id: string;
  /** Libellé FRANÇAIS affiché. Absent = le bâtiment n'est désigné que par son `id`. */
  label?: string;
  /** Hauteur (m) SAISIE ou relevée. `null`/absent = NON RENSEIGNÉE. */
  hauteurM?: number | null;
  /** Nombre d'étages SAISI. Ne fabrique JAMAIS une hauteur (contrat CALX84). */
  etages?: number | null;
  /** Hauteur d'un étage (m), SAISIE. Même discipline que `etages`. */
  hauteurEtageM?: number | null;
  /** D'OÙ vient la hauteur, en clair. OBLIGATOIRE dès que `hauteurM` porte un nombre. */
  source?: string | null;
  /**
   * CALX101 — hauteur (m) du RELEVÉ D'ACROTÈRE au-dessus de la dalle, SAISIE. Clé
   * ADDITIVE : `$defs/building` accepte `additionalProperties`, donc un document qui la
   * porte reste valide octet pour octet et un document qui l'ignore ne change pas. Absente
   * = aucun bandeau d'acrotère n'est dessiné (l'atelier d'aujourd'hui). Jamais déduite de
   * `parapetM` : le retrait dit À QUELLE DISTANCE on pose, pas À QUELLE HAUTEUR ça monte.
   */
  hauteurAcrotereM?: number | null;
}

/**
 * CALX100 — identifiant CONVENTIONNEL du bâtiment d'un pan qui n'en nomme aucun
 * (`buildingId` absent, CAL59). Le contrat exige un `id` non vide ; celui-ci regroupe
 * EXACTEMENT ce que la `Map` de CAL60 regroupait déjà sous sa clé vide — ni plus, ni
 * moins. Ce n'est pas un bâtiment relevé, c'est une convention de document, et l'écran
 * le nomme comme la liste des pans le nomme déjà (« Bâtiment sans id », `zones.ts`).
 */
export const ID_BATIMENT_SANS_ID = 'bat-sans-id';

/** L'identifiant de bâtiment d'un pan : celui qu'il nomme, sinon la convention ci-dessus. */
export function idBatimentDuPan(buildingId?: string | null): string {
  const t = (buildingId ?? '').trim();
  return t.length ? t : ID_BATIMENT_SANS_ID;
}

/** Le bâtiment décrit par le document pour cet identifiant, ou `null` (non décrit). */
export function batimentPourId(
  batiments: readonly Batiment[] | null | undefined,
  id: string,
): Batiment | null {
  if (!Array.isArray(batiments)) return null;
  return batiments.find((b) => b && b.id === id) ?? null;
}

/** Le bâtiment du PAN (via `buildingId`, CAL59), ou `null` s'il n'est pas décrit. */
export function batimentDuPan(
  batiments: readonly Batiment[] | null | undefined,
  buildingId?: string | null,
): Batiment | null {
  return batimentPourId(batiments, idBatimentDuPan(buildingId));
}

// ═══════════════ CALX100 — LA HAUTEUR D'EXTRUSION, ET D'OÙ ELLE VIENT ═══════════════

/**
 * Hauteur de DESSIN (m) utilisée quand AUCUNE hauteur n'est saisie. Ce n'est pas une
 * constante d'ingénierie neuve : c'est exactement le repli historique déjà affiché comme
 * une hypothèse par CAL60 (`FLOORS × FLOOR_HEIGHT_M`, `constants.ts`). Convention de
 * DESSIN : elle permet de dessiner un volume plutôt qu'une dalle qui flotte, et elle est
 * TOUJOURS annoncée comme une hypothèse — jamais reprise dans un chiffre engageant.
 */
export const HAUTEUR_DESSIN_M = FLOORS * FLOOR_HEIGHT_M;

/** Un nombre fini et strictement positif ? (le seul « saisi » qu'on accepte). */
function estMesure(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v > 0;
}

const fmt1 = (n: number): string =>
  n.toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** D'où vient la hauteur réellement extrudée. */
export interface HauteurExtrusion {
  /** Hauteur (m) que la 3D extrude. */
  hauteurM: number;
  /** `saisie` = relevée sur site et tracée ; `dessin` = convention annoncée. */
  origine: 'saisie' | 'dessin';
  /** La provenance SAISIE (CALX84 `source`), ou `null` en hauteur de dessin. */
  source: string | null;
  /** Phrase FRANÇAISE prête à afficher — un chiffre ne part jamais muet. */
  mention: string;
  /** Ce qui manque, NOMMÉ. Vide quand la hauteur est saisie et tracée. */
  nonMesure: string[];
}

/**
 * CALX100 — la hauteur que la 3D extrude pour ce bâtiment.
 *
 * Saisie ET tracée (`source` non vide) ⇒ elle pilote l'extrusion. Sinon ⇒ hauteur de
 * DESSIN, annoncée comme une hypothèse, et ce qui manque est nommé (« hauteur »,
 * « provenance de la hauteur ») — jamais un 6 m muet qui se lirait comme une mesure.
 */
export function hauteurExtrusion(batiment?: Batiment | null): HauteurExtrusion {
  const h = batiment?.hauteurM;
  const src = typeof batiment?.source === 'string' ? batiment.source.trim() : '';
  if (estMesure(h) && src.length) {
    return {
      hauteurM: h,
      origine: 'saisie',
      source: src,
      mention: `Hauteur saisie : ${fmt1(h)} m (${src}).`,
      nonMesure: [],
    };
  }
  const nonMesure: string[] = [];
  if (!estMesure(h)) nonMesure.push('hauteur du bâtiment');
  else nonMesure.push('provenance de la hauteur (source)');
  return {
    hauteurM: HAUTEUR_DESSIN_M,
    origine: 'dessin',
    source: null,
    mention:
      `Hauteur de dessin : ${fmt1(HAUTEUR_DESSIN_M)} m (hypothèse, ${FLOORS} étages) — ` +
      `${nonMesure[0]} non renseignée : saisissez-la pour un volume et un ombrage exacts.`,
    nonMesure,
  };
}

/**
 * CALX100 — la mention d'ÉCRAN du couple étages × hauteur d'étage, ou `null` si l'un des
 * deux manque. C'est une LECTURE, jamais une hauteur de remplacement : le contrat CALX84
 * interdit d'écrire ce produit à la place de `hauteurM`, et cette fonction ne l'écrit nulle
 * part — elle se contente de le DIRE, y compris quand il contredit la hauteur saisie (deux
 * valeurs incohérentes sont un fait que l'écran montre, pas une erreur qu'un calcul efface).
 */
export function mentionEtages(batiment?: Batiment | null): string | null {
  const n = batiment?.etages;
  const he = batiment?.hauteurEtageM;
  if (typeof n !== 'number' || !Number.isFinite(n) || n <= 0) return null;
  if (!estMesure(he)) return null;
  return `${n} étage(s) × ${fmt1(he)} m = ${fmt1(n * he)} m saisis — information d'écran, la hauteur extrudée reste celle du champ « hauteur ».`;
}

// ═══════════════ CALX100 — SAISIE, NORMALISATION, SÉRIALISATION ═══════════════

/** Ce qu'un panneau « Bâtiment » saisit. `null` efface explicitement, `undefined` ne touche à rien. */
export interface SaisieBatiment {
  label?: string | null;
  hauteurM?: number | null;
  etages?: number | null;
  hauteurEtageM?: number | null;
  source?: string | null;
  hauteurAcrotereM?: number | null;
}

/** Le résultat d'une saisie : la liste NEUVE, et les refus NOMMÉS par champ fautif. */
export interface ResultatSaisie {
  batiments: Batiment[];
  /** Refus, chacun désignant LE CHAMP fautif (règle fondateur : jamais un refus générique). */
  refus: Array<{ champ: keyof SaisieBatiment; message: string }>;
}

/**
 * CALX100 — applique une saisie au bâtiment `id` et rend une liste NEUVE (jamais de
 * mutation en place : l'appelant remplace `ctx.batiments`, ce qui rend le geste
 * photographiable par l'historique de l'atelier).
 *
 * Le SEUL refus possible est celui que le contrat impose : une hauteur sans provenance.
 * Il nomme le champ (`source`), il ne se contente pas d'un « non enregistré » (règle
 * fondateur 08/09). Une valeur vide/non finie EFFACE le champ — elle ne le met pas à 0.
 */
export function appliquerSaisie(
  batiments: readonly Batiment[] | null | undefined,
  id: string,
  saisie: SaisieBatiment,
): ResultatSaisie {
  const liste = (Array.isArray(batiments) ? batiments : []).map((b) => ({ ...b }));
  const idx = liste.findIndex((b) => b && b.id === id);
  const courant: Batiment = idx >= 0 ? liste[idx] : { id };
  const suivant: Batiment = { ...courant, id };

  const poserNombre = (
    champ: 'hauteurM' | 'etages' | 'hauteurEtageM' | 'hauteurAcrotereM',
    v: number | null | undefined,
  ) => {
    if (v === undefined) return;
    suivant[champ] = estMesure(v) ? v : null;
  };
  poserNombre('hauteurM', saisie.hauteurM);
  poserNombre('hauteurEtageM', saisie.hauteurEtageM);
  poserNombre('hauteurAcrotereM', saisie.hauteurAcrotereM);
  if (saisie.etages !== undefined) {
    const n = saisie.etages;
    suivant.etages = typeof n === 'number' && Number.isFinite(n) && n > 0 ? Math.round(n) : null;
  }
  if (saisie.source !== undefined) {
    const s = typeof saisie.source === 'string' ? saisie.source.trim() : '';
    suivant.source = s.length ? s : null;
  }
  if (saisie.label !== undefined) {
    const l = typeof saisie.label === 'string' ? saisie.label.trim() : '';
    if (l.length) suivant.label = l;
    else delete suivant.label;
  }

  const refus: ResultatSaisie['refus'] = [];
  if (estMesure(suivant.hauteurM) && !(typeof suivant.source === 'string' && suivant.source.trim().length)) {
    refus.push({
      champ: 'source',
      message:
        'Provenance obligatoire : une hauteur de bâtiment n’est engageable que si l’on dit d’où elle vient ' +
        '(« mesurée au télémètre », « lue sur le permis », « déclarée par le client »…).',
    });
    // La hauteur n'est PAS écrite sans sa provenance — on garde celle d'avant la saisie.
    suivant.hauteurM = estMesure(courant.hauteurM) ? courant.hauteurM : null;
    suivant.source = typeof courant.source === 'string' ? courant.source : null;
  }

  if (idx >= 0) liste[idx] = suivant;
  else liste.push(suivant);
  return { batiments: liste, refus };
}

/**
 * CALX84 — normalise UN bâtiment pour l'écriture dans le document : identifiant non vide,
 * mesures finies et strictement positives ou `null`, et — la règle du contrat — une hauteur
 * n'est JAMAIS écrite sans sa provenance (elle repart à `null` avec elle, plutôt que de
 * produire un document que `valider_document` refuserait en nommant `source`).
 */
export function normaliserBatiment(brut: unknown): Batiment | null {
  const b = brut as Batiment | null;
  if (!b || typeof b !== 'object') return null;
  const id = typeof b.id === 'string' ? b.id.trim() : '';
  if (!id) return null;
  const source = typeof b.source === 'string' && b.source.trim().length ? b.source.trim() : null;
  const hauteurM = estMesure(b.hauteurM) && source ? b.hauteurM : null;
  const etages =
    typeof b.etages === 'number' && Number.isFinite(b.etages) && b.etages >= 0 ? Math.round(b.etages) : null;
  const out: Batiment = {
    id,
    hauteurM,
    etages,
    hauteurEtageM: estMesure(b.hauteurEtageM) ? b.hauteurEtageM : null,
    source: hauteurM != null ? source : null,
  };
  if (typeof b.label === 'string' && b.label.trim().length) out.label = b.label.trim();
  // CALX101 — additive : jamais émise quand aucune hauteur d'acrotère n'est saisie.
  if (estMesure(b.hauteurAcrotereM)) out.hauteurAcrotereM = b.hauteurAcrotereM;
  return out;
}

/** Un bâtiment qui ne porte AUCUNE mesure et aucun libellé n'apprend rien au document. */
function batimentVide(b: Batiment): boolean {
  return (
    b.hauteurM == null &&
    b.etages == null &&
    b.hauteurEtageM == null &&
    b.hauteurAcrotereM == null &&
    !b.label
  );
}

/** CALX84 — la liste prête à écrire : entrées normalisées, entrées vides écartées. */
export function serialiserBatiments(list: readonly Batiment[] | null | undefined): Batiment[] {
  if (!Array.isArray(list)) return [];
  const out: Batiment[] = [];
  const vus = new Set<string>();
  for (const brut of list) {
    const b = normaliserBatiment(brut);
    if (!b || vus.has(b.id) || batimentVide(b)) continue;
    vus.add(b.id);
    out.push(b);
  }
  return out;
}

/**
 * CALX100 — LE fragment que `serializeLayout` étale (`...`) en fin de bloc d'émission :
 * la clé `buildings` n'existe QUE si au moins un bâtiment apprend quelque chose au
 * document. Sinon l'objet rendu est vide et le document reste identique octet pour octet.
 */
export function emettreBatiments(list: readonly Batiment[] | null | undefined): { buildings?: Batiment[] } {
  const buildings = serialiserBatiments(list);
  return buildings.length ? { buildings } : {};
}

/**
 * CALX100 — relit `buildings[]` d'un document sérialisé (réhydratation d'un devis rouvert).
 * Mêmes garde-fous qu'à l'écriture : un JSON douteux rend une liste vide plutôt que de
 * casser l'ouverture, et aucune hauteur sans provenance n'est reprise. Accepte le document
 * complet ou déjà le tableau brut.
 */
export function lireBatiments(json: unknown): Batiment[] {
  const raw = (json as { buildings?: unknown } | null | undefined)?.buildings ?? json;
  return serialiserBatiments(raw as readonly Batiment[] | null | undefined);
}

// ═══════════════ GÉOMÉTRIE D'ANNEAU (partagée acrotère / lucarne) ═══════════════

/** Aire SIGNÉE (m²) d'un anneau ENU — positif = sens trigonométrique. */
export function aireSigneeM2(ring: readonly [number, number][]): number {
  let s = 0;
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    s += x1 * y2 - x2 * y1;
  }
  return s / 2;
}

/** Le point (x, y) est-il STRICTEMENT dans l'anneau ? (lancer de rayon, anneau fermé implicitement.) */
export function dansAnneau(ring: readonly [number, number][], x: number, y: number): boolean {
  let dedans = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const traverse = yi > y !== yj > y;
    if (traverse && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) dedans = !dedans;
  }
  return dedans;
}

/**
 * CALX101 — anneau RENTRÉ de `epaisseurM` (offset par bissectrices). Sert de TROU au
 * bandeau d'acrotère : entre l'anneau du tracé et celui-ci, il reste exactement la bande
 * que le retrait d'acrotère (`parapetM`, CAL76) réserve déjà — aucune épaisseur inventée.
 *
 * Rend `null` quand le rentrant n'est pas géométriquement tenable (moins de 3 sommets,
 * épaisseur nulle, ou tracé trop étroit : l'anneau s'auto-recouvrirait). Dans ce cas
 * AUCUN bandeau n'est dessiné — on ne devine pas une forme qui ne tient pas.
 */
export function anneauInterieur(
  ring: readonly [number, number][],
  epaisseurM: number,
): [number, number][] | null {
  if (ring.length < 3 || !estMesure(epaisseurM)) return null;
  const aire = aireSigneeM2(ring);
  if (!Number.isFinite(aire) || aire === 0) return null;
  const sens = aire > 0 ? 1 : -1; // normale rentrante = rotation -90° × sens
  const out: [number, number][] = [];
  const n = ring.length;
  for (let i = 0; i < n; i++) {
    const p = ring[i];
    const a = ring[(i - 1 + n) % n];
    const b = ring[(i + 1) % n];
    const d1x = p[0] - a[0];
    const d1y = p[1] - a[1];
    const d2x = b[0] - p[0];
    const d2y = b[1] - p[1];
    const l1 = Math.hypot(d1x, d1y);
    const l2 = Math.hypot(d2x, d2y);
    if (l1 === 0 || l2 === 0) return null;
    // Normales RENTRANTES unitaires des deux arêtes : l'intérieur d'un anneau parcouru
    // dans le sens trigonométrique (`sens` = +1) est À GAUCHE de la marche, soit (−dy, dx).
    const n1x = (-sens * d1y) / l1;
    const n1y = (sens * d1x) / l1;
    const n2x = (-sens * d2y) / l2;
    const n2y = (sens * d2x) / l2;
    let bx = n1x + n2x;
    let by = n1y + n2y;
    const lb = Math.hypot(bx, by);
    if (lb < 1e-9) return null; // arêtes opposées : pointe dégénérée
    bx /= lb;
    by /= lb;
    const cos = bx * n1x + by * n1y;
    if (cos < 0.2) return null; // angle trop aigu : le rentrant explose
    out.push([p[0] + (bx * epaisseurM) / cos, p[1] + (by * epaisseurM) / cos]);
  }
  const aireInt = aireSigneeM2(out);
  // Même sens ET strictement plus petit : sinon le tracé est plus étroit que l'épaisseur.
  if (!Number.isFinite(aireInt) || Math.sign(aireInt) !== Math.sign(aire) || Math.abs(aireInt) >= Math.abs(aire)) {
    return null;
  }
  return out;
}

// ═══════════════ CALX101 — LE BANDEAU D'ACROTÈRE, COMME UN VOLUME ═══════════════

/** Le bandeau d'acrotère à dessiner, avec sa provenance — ou l'absence, nommée. */
export interface VolumeAcrotere {
  /** Hauteur SAISIE (m) du relevé, au-dessus de la dalle. */
  hauteurM: number;
  /** Épaisseur (m) = le retrait d'acrotère RÉGLÉ (`parapetM`, CAL76). Jamais inventée. */
  epaisseurM: number;
  /** Phrase française prête à afficher. */
  mention: string;
}

/**
 * CALX101 — le bandeau d'acrotère du bâtiment, ou `null`.
 *
 * DEUX conditions, toutes deux issues du document : le retrait d'acrotère est réglé
 * (`parapetM > 0`, CAL76) ET une hauteur d'acrotère est SAISIE dans le panneau Bâtiment.
 * L'une manque ⇒ `null` ⇒ la scène garde exactement les maillages d'aujourd'hui.
 */
export function acrotereDuBatiment(
  batiment: Batiment | null | undefined,
  parapetM: number | null | undefined,
): VolumeAcrotere | null {
  const h = batiment?.hauteurAcrotereM;
  if (!estMesure(h) || !estMesure(parapetM)) return null;
  return {
    hauteurM: h,
    epaisseurM: parapetM,
    mention: `Acrotère saisi : ${fmt1(h)} m de relevé sur ${fmt1(parapetM)} m de retrait réglé.`,
  };
}

/**
 * CALX101 — le MAILLAGE du bandeau d'acrotère : un volume périphérique (anneau extrudé)
 * qui monte de `volume.hauteurM` au-dessus de la dalle et PROJETTE une vraie ombre
 * (`castShadow`), ce qu'une simple contrainte de recul ne pouvait pas faire.
 *
 * `null` quand il n'y a rien à dessiner (aucun volume saisi, tracé trop étroit pour le
 * rentrant) : l'appelant n'ajoute alors rien et la scène reste celle d'aujourd'hui.
 */
export function construireAcrotere(
  ring: readonly [number, number][],
  volume: VolumeAcrotere | null,
  baseZ: number,
  dim: boolean,
): THREE.Mesh | null {
  if (!volume || ring.length < 3 || !Number.isFinite(baseZ)) return null;
  const interieur = anneauInterieur(ring, volume.epaisseurM);
  if (!interieur) return null;
  const shape = new THREE.Shape();
  ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();
  const trou = new THREE.Path();
  interieur.forEach(([x, y], i) => (i === 0 ? trou.moveTo(x, y) : trou.lineTo(x, y)));
  trou.closePath();
  shape.holes.push(trou);
  const geo = new THREE.ExtrudeGeometry(shape, { depth: volume.hauteurM, bevelEnabled: false });
  // Même teinte que le bâtiment (continuité du volume) ; subduée pour un pan non actif,
  // exactement comme les murs (`buildZoneMeshes`).
  const mat = new THREE.MeshStandardMaterial({
    color: dim ? 0x9aa3b4 : 0xe2e7f2,
    roughness: 0.85,
    metalness: 0,
    transparent: dim,
    opacity: dim ? 0.55 : 1,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = 'rp11-acrotere';
  mesh.position.z = baseZ;
  mesh.castShadow = true; // l'ombre de rive : la raison d'être du relevé
  mesh.receiveShadow = true;
  return mesh;
}

// ═══════════════ CALX102 — LA LUCARNE PERCE LE PAN ═══════════════

/** Une lucarne (chien-assis) prête à dessiner, dans le repère ENU de la scène. */
export interface Lucarne {
  id: string;
  /** Centre ENU (m) dans le repère de la scène (offset de zone déjà appliqué). */
  centre: [number, number];
  /** Étendue NORD-SUD (m), SAISIE. */
  longueurM: number;
  /** Étendue EST-OUEST (m), SAISIE. */
  largeurM: number;
  /** Hauteur de faîtage (m) au-dessus du plan du pan, SAISIE (CAL66 `heightM`). */
  hauteurM: number;
  /** Pente (°) des deux versants — DÉRIVÉE de la hauteur et de l'emprise saisies. */
  penteDeg: number;
  /** D'où vient `penteDeg`, en clair : la dérivation est nommée, jamais muette. */
  provenancePente: string;
  /** L'emprise, en ENU, dans l'ordre du contour. */
  emprise: [number, number][];
}

/**
 * CALX102 — les lucarnes d'un pan, lues dans les obstacles du DOCUMENT.
 *
 * Seul un obstacle de type `chien_assis` PORTANT une hauteur SAISIE (CAL66 `heightM`)
 * devient une lucarne. Sans hauteur, l'obstacle reste ce qu'il est aujourd'hui — une
 * boîte de placement — et RIEN ne change dans la scène.
 *
 * La pente des deux versants est DÉRIVÉE de deux valeurs saisies (la hauteur de faîtage
 * et la demi-emprise du petit côté) : aucune pente forfaitaire n'existe ici, et la
 * dérivation voyage avec la lucarne (`provenancePente`) pour que l'écran puisse la dire.
 */
export function lucarnesDuPan(
  obstacles: readonly Obstacle[] | null | undefined,
  origin: LngLat,
  offX = 0,
  offY = 0,
): Lucarne[] {
  if (!Array.isArray(obstacles) || !Array.isArray(origin)) return [];
  const cosLat = Math.cos(origin[1] * DEG2RAD);
  const out: Lucarne[] = [];
  for (const o of obstacles) {
    if (!o || o.type !== 'chien_assis' || !estMesure(o.heightM)) continue;
    if (!estMesure(o.lengthM) || !estMesure(o.widthM)) continue;
    const cx = (o.centerLng - origin[0]) * DEG2M * cosLat + offX;
    const cy = (o.centerLat - origin[1]) * DEG2M + offY;
    const hw = o.widthM / 2;
    const hl = o.lengthM / 2;
    // Le FAÎTAGE court le long du GRAND côté ; les versants descendent vers les deux
    // grands côtés. La pente vient donc du PETIT demi-côté et de la hauteur saisie.
    const demiPetitCote = Math.min(hw, hl);
    const penteDeg = Math.atan2(o.heightM, demiPetitCote) / DEG2RAD;
    out.push({
      id: o.id,
      centre: [cx, cy],
      longueurM: o.lengthM,
      largeurM: o.widthM,
      hauteurM: o.heightM,
      penteDeg,
      provenancePente:
        `dérivée de la hauteur saisie (${fmt1(o.heightM)} m) et de la demi-emprise saisie ` +
        `(${fmt1(demiPetitCote)} m) — aucune pente forfaitaire`,
      emprise: [
        [cx - hw, cy - hl],
        [cx + hw, cy - hl],
        [cx + hw, cy + hl],
        [cx - hw, cy + hl],
      ],
    });
  }
  return out;
}

/** Ce qu'un percement a réellement fait, et ce qu'il a refusé de faire — nommé. */
export interface PercementPan {
  /** La forme du PAN, trouée de chaque lucarne effectivement percée. */
  shape: THREE.Shape;
  /** Aire (m²) réellement retirée du maillage du pan. */
  aireRetireeM2: number;
  /** Identifiants des lucarnes percées. */
  percees: string[];
  /** Ce qui n'a PAS été percé, avec le motif (jamais un percement silencieusement raté). */
  nonPercees: Array<{ id: string; motif: string }>;
}

/**
 * CALX102 — construit la forme du PAN en y RETIRANT l'emprise de chaque lucarne.
 *
 * Le percement est VISUEL : il ne touche ni `clearanceForType` ni l'optimiseur, donc
 * l'aire POSABLE reste EXACTEMENT celle d'aujourd'hui (le retrait par type était déjà
 * appliqué autour du chien-assis — le percer ne le retire pas une seconde fois).
 *
 * Une lucarne dont l'emprise n'est pas STRICTEMENT à l'intérieur du tracé n'est PAS
 * percée (une découpe qui mord la rive ne se triangule pas proprement) : elle est
 * rapportée dans `nonPercees` avec son motif, jamais percée « à peu près ». La forme
 * rendue est NEUVE : l'anneau d'origine, lui, continue d'extruder le bâtiment intact.
 */
export function percerPanLucarnes(
  ring: readonly [number, number][],
  lucarnes: readonly Lucarne[],
): PercementPan {
  const shape = new THREE.Shape();
  ring.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();
  const percees: string[] = [];
  const nonPercees: Array<{ id: string; motif: string }> = [];
  let aireRetireeM2 = 0;
  if (ring.length < 3) return { shape, aireRetireeM2, percees, nonPercees };
  for (const l of lucarnes) {
    if (!l.emprise.every(([x, y]) => dansAnneau(ring, x, y))) {
      nonPercees.push({
        id: l.id,
        motif: 'emprise hors du tracé du pan (ou à cheval sur une rive) — le pan n’est pas percé',
      });
      continue;
    }
    const trou = new THREE.Path();
    l.emprise.forEach(([x, y], i) => (i === 0 ? trou.moveTo(x, y) : trou.lineTo(x, y)));
    trou.closePath();
    shape.holes.push(trou);
    percees.push(l.id);
    aireRetireeM2 += Math.abs(aireSigneeM2(l.emprise));
  }
  return { shape, aireRetireeM2, percees, nonPercees };
}

/**
 * CALX102 — le VOLUME d'une lucarne à DEUX VERSANTS, posé sur le plan du pan (base
 * `baseZ`) : deux rampants qui montent jusqu'au faîtage à la hauteur SAISIE, fermés par
 * deux pignons triangulaires. Il porte une vraie ombre (`castShadow`) — c'est ce qui le
 * distingue de la boîte posée d'aujourd'hui.
 *
 * Le maillage est construit en coordonnées de scène (les sommets portent déjà le centre
 * de la lucarne), donc aucune rotation n'est appliquée : le faîtage suit le GRAND côté de
 * l'emprise SAISIE — pas un axe supposé.
 */
export function construireLucarne(lucarne: Lucarne, baseZ: number, dim: boolean): THREE.Mesh | null {
  if (!estMesure(lucarne.hauteurM) || !Number.isFinite(baseZ)) return null;
  const [cx, cy] = lucarne.centre;
  const hw = lucarne.largeurM / 2; // est-ouest
  const hl = lucarne.longueurM / 2; // nord-sud
  if (!(hw > 0) || !(hl > 0)) return null;
  const h = lucarne.hauteurM;
  const faitageEO = hw >= hl; // faîtage le long du grand côté
  const p: number[] = [];
  const tri = (
    a: [number, number, number],
    b: [number, number, number],
    c: [number, number, number],
  ) => p.push(a[0], a[1], a[2], b[0], b[1], b[2], c[0], c[1], c[2]);

  if (faitageEO) {
    // Faîtage sur l'axe X (est-ouest), versants descendant vers y = ±hl.
    const f1: [number, number, number] = [cx - hw, cy, h];
    const f2: [number, number, number] = [cx + hw, cy, h];
    const s: [number, number, number] = [cx - hw, cy - hl, 0];
    const se: [number, number, number] = [cx + hw, cy - hl, 0];
    const n: [number, number, number] = [cx - hw, cy + hl, 0];
    const ne: [number, number, number] = [cx + hw, cy + hl, 0];
    tri(s, se, f2); tri(s, f2, f1); // versant sud
    tri(ne, n, f1); tri(ne, f1, f2); // versant nord
    tri(s, f1, n); // pignon ouest
    tri(se, ne, f2); // pignon est
  } else {
    // Faîtage sur l'axe Y (nord-sud), versants descendant vers x = ±hw.
    const f1: [number, number, number] = [cx, cy - hl, h];
    const f2: [number, number, number] = [cx, cy + hl, h];
    const o: [number, number, number] = [cx - hw, cy - hl, 0];
    const on: [number, number, number] = [cx - hw, cy + hl, 0];
    const e: [number, number, number] = [cx + hw, cy - hl, 0];
    const en: [number, number, number] = [cx + hw, cy + hl, 0];
    tri(o, on, f2); tri(o, f2, f1); // versant ouest
    tri(e, f1, f2); tri(e, f2, en); // versant est
    tri(o, e, f1); // pignon sud
    tri(on, f2, en); // pignon nord
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(p), 3));
  geo.computeVertexNormals();
  const mat = new THREE.MeshStandardMaterial({
    color: dim ? 0x9aa3b4 : 0xe2e7f2,
    roughness: 0.85,
    metalness: 0,
    side: THREE.DoubleSide,
    transparent: dim,
    opacity: dim ? 0.55 : 1,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.name = `rp11-lucarne-${lucarne.id}`;
  mesh.position.z = baseZ;
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  return mesh;
}

/** CALX102 — les volumes de TOUTES les lucarnes d'un pan (liste vide = rien à ajouter). */
export function construireLucarnes(
  lucarnes: readonly Lucarne[],
  baseZ: number,
  dim: boolean,
): THREE.Mesh[] {
  const out: THREE.Mesh[] = [];
  for (const l of lucarnes) {
    const m = construireLucarne(l, baseZ, dim);
    if (m) out.push(m);
  }
  return out;
}
