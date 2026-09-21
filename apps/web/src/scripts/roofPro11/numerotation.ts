/**
 * CALX111 — NUMÉROTATION STABLE DES MODULES (3D + vue plan).
 *
 * LE PROBLÈME
 * -----------
 * Les seuls numéros affichés par l'atelier sont recalculés depuis l'index du tableau au
 * moment d'afficher une proposition de retrait (`shadingUi.ts`, `nº${i + 1}`) : retirer un
 * module renumérote tous ses voisins, et le repérage imprimé la veille ne désigne plus le
 * même module. Ni la scène 3D ni la vue plan n'étiquettent quoi que ce soit.
 *
 * LA RÈGLE
 * --------
 * Le DOCUMENT est la seule source des numéros (contrat CALX83 : `panels[].n` entier ≥ 1,
 * `panels[].rangee`, `geometry.numerotation{prefixe, depart, sens}`). Un module reçoit son
 * `n` À LA POSE et ne le rend jamais :
 *   • retirer un module laisse son numéro VACANT (la suite est trouée, c'est le but) ;
 *   • un module posé à un emplacement NEUF prend le premier numéro libre AU-DELÀ du plus
 *     haut jamais attribué sur ce pan — jamais un numéro libéré par un retrait ;
 *   • un module reposé à un emplacement DÉJÀ numéroté retrouve SON numéro.
 * Rien n'est attribué tant que la bascule « Numéroter » est éteinte (défaut) : le document
 * et le rendu restent alors ceux d'aujourd'hui, octet pour octet.
 *
 * CE QUI EST SAISI, CE QUI NE L'EST PAS
 * -------------------------------------
 * `depart` et `sens` portent l'IDENTITÉ des modules : ils sont SAISIS, sans valeur par
 * défaut, et tant qu'ils manquent AUCUN numéro n'est attribué — le champ fautif est nommé
 * (`ResultatAttribution.refus`). Les seuils d'affichage (zoom carte, échelle du plan) sont
 * des constantes de DESSIN : elles ne décrivent aucun module, seulement à partir de quand
 * un chiffre reste lisible.
 *
 * DÉPENDANCES : aucune. Three.js n'est utilisé que par type (`import type`) et reçu en
 * paramètre — ce module reste importable depuis `prefill.ts` sans y tirer la 3D.
 */
import type * as THREE from 'three';

// ════════════════════════════ Formes du contrat CALX83 ════════════════════════════

/** ORDRE d'attribution sur le pan, SAISI (énumération FERMÉE du contrat v2). */
export type SensNumerotation = 'ligne' | 'serpentin';

/** Un module POSÉ tel que le document le porte : un centre ENU dans le repère du pan. */
export interface ModulePose {
  cx: number;
  cy: number;
  face?: 'E' | 'W';
}

/** Un module posé ET numéroté (les deux clés additives de CALX83). */
export interface ModuleNumerote extends ModulePose {
  n?: number;
  rangee?: string;
}

/** La convention de numérotation d'un pan, telle qu'elle voyage dans le document. */
export interface ConventionNumerotation {
  /** Préfixe SAISI affiché devant le numéro (« PV »…). Vide/absent = aucun préfixe. */
  prefixe?: string;
  /** Premier numéro attribué sur ce pan, SAISI. */
  depart?: number;
  /** Ordre d'attribution, SAISI. */
  sens?: SensNumerotation;
  /**
   * TRACE de l'attribution initiale : `'initiale'` = c'est cet atelier qui a posé les
   * premiers numéros de ce pan, dans le `sens` et depuis le `depart` ci-dessus. Écrite UNE
   * fois puis jamais réécrite ; absente = les numéros viennent d'ailleurs et on n'invente
   * pas leur histoire.
   */
  attribution?: string;
}

/** Ce que l'utilisateur a réglé dans la bascule « Numéroter » (état d'écran, pas document). */
export interface SaisieNumerotation {
  /** Bascule « Numéroter » — ÉTEINTE par défaut. */
  actif: boolean;
  /** Préfixe SAISI (chaîne vide = aucun). */
  prefixe: string;
  /** Premier numéro SAISI — `null` tant que rien n'a été saisi. */
  depart: number | null;
  /** Sens SAISI — `null` tant que rien n'a été choisi. */
  sens: SensNumerotation | null;
  /** Zoom carte à partir duquel les étiquettes 3D sont dessinées. */
  zoomMin: number;
}

/** Ce que le pan a DÉJÀ attribué : la mémoire qui rend la suite stable ET trouée. */
export interface HistoriqueNumerotation {
  /** Emplacement (clé) → numéro attribué. JAMAIS purgé : un retrait n'efface rien. */
  numeros: ReadonlyMap<string, number>;
  /** Plus haut numéro JAMAIS attribué sur ce pan (0 = aucun). */
  plafond: number;
}

