/**
 * CALX100 — LE BÂTIMENT VIENT DU DOCUMENT, PAS D'UNE CONSTANTE.
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
import { FLOORS, FLOOR_HEIGHT_M } from './constants';

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