/** Le champ qui manque, nommé — jamais un « impossible » générique. */
export interface RefusNumerotation {
  champ: string;
  message: string;
}

export interface ResultatAttribution {
  /** Les modules d'entrée, DANS LE MÊME ORDRE (CAL248 aligne `solarAccess` sur cet ordre). */
  modules: ModuleNumerote[];
  /** La convention à écrire dans le document, ou `null` si rien n'a été attribué. */
  numerotation: ConventionNumerotation | null;
  /** La mémoire du pan APRÈS ce passage (inchangée en cas de refus). */
  historique: HistoriqueNumerotation;
  /** Le champ manquant qui a empêché l'attribution, ou `null`. */
  refus: RefusNumerotation | null;
}

/** Mémoire vide d'un pan qui n'a jamais été numéroté. */
export const HISTORIQUE_VIDE: HistoriqueNumerotation = { numeros: new Map(), plafond: 0 };

// ════════════════════════════ Conventions de DESSIN ════════════════════════════
// Aucune de ces valeurs ne décrit un module : elles disent seulement à partir de quand un
// chiffre reste lisible, et à quelle finesse deux centres sont le même emplacement.

/** Convention de dessin : deux centres distants de moins d'1 cm sont le MÊME emplacement. */
export const TOLERANCE_EMPLACEMENT_M = 0.01;
/** Convention de dessin : le pavage aligne les rangées au décimètre près. */
export const PAS_RANGEE_M = 0.1;
/** Convention de dessin : zoom carte pré-rempli dans la bascule (modifiable, SAISI ensuite). */
export const ZOOM_MIN_ETIQUETTES = 18;
/** Convention de dessin : sous 6 px par mètre, un numéro n'est plus lisible sur le plan. */
export const ECHELLE_MIN_ETIQUETTE_PX_PAR_M = 6;
/** Convention de dessin : largeur de l'étiquette 3D (m) — un module fait ~1,1 m de large. */
export const LARGEUR_ETIQUETTE_3D_M = 0.55;
/** Convention de dessin : l'étiquette 3D flotte 0,35 m au-dessus du centre du module. */
export const HAUTEUR_ETIQUETTE_3D_M = 0.35;
/** Nom du groupe Three qui porte les étiquettes (pour le retrouver et le retirer). */
export const NOM_GROUPE_ETIQUETTES = 'calx111-numeros';

// ════════════════════════════ Emplacements et rangées (PUR) ════════════════════════════

/**
 * Clé d'EMPLACEMENT d'un module : c'est la seule identité qu'un module possède dans le
 * document (il n'a pas d'id). Deux centres à moins d'un centimètre sont le même
 * emplacement ; un module retiré puis reposé au même endroit retrouve donc son numéro.
 */
export function cleEmplacement(cx: number, cy: number): string {
  const q = (v: number) => Math.round(v / TOLERANCE_EMPLACEMENT_M);
  return `${q(cx)}:${q(cy)}`;
}

/**
 * Passe un centre du repère du pan au repère de POSE : abscisse le long de la rangée,
 * puis profondeur en travers. L'azimut de la famille oriente les rangées.
 */
export function versRepereRangees(cx: number, cy: number, azimutDeg: number): [number, number] {
  const az = (azimutDeg || 0) * (Math.PI / 180);
  const fe = Math.sin(az);
  const fn = Math.cos(az);
  // Axe de rangée = perpendiculaire à la visée.
  const angle = Math.atan2(fe, -fn);
  const ca = Math.cos(angle);
  const sa = Math.sin(angle);
  return [cx * ca + cy * sa, -cx * sa + cy * ca];
}

/** Nom de rangée : A…Z puis AA, AB… (une ÉTIQUETTE, jamais un rang calculé). */
export function nomRangee(index: number): string {
  if (!Number.isInteger(index) || index < 0) return '';
  let reste = index;
  let nom = '';
  do {
    nom = String.fromCharCode(65 + (reste % 26)) + nom;
    reste = Math.floor(reste / 26) - 1;
  } while (reste >= 0);
  return nom;
}

/** Une rangée du pavage : son étiquette, sa profondeur et ses modules d'ouest en est. */
export interface RangeeModules<T extends ModulePose> {
  nom: string;
  profondeurM: number;
  modules: T[];
}

/**
 * Regroupe les modules POSÉS en rangées du pavage (profondeur arrondie au décimètre),
 * triées de la plus faible profondeur à la plus grande, chacune ordonnée le long de la
 * rangée. Les rangées sont nommées A, B, C… dans cet ordre.
 */
export function rangeesDeModules<T extends ModulePose>(
  modules: readonly T[],
  azimutDeg: number,
): RangeeModules<T>[] {
  const paquets = new Map<number, { profondeurM: number; entrees: { le: number; module: T }[] }>();
  for (const module of modules) {
    const [le, ld] = versRepereRangees(module.cx, module.cy, azimutDeg);
    const cle = Math.round(ld / PAS_RANGEE_M);
    const paquet = paquets.get(cle);
    if (paquet) paquet.entrees.push({ le, module });
    else paquets.set(cle, { profondeurM: cle * PAS_RANGEE_M, entrees: [{ le, module }] });
  }
  const ordonnees = [...paquets.values()].sort((a, b) => a.profondeurM - b.profondeurM);
  return ordonnees.map((paquet, index) => ({
    nom: nomRangee(index),
    profondeurM: paquet.profondeurM,
    modules: paquet.entrees.sort((a, b) => a.le - b.le).map((e) => e.module),
  }));
}

/**
 * ORDRE dans lequel les numéros sont attribués, et rangée de chaque module.
 * `ligne` : chaque rangée dans le même sens. `serpentin` : une rangée sur deux à l'envers,
 * l'ordre dans lequel un poseur marche réellement.
 * N'A AUCUN effet sur l'ordre du tableau `panels` — seulement sur QUI reçoit quel numéro.
 */
export function ordreAttribution<T extends ModulePose>(
  modules: readonly T[],
  azimutDeg: number,
  sens: SensNumerotation,
): { module: T; rangee: string }[] {
  const ordre: { module: T; rangee: string }[] = [];
  const rangees = rangeesDeModules(modules, azimutDeg);
  rangees.forEach((rangee, index) => {
    const marche = sens === 'serpentin' && index % 2 === 1 ? [...rangee.modules].reverse() : rangee.modules;
    for (const module of marche) ordre.push({ module, rangee: rangee.nom });
  });
  return ordre;
}

// ════════════════════════════ Attribution (PURE) ════════════════════════════

/**
 * Attribue les numéros des modules POSÉS. Fonction PURE : elle ne lit ni le document, ni
 * l'écran, ni l'horloge ; elle ne modifie NI `poses` NI `historique`.
 *
 * Stabilité — ce qui est garanti, et pourquoi :
 *  • un emplacement déjà numéroté garde SON numéro (il est retrouvé par sa clé, pas par
 *    sa place dans le tableau) : retirer un module ne touche donc aucun de ses voisins ;
 *  • un emplacement neuf prend `plafond + 1` (ou le `depart` saisi au tout premier
 *    passage) : un numéro libéré par un retrait n'est JAMAIS redonné à un autre module ;
 *  • les modules sortent dans l'ORDRE D'ENTRÉE — `solarAccess` (CAL248) s'aligne sur cet
 *    ordre, le décaler contredirait le document.
 */
export function attribuerNumeros(
  poses: readonly ModulePose[],
  historique: HistoriqueNumerotation,
  convention: ConventionNumerotation,
  azimutDeg: number,
): ResultatAttribution {
  const inchange = (refus: RefusNumerotation | null): ResultatAttribution => ({
    modules: poses.map((module) => ({ ...module })),
    numerotation: null,
    historique,
    refus,
  });
  if (!convention.sens) {
    return inchange({
      champ: 'numerotation.sens',
      message: 'Sens de numérotation non saisi — aucun numéro n’est attribué.',
    });
  }
  const depart = convention.depart;
  if (historique.plafond < 1 && !(typeof depart === 'number' && Number.isInteger(depart) && depart >= 1)) {
    return inchange({
      champ: 'numerotation.depart',
      message: 'Premier numéro non saisi — aucun numéro n’est attribué.',
    });
  }
  if (!poses.length) return inchange(null);

  const numeros = new Map(historique.numeros);
  let plafond = historique.plafond;
  let suivant = Math.max(plafond + 1, typeof depart === 'number' ? depart : 1);
  const attribues = new Map<string, number>();
  const rangees = new Map<string, string>();
  for (const { module, rangee } of ordreAttribution(poses, azimutDeg, convention.sens)) {
    const cle = cleEmplacement(module.cx, module.cy);
    rangees.set(cle, rangee);
    if (attribues.has(cle)) continue; // deux modules au même endroit : le premier fait foi
    const connu = numeros.get(cle);
    const numero = typeof connu === 'number' ? connu : suivant++;
    numeros.set(cle, numero);
    attribues.set(cle, numero);
    if (numero > plafond) plafond = numero;
  }

  const modules = poses.map((module) => {
    const cle = cleEmplacement(module.cx, module.cy);
    const numero = attribues.get(cle);
    const rangee = rangees.get(cle);
    return {
      ...module,
      ...(typeof numero === 'number' ? { n: numero } : {}),
      ...(rangee ? { rangee } : {}),
    };
  });

  const numerotation: ConventionNumerotation = {};
  const prefixe = (convention.prefixe ?? '').trim();
  if (prefixe) numerotation.prefixe = prefixe;
  if (typeof depart === 'number') numerotation.depart = depart;
  numerotation.sens = convention.sens;
  // TRACE : `initiale` seulement quand ce passage est le PREMIER du pan. Un pan qui portait
  // déjà des numéros venus d'ailleurs garde une trace absente — on n'invente pas son passé.
  if (convention.attribution) numerotation.attribution = convention.attribution;
  else if (historique.plafond < 1) numerotation.attribution = 'initiale';

  return { modules, numerotation, historique: { numeros, plafond }, refus: null };
}

/**
 * Étiquette HUMAINE d'un module, LUE DEPUIS `n` — jamais depuis l'index du tableau.
 * Renvoie une chaîne VIDE quand le module ne porte pas de numéro : un module non numéroté
 * n'en reçoit pas un de circonstance.
 */
export function etiquette(
  module: ModuleNumerote | null | undefined,
  convention?: ConventionNumerotation | null,
): string {
  const n = module?.n;
  if (typeof n !== 'number' || !Number.isInteger(n) || n < 1) return '';
  const prefixe = (convention?.prefixe ?? '').trim();
  return prefixe ? `${prefixe} nº${n}` : `nº${n}`;
}

// ════════════════════════════ Registre de session ════════════════════════════
// Le document est la seule SOURCE des numéros ; entre deux écritures, l'atelier a quand
// même besoin de se souvenir de ce qu'il a attribué (le tableau `panels` est reconstruit à
// chaque sérialisation, sans `n`). Ce registre est cette mémoire : il est SEMÉ par le
// document (`absorberDocument`) et ne contient jamais rien qu'il n'ait lu ou attribué.

/** Forme MINIMALE d'un document lue ici — aucune dépendance à `prefill.ts`. */
interface PanDocument {
  id?: string;
  geometry?: {
    azimuthDeg?: number;
    panels?: ModuleNumerote[];
    numerotation?: ConventionNumerotation;
  };
}
interface DocumentNumerotable {
  zones?: PanDocument[];
}

export interface RegistreNumerotation {
  /** Sème la mémoire depuis un document qui porte déjà des `n` (idempotent). */
  absorberDocument(document: unknown): void;
  historique(panId: string): HistoriqueNumerotation;
  /** La convention DÉJÀ en vigueur sur ce pan, ou `null`. */
  convention(panId: string): ConventionNumerotation | null;
  /** Les modules numérotés du dernier passage sur ce pan (pour les étiquettes). */
  modules(panId: string): ModuleNumerote[];
  /** Attribue et mémorise ; renvoie le résultat PUR de `attribuerNumeros`. */
  appliquer(
    panId: string,
    poses: readonly ModulePose[],
    convention: ConventionNumerotation,
    azimutDeg: number,
  ): ResultatAttribution;
  oublier(): void;
}

export function creerRegistre(): RegistreNumerotation {
  const historiques = new Map<string, HistoriqueNumerotation>();
  const conventions = new Map<string, ConventionNumerotation>();
  const derniers = new Map<string, ModuleNumerote[]>();

  const memoriser = (panId: string, modules: readonly ModuleNumerote[]) => {
    const courant = historiques.get(panId) ?? HISTORIQUE_VIDE;
    const numeros = new Map(courant.numeros);
    let plafond = courant.plafond;
    for (const module of modules) {
      const n = module.n;
      if (typeof n !== 'number' || !Number.isInteger(n) || n < 1) continue;
      numeros.set(cleEmplacement(module.cx, module.cy), n);
      if (n > plafond) plafond = n;
    }
    historiques.set(panId, { numeros, plafond });
  };

  return {
    absorberDocument(document: unknown) {
      const zones = (document as DocumentNumerotable | null)?.zones;
      if (!Array.isArray(zones)) return;
      for (const zone of zones) {
        const panId = zone?.id;
        const geometrie = zone?.geometry;
        if (!panId || !geometrie || !Array.isArray(geometrie.panels)) continue;
        const numerotes = geometrie.panels.filter((module) => typeof module?.n === 'number');
        if (numerotes.length) {
          memoriser(panId, numerotes);
          derniers.set(panId, geometrie.panels.map((module) => ({ ...module })));
        }
        if (geometrie.numerotation && typeof geometrie.numerotation === 'object') {
          conventions.set(panId, { ...geometrie.numerotation });
        }
      }
    },
    historique(panId: string) {
      return historiques.get(panId) ?? HISTORIQUE_VIDE;
    },
    convention(panId: string) {
      return conventions.get(panId) ?? null;
    },
    modules(panId: string) {
      return derniers.get(panId) ?? [];
    },
    appliquer(panId, poses, convention, azimutDeg) {
      const resultat = attribuerNumeros(poses, historiques.get(panId) ?? HISTORIQUE_VIDE, convention, azimutDeg);
      if (resultat.refus) return resultat;
      historiques.set(panId, resultat.historique);
      derniers.set(panId, resultat.modules);
      if (resultat.numerotation) conventions.set(panId, resultat.numerotation);
      return resultat;
    },
    oublier() {
      historiques.clear();
      conventions.clear();
      derniers.clear();
    },
  };
}

/** La mémoire de L'ATELIER (une seule par page). */
export const registreAtelier = creerRegistre();

// ════════════════════════════ Bascule « Numéroter » (état d'écran) ════════════════════════════

const SAISIE_ETEINTE: SaisieNumerotation = {
  actif: false,
  prefixe: '',
  depart: null,
  sens: null,
  zoomMin: ZOOM_MIN_ETIQUETTES,
};

let saisie: SaisieNumerotation = { ...SAISIE_ETEINTE };

export function saisieCourante(): SaisieNumerotation {
  return { ...saisie };
}

export function definirSaisie(partielle: Partial<SaisieNumerotation>): SaisieNumerotation {
  saisie = { ...saisie, ...partielle };
  return saisieCourante();
}

/** Remet la bascule à l'état de départ (éteinte) — utilisé par les tests. */
export function reinitialiserNumerotation(): void {
  saisie = { ...SAISIE_ETEINTE };
  registreAtelier.oublier();
}

/** La convention que la SAISIE propose, telle qu'elle entrerait dans le document. */
export function conventionSaisie(etat: SaisieNumerotation = saisie): ConventionNumerotation {
  const convention: ConventionNumerotation = {};
  const prefixe = etat.prefixe.trim();
  if (prefixe) convention.prefixe = prefixe;
  if (typeof etat.depart === 'number' && Number.isInteger(etat.depart) && etat.depart >= 1) {
    convention.depart = etat.depart;
  }
  if (etat.sens) convention.sens = etat.sens;
  return convention;
}

/**
 * La convention RÉELLEMENT appliquée à un pan : celle DÉJÀ inscrite dans le document gagne
 * (un écran rouvert reprend la même main, et changer le sens ne renumérote donc rien) ; la
 * saisie ne comble que ce qui manque.
 */
export function conventionDuPan(
  deja: ConventionNumerotation | null,
  etat: SaisieNumerotation = saisie,
): ConventionNumerotation {
  return { ...conventionSaisie(etat), ...(deja ?? {}) };
}

// ════════════════════════════ Crochet document (serializeLayout) ════════════════════════════

/**
 * Écrit les numéros dans le document qui vient d'être émis. C'est le SEUL endroit où les
 * clés `n`/`rangee`/`numerotation` entrent dans un document.
 *
 * Bascule ÉTEINTE (défaut) : le document ressort tel quel, octet pour octet — la mémoire
 * est seulement SEMÉE par ce qu'il porte déjà. Bascule allumée mais `depart`/`sens` non
 * saisis : rien n'est écrit non plus, et `refus` nomme le champ manquant.
 */
export function numeroterDocument(
  document: unknown,
  etat: SaisieNumerotation = saisie,
  registre: RegistreNumerotation = registreAtelier,
): RefusNumerotation | null {
  registre.absorberDocument(document);
  if (!etat.actif) return null;
  const zones = (document as DocumentNumerotable | null)?.zones;
  if (!Array.isArray(zones)) return null;
  let refus: RefusNumerotation | null = null;
  for (const zone of zones) {
    const panId = zone?.id;
    const geometrie = zone?.geometry;
    if (!panId || !geometrie || !Array.isArray(geometrie.panels) || !geometrie.panels.length) continue;
    const resultat = registre.appliquer(
      panId,
      geometrie.panels,
      conventionDuPan(registre.convention(panId), etat),
      geometrie.azimuthDeg ?? 0,
    );
    if (resultat.refus) {
      refus = refus ?? resultat.refus;
      continue;
    }
    geometrie.panels = resultat.modules;
    if (resultat.numerotation) geometrie.numerotation = resultat.numerotation;
  }
  return refus;
}

// ════════════════════════════ Étiquettes 3D et plan (décision PURE) ════════════════════════════

/** Une étiquette à poser : le module visé (par sa place dans la liste rendue) et son texte. */
export interface EtiquetteModule {
  index: number;
  texte: string;
}

/** Une étiquette de vue plan : même chose, plus la position écran de son module. */
export interface EtiquettePlan extends EtiquetteModule {
  x: number;
  y: number;
}

/**
 * DÉCIDE quelles étiquettes 3D dessiner — PUR, sans Three ni DOM. Liste VIDE quand la
 * bascule est éteinte, quand le zoom courant est inconnu, ou quand il n'atteint pas le
 * seuil saisi : le rendu est alors celui d'aujourd'hui, à l'objet près.
 */
export function etiquettes3d(
  modules: readonly ModulePose[],
  numeros: ReadonlyMap<string, number>,
  convention: ConventionNumerotation | null,
  zoom: number | null | undefined,
  etat: SaisieNumerotation = saisie,
): EtiquetteModule[] {
  if (!etat.actif) return [];
  if (typeof zoom !== 'number' || !Number.isFinite(zoom) || zoom < etat.zoomMin) return [];
  const etiquettes: EtiquetteModule[] = [];
  modules.forEach((module, index) => {
    const n = numeros.get(cleEmplacement(module.cx, module.cy));
    const texte = etiquette({ ...module, n }, convention);
    if (texte) etiquettes.push({ index, texte });
  });
  return etiquettes;
}

/** La projection plan telle que `projectPlanView` la rend (sous-ensemble lu ici). */
export interface ProjectionPlan {
  panels: ReadonlyArray<ReadonlyArray<readonly [number, number]>>;
  pxPerM: number;
}

/**
 * DÉCIDE les étiquettes de la VUE PLAN — PUR. Le texte vient de `n` (jamais de l'index) et
 * la position est le centre du rectangle projeté. Liste VIDE si la bascule est éteinte, si
 * l'échelle est trop petite pour qu'un chiffre reste lisible, ou si la projection et les
 * modules ne se correspondent pas (longueurs différentes) : on ne devine aucun appariement.
 */
export function etiquettesPlan(
  plan: ProjectionPlan | null | undefined,
  modules: readonly ModuleNumerote[],
  convention: ConventionNumerotation | null,
  etat: SaisieNumerotation = saisie,
): EtiquettePlan[] {
  if (!etat.actif || !plan || !Array.isArray(plan.panels)) return [];
  if (plan.panels.length !== modules.length) return [];
  if (!(plan.pxPerM >= ECHELLE_MIN_ETIQUETTE_PX_PAR_M)) return [];
  const etiquettes: EtiquettePlan[] = [];
  plan.panels.forEach((quad, index) => {
    const texte = etiquette(modules[index], convention);
    if (!texte || !quad.length) return;
    let sx = 0;
    let sy = 0;
    for (const [x, y] of quad) {
      sx += x;
      sy += y;
    }
    etiquettes.push({ index, texte, x: sx / quad.length, y: sy / quad.length });
  });
  return etiquettes;
}

// ════════════════════════════ Pose des étiquettes 3D (mince, impur) ════════════════════════════

/** Ce dont la pose 3D a besoin — fourni par `scene3d.ts` en UNE ligne. */
export interface DemandeEtiquettes3d {
  three: typeof THREE;
  racine: THREE.Object3D | null;
  panId: string;
  /** Les modules RENDUS, dans l'ordre des matrices d'instance. */
  modules: readonly ModulePose[];
  matrices: readonly THREE.Matrix4[];
  /** Zoom courant de la carte (`map.getZoom()`), ou null quand il n'est pas connu. */
  zoom: number | null;
  /** Un pan NON actif : pas d'étiquette (le surlignage est déjà réservé au pan en cours). */
  autreZone?: boolean;
  /** Où accrocher la bascule « Numéroter » si la page ne la fournit pas (créée une fois). */
  hote?: HTMLElement | null;
  /** Repeint de la carte, pour que basculer la case ait un effet immédiat. */
  repeint?: () => void;
  registre?: RegistreNumerotation;
}

let derniereDemande: DemandeEtiquettes3d | null = null;
let rafraichirCarte: (() => void) | null = null;

/** Retire le groupe d'étiquettes d'une racine (et libère ses textures canvas). */
function retirerGroupe(racine: THREE.Object3D | null): void {
  if (!racine) return;
  const ancien = racine.children.find((enfant) => enfant.name === NOM_GROUPE_ETIQUETTES);
  if (!ancien) return;
  ancien.traverse((objet: THREE.Object3D) => {
    const materiau = (objet as THREE.Sprite).material as THREE.SpriteMaterial | undefined;
    if (!materiau) return;
    materiau.map?.dispose?.();
    materiau.dispose?.();
  });
  racine.remove(ancien);
}

/** Dessine le texte sur un canevas — convention de dessin, rien d'autre. */
function canevasEtiquette(texte: string): HTMLCanvasElement | null {
  if (typeof document === 'undefined' || typeof document.createElement !== 'function') return null;
  const taillePx = 56;
  const margeX = 22;
  const margeY = 14;
  const police = `bold ${taillePx}px "Inter", system-ui, -apple-system, Segoe UI, sans-serif`;
  const mesure = document.createElement('canvas').getContext('2d');
  if (mesure) mesure.font = police;
  const largeurTexte = mesure ? mesure.measureText(texte).width : texte.length * taillePx * 0.55;
  const canevas = document.createElement('canvas');
  canevas.width = Math.max(1, Math.ceil(largeurTexte + margeX * 2));
  canevas.height = taillePx + margeY * 2;
  const pinceau = canevas.getContext('2d');
  if (pinceau) {
    pinceau.font = police;
    pinceau.textAlign = 'center';
    pinceau.textBaseline = 'middle';
    pinceau.fillStyle = 'rgba(7, 11, 29, 0.82)';
    pinceau.fillRect(0, 0, canevas.width, canevas.height);
    pinceau.lineWidth = 5;
    pinceau.strokeStyle = 'rgba(7, 11, 29, 0.95)';
    pinceau.strokeText(texte, canevas.width / 2, canevas.height / 2 + 2);
    pinceau.fillStyle = '#ffffff';
    pinceau.fillText(texte, canevas.width / 2, canevas.height / 2 + 2);
  }
  return canevas;
}

/**
 * Pose (ou retire) les étiquettes de numéro sur les modules RENDUS. Appelée en UNE ligne
 * par `scene3d.ts` à la fin du rendu des modules.
 *
 * Bascule éteinte : le groupe d'étiquettes est retiré s'il existait, et RIEN n'est ajouté à
 * la scène — le rendu est celui d'aujourd'hui. Aucun calcul de numéro ici : la décision est
 * prise par `etiquettes3d` (pure) et les numéros viennent du registre, donc du document.
 */
export function poserEtiquettesNumeros(demande: DemandeEtiquettes3d): void {
  const { three, racine } = demande;
  monterControleNumerotation(demande.hote);
  if (demande.repeint) rafraichirCarte = demande.repeint;
  if (!racine || !three) return;
  if (!demande.autreZone) derniereDemande = demande;
  retirerGroupe(racine);
  if (demande.autreZone) return;
  const registre = demande.registre ?? registreAtelier;
  const aPoser = etiquettes3d(
    demande.modules,
    registre.historique(demande.panId).numeros,
    registre.convention(demande.panId),
    demande.zoom,
  );
  if (!aPoser.length) return;
  const groupe = new three.Group();
  groupe.name = NOM_GROUPE_ETIQUETTES;
  const position = new three.Vector3();
  for (const { index, texte } of aPoser) {
    const matrice = demande.matrices[index];
    const canevas = matrice ? canevasEtiquette(texte) : null;
    if (!matrice || !canevas) continue;
    const texture = new three.CanvasTexture(canevas);
    texture.colorSpace = three.SRGBColorSpace;
    texture.needsUpdate = true;
    const sprite = new three.Sprite(
      new three.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false }),
    );
    position.setFromMatrixPosition(matrice);
    sprite.position.set(position.x, position.y, position.z + HAUTEUR_ETIQUETTE_3D_M);
    const largeur = LARGEUR_ETIQUETTE_3D_M;
    sprite.scale.set(largeur, (largeur * canevas.height) / canevas.width, 1);
    sprite.renderOrder = 21;
    groupe.add(sprite);
  }
  if (groupe.children.length) racine.add(groupe);
}

/** Rejoue la pose sur la dernière scène rendue (après un changement de bascule ou de zoom). */
export function rafraichirEtiquettes(): void {
  if (derniereDemande) poserEtiquettesNumeros(derniereDemande);
  rafraichirCarte?.();
}

// ════════════════════════════ Contrôle DOM créé par le module ════════════════════════════
// Patron de `obstaclesUi.ensureTypePicker` / `zones.ensureStatsTable` : le contrôle est créé
// ICI s'il n'existe pas déjà dans la page — AUCUNE page hôte n'a à être modifiée.

export const ID_CONTROLE_NUMEROTATION = 'rp11-numerotation';

/** Crée (une seule fois) la bascule « Numéroter » et ses trois saisies. */
export function monterControleNumerotation(hote: HTMLElement | null | undefined): HTMLElement | null {
  if (typeof document === 'undefined' || typeof document.createElement !== 'function') return null;
  const existant = document.getElementById(ID_CONTROLE_NUMEROTATION);
  if (existant) return existant;
  if (!hote) return null;

  const bloc = document.createElement('div');
  bloc.id = ID_CONTROLE_NUMEROTATION;
  bloc.className = 'mt-3 text-sm';

  const ligneBascule = document.createElement('label');
  ligneBascule.setAttribute('for', `${ID_CONTROLE_NUMEROTATION}-actif`);
  const bascule = document.createElement('input');
  bascule.type = 'checkbox';
  bascule.id = `${ID_CONTROLE_NUMEROTATION}-actif`;
  bascule.checked = saisie.actif;
  ligneBascule.appendChild(bascule);
  ligneBascule.appendChild(document.createTextNode(' Numéroter les modules'));
  bloc.appendChild(ligneBascule);

  const erreurs = document.createElement('div');
  erreurs.id = `${ID_CONTROLE_NUMEROTATION}-erreur`;
  erreurs.className = 'mt-1 text-xs';
  erreurs.setAttribute('role', 'status');

  const champ = (id: string, libelle: string, type: string): HTMLInputElement => {
    const enveloppe = document.createElement('label');
    enveloppe.setAttribute('for', id);
    enveloppe.className = 'mt-1 block';
    enveloppe.appendChild(document.createTextNode(`${libelle} `));
    const entree = document.createElement('input');
    entree.type = type;
    entree.id = id;
    entree.className = 'rp9-input';
    enveloppe.appendChild(entree);
    bloc.appendChild(enveloppe);
    return entree;
  };

  const prefixeEl = champ(`${ID_CONTROLE_NUMEROTATION}-prefixe`, 'Préfixe', 'text');
  prefixeEl.value = saisie.prefixe;
  const departEl = champ(`${ID_CONTROLE_NUMEROTATION}-depart`, 'Premier numéro', 'number');
  departEl.min = '1';
  departEl.step = '1';
  departEl.value = saisie.depart == null ? '' : String(saisie.depart);

  const sensEnveloppe = document.createElement('label');
  sensEnveloppe.className = 'mt-1 block';
  sensEnveloppe.setAttribute('for', `${ID_CONTROLE_NUMEROTATION}-sens`);
  sensEnveloppe.appendChild(document.createTextNode('Sens '));
  const sensEl = document.createElement('select');
  sensEl.id = `${ID_CONTROLE_NUMEROTATION}-sens`;
  sensEl.className = 'rp9-input';
  for (const [valeur, libelle] of [
    ['', '— à choisir —'],
    ['ligne', 'Ligne (chaque rangée dans le même sens)'],
    ['serpentin', 'Serpentin (une rangée sur deux à l’envers)'],
  ] as const) {
    const option = document.createElement('option');
    option.value = valeur;
    option.textContent = libelle;
    sensEl.appendChild(option);
  }
  sensEl.value = saisie.sens ?? '';
  sensEnveloppe.appendChild(sensEl);
  bloc.appendChild(sensEnveloppe);

  const zoomEl = champ(`${ID_CONTROLE_NUMEROTATION}-zoom`, 'Afficher à partir du zoom', 'number');
  zoomEl.step = '0.5';
  zoomEl.value = String(saisie.zoomMin);

  bloc.appendChild(erreurs);

  /** Erreur SOUS le champ fautif : on nomme le champ, jamais un « impossible » générique. */
  const direErreur = () => {
    if (!saisie.actif) {
      erreurs.textContent = '';
      return;
    }
    if (!saisie.sens) {
      erreurs.textContent = 'Sens de numérotation non saisi — aucun numéro n’est attribué.';
      return;
    }
    if (saisie.depart == null) {
      erreurs.textContent = 'Premier numéro non saisi — aucun numéro n’est attribué.';
      return;
    }
    erreurs.textContent = '';
  };

  const appliquer = () => {
    const departLu = Number.parseInt(departEl.value, 10);
    const zoomLu = Number.parseFloat(zoomEl.value);
    definirSaisie({
      actif: bascule.checked,
      prefixe: prefixeEl.value,
      depart: Number.isInteger(departLu) && departLu >= 1 ? departLu : null,
      sens: sensEl.value === 'ligne' || sensEl.value === 'serpentin' ? sensEl.value : null,
      zoomMin: Number.isFinite(zoomLu) ? zoomLu : ZOOM_MIN_ETIQUETTES,
    });
    direErreur();
    rafraichirEtiquettes();
  };

  for (const element of [bascule, prefixeEl, departEl, sensEl, zoomEl]) {
    element.addEventListener('change', appliquer);
  }
  direErreur();
  hote.appendChild(bloc);
  return bloc;
}
