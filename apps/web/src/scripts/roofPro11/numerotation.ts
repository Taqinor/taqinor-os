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
 * INVARIANT (revue du lot 8, suite ACAL1720) : un numéro ENGAGÉ désigne UNE place pour toujours. Seul un
 * enregistrement engage ; un document ne peut jamais engager un numéro que la mémoire engagée donne à une autre
 * place, ni un numéro au plus égal au plafond engagé pour une place inconnue (`assainirNumerosPortes`).
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
  /** La mémoire du pan APRÈS ce passage, SI ce passage est enregistré (inchangée en cas de refus). */
  historique: HistoriqueNumerotation;
  /** Numérotation stable (suite ACAL1720) — les numéros PROVISOIRES après ce passage : les
   *  emplacements numérotés ici qui ne sont pas dans `historique` d'entrée (rien n'est engagé). */
  provisoires: ReadonlyMap<string, number>;
  /** Le champ manquant qui a empêché l'attribution, ou `null`. */
  refus: RefusNumerotation | null;
}

/** Mémoire vide d'un pan qui n'a jamais été numéroté. */
export const HISTORIQUE_VIDE: HistoriqueNumerotation = { numeros: new Map(), plafond: 0 };

/** Numérotation stable (suite ACAL1720) — aucun numéro provisoire. */
const AUCUN_PROVISOIRE: ReadonlyMap<string, number> = new Map();

/** Numérotation stable (suite ACAL1720) — clé RACINE du document (`roof_layout_v2.schema.json`) : par pan, le plus
 *  haut numéro JAMAIS attribué, écrite SEULEMENT quand il dépasse le plus haut `n` encore posé (modules du haut
 *  retirés, pan supprimé). Sans elle, rouvrir le document redonnait ces numéros à d'autres modules. */
export const CLE_PLAFONDS = 'plafondsNumerotation';

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
 *
 * Numérotation stable (suite ACAL1720) — `provisoires` : les numéros montrés à l'écran depuis le dernier
 * enregistrement, que RIEN de stocké ne désigne encore. Un emplacement provisoire GARDE le sien (retirer un
 * module neuf ne renumérote pas ses voisins) ; un emplacement neuf prend le numéro qui suit le plus haut
 * numéro VIVANT (engagé ou provisoire) — jamais au-delà des numéros d'une pose qui n'est plus à l'écran :
 * faire glisser une inclinaison ne dépense donc plus rien. Seul `historique` est la mémoire engagée.
 */
export function attribuerNumeros(
  poses: readonly ModulePose[],
  historique: HistoriqueNumerotation,
  convention: ConventionNumerotation,
  azimutDeg: number,
  provisoires: ReadonlyMap<string, number> = AUCUN_PROVISOIRE,
): ResultatAttribution {
  const inchange = (refus: RefusNumerotation | null): ResultatAttribution => ({
    modules: poses.map((module) => ({ ...module })),
    numerotation: null,
    historique,
    provisoires,
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
  // Le premier numéro qu'un emplacement neuf peut prendre (le `depart` saisi au tout premier passage).
  const base = Math.max(plafond, (typeof depart === 'number' ? depart : 1) - 1);
  const attribues = new Map<string, number>();
  const rangees = new Map<string, string>();
  const ordre = ordreAttribution(poses, azimutDeg, convention.sens);
  const pris = new Set<number>();
  const retenir = (cle: string, numero: number) => {
    attribues.set(cle, numero);
    pris.add(numero);
  };
  // 1) les numéros ENGAGÉS, 2) les numéros PROVISOIRES encore libres (au-delà de `base`), dans l'ordre.
  for (const { module, rangee } of ordre) {
    const cle = cleEmplacement(module.cx, module.cy);
    rangees.set(cle, rangee);
    const connu = numeros.get(cle);
    if (!attribues.has(cle) && typeof connu === 'number') retenir(cle, connu);
  }
  for (const { module } of ordre) {
    const cle = cleEmplacement(module.cx, module.cy);
    const provisoire = provisoires.get(cle);
    if (!attribues.has(cle) && typeof provisoire === 'number' && provisoire > base && !pris.has(provisoire)) {
      retenir(cle, provisoire);
    }
  }
  // 3) les emplacements neufs : au-delà du plus haut numéro vivant (deux modules au même endroit : le premier fait foi).
  let suivant = Math.max(base, ...pris) + 1;
  const nouveauxProvisoires = new Map(provisoires);
  for (const { module } of ordre) {
    const cle = cleEmplacement(module.cx, module.cy);
    if (!attribues.has(cle)) retenir(cle, suivant++);
  }
  for (const [cle, numero] of attribues) {
    if (!historique.numeros.has(cle)) nouveauxProvisoires.set(cle, numero);
    numeros.set(cle, numero);
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

  return { modules, numerotation, historique: { numeros, plafond }, provisoires: nouveauxProvisoires, refus: null };
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
  [CLE_PLAFONDS]?: unknown;
}

export interface RegistreNumerotation {
  /** Sème la mémoire ENGAGÉE depuis un document qui porte déjà des `n` (idempotent) — et, suite ACAL1720,
   *  depuis sa clé racine `plafondsNumerotation` (plafond d'un pan dont les modules du haut sont retirés). */
  absorberDocument(document: unknown): void;
  /** La mémoire ENGAGÉE du pan (document rouvert + enregistrements) — jamais un numéro provisoire. */
  historique(panId: string): HistoriqueNumerotation;
  /** La convention DÉJÀ en vigueur sur ce pan, ou `null`. */
  convention(panId: string): ConventionNumerotation | null;
  /** Les modules numérotés du dernier passage sur ce pan (pour les étiquettes) — provisoires compris. */
  modules(panId: string): ModuleNumerote[];
  /** Suite ACAL1720 — les modules ENGAGÉS du pan (document absorbé ou enregistré) : seuls réécrits par ACAL31. */
  modulesEngages(panId: string): ModuleNumerote[];
  /** Suite ACAL1720 — emplacement → numéro AFFICHÉ (engagé, ou provisoire du dernier passage). */
  numerosAffiches(panId: string): ReadonlyMap<string, number>;
  /** Suite ACAL1720 — emplacement → numéro PROVISOIRE (montré, rien de stocké ne le désigne). */
  provisoires(panId: string): ReadonlyMap<string, number>;
  /** Suite ACAL1720 — les pans dont la mémoire engagée est connue. */
  pans(): string[];
  /** Attribue et mémorise (ENGAGE) ; renvoie le résultat PUR de `attribuerNumeros`. */
  appliquer(
    panId: string,
    poses: readonly ModulePose[],
    convention: ConventionNumerotation,
    azimutDeg: number,
  ): ResultatAttribution;
  /** Suite ACAL1720 — une COPIE indépendante (une sérialisation de lecture travaille dessus). */
  cloner(): RegistreNumerotation;
  /** Suite ACAL1720 — reprend d'une copie de LECTURE ce qu'elle a montré : ses modules affichés, et comme
   *  PROVISOIRES les numéros qu'elle a attribués hors de la mémoire engagée. Rien n'est engagé. */
  retenirLecture(copie: RegistreNumerotation): void;
  oublier(): void;
}

/** L'état d'un registre (suite ACAL1720 — recopié par `cloner`). */
interface EtatRegistre {
  historiques: Map<string, HistoriqueNumerotation>;
  conventions: Map<string, ConventionNumerotation>;
  derniers: Map<string, ModuleNumerote[]>;
  engages: Map<string, ReadonlyMap<string, ModuleNumerote>>;
  provisoires: Map<string, ReadonlyMap<string, number>>;
}

export function creerRegistre(depuis?: EtatRegistre): RegistreNumerotation {
  const historiques = new Map(depuis?.historiques);
  const conventions = new Map(depuis?.conventions);
  const derniers = new Map(depuis?.derniers);
  const engages = new Map(depuis?.engages);
  const provisoires = new Map(depuis?.provisoires);

  const memoriser = (panId: string, modules: readonly ModuleNumerote[], plafondLu = 0) => {
    const courant = historiques.get(panId) ?? HISTORIQUE_VIDE;
    const numeros = new Map(courant.numeros);
    let plafond = Math.max(courant.plafond, plafondLu);
    for (const module of modules) {
      const n = module.n;
      if (typeof n !== 'number' || !Number.isInteger(n) || n < 1) continue;
      numeros.set(cleEmplacement(module.cx, module.cy), n);
      if (n > plafond) plafond = n;
    }
    historiques.set(panId, { numeros, plafond });
  };
  /** Suite ACAL1720 — les modules ENGAGÉS, par emplacement, jamais purgés (comme `numeros`) : une pose ramenée à
   *  celle du document relu retrouve ses `n` même après un passage ailleurs. */
  const engager = (panId: string, modules: readonly ModuleNumerote[]) => {
    const parPlace = new Map(engages.get(panId));
    for (const module of modules) {
      if (typeof module.n === 'number' || typeof module.rangee === 'string') parPlace.set(cleEmplacement(module.cx, module.cy), module);
    }
    engages.set(panId, parPlace);
  };

  const registre: RegistreNumerotation = {
    absorberDocument(document: unknown) {
      const doc = document as DocumentNumerotable | null;
      const plafondsLus = doc?.[CLE_PLAFONDS];
      if (plafondsLus && typeof plafondsLus === 'object' && !Array.isArray(plafondsLus)) {
        for (const [panId, valeur] of Object.entries(plafondsLus as Record<string, unknown>)) {
          if (typeof valeur === 'number' && Number.isInteger(valeur) && valeur >= 1) memoriser(panId, [], valeur);
        }
      }
      const zones = doc?.zones;
      if (!Array.isArray(zones)) return;
      for (const zone of zones) {
        const panId = zone?.id;
        const geometrie = zone?.geometry;
        if (!panId || !geometrie || !Array.isArray(geometrie.panels)) continue;
        const numerotes = geometrie.panels.filter((module) => typeof module?.n === 'number');
        if (numerotes.length) {
          memoriser(panId, numerotes);
          const copie = geometrie.panels.map((module) => ({ ...module }));
          derniers.set(panId, copie);
          engager(panId, copie);
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
    modulesEngages(panId: string) {
      return [...(engages.get(panId)?.values() ?? [])];
    },
    numerosAffiches(panId: string) {
      const affiches = new Map((historiques.get(panId) ?? HISTORIQUE_VIDE).numeros);
      for (const module of derniers.get(panId) ?? []) {
        if (typeof module.n === 'number' && Number.isInteger(module.n) && module.n >= 1) {
          affiches.set(cleEmplacement(module.cx, module.cy), module.n);
        }
      }
      return affiches;
    },
    provisoires(panId: string) {
      return provisoires.get(panId) ?? AUCUN_PROVISOIRE;
    },
    pans() {
      return [...historiques.keys()];
    },
    appliquer(panId, poses, convention, azimutDeg) {
      const resultat = attribuerNumeros(
        poses, historiques.get(panId) ?? HISTORIQUE_VIDE, convention, azimutDeg, provisoires.get(panId),
      );
      if (resultat.refus) return resultat;
      historiques.set(panId, resultat.historique);
      derniers.set(panId, resultat.modules);
      engager(panId, resultat.modules);
      if (resultat.numerotation) conventions.set(panId, resultat.numerotation);
      return resultat;
    },
    cloner() {
      // Les valeurs (historiques, listes) ne sont jamais modifiées en place : copier les cartes suffit.
      return creerRegistre({ historiques, conventions, derniers, engages, provisoires });
    },
    retenirLecture(copie: RegistreNumerotation) {
      for (const panId of copie.pans()) {
        const engagesPan = (historiques.get(panId) ?? HISTORIQUE_VIDE).numeros;
        const suite = new Map(copie.provisoires(panId));
        for (const [cle, numero] of copie.historique(panId).numeros) {
          if (!engagesPan.has(cle)) suite.set(cle, numero);
        }
        if (suite.size) provisoires.set(panId, suite);
        const affiches = copie.modules(panId);
        if (affiches.length) derniers.set(panId, affiches.map((module) => ({ ...module })));
      }
    },
    oublier() {
      historiques.clear();
      conventions.clear();
      derniers.clear();
      engages.clear();
      provisoires.clear();
    },
  };
  return registre;
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

/**
 * ACAL307 — la convention appliquée D'OFFICE à un pan pavé dans la session (D-ACAL,
 * « numérotation stable d'office ») : premier numéro 1, sens « ligne ». La saisie de
 * l'utilisateur et la convention déjà inscrite dans le document l'emportent toujours.
 */
export const CONVENTION_PAR_DEFAUT: Readonly<ConventionNumerotation> = { depart: 1, sens: 'ligne' };

/** ACAL307 — les pans où la numérotation d'office a été DÉSACTIVÉE (choix par pan). */
const pansSansNumerotation = new Set<string>();

/** ACAL307 — active (défaut) ou désactive la numérotation d'office d'UN pan. */
export function definirNumerotationPan(panId: string, active: boolean): void {
  if (active) pansSansNumerotation.delete(panId);
  else pansSansNumerotation.add(panId);
}

/** ACAL307 — la numérotation d'office est-elle active sur ce pan ? */
export function numerotationPanActive(panId: string): boolean {
  return !pansSansNumerotation.has(panId);
}

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
  pansSansNumerotation.clear(); // ACAL307
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
 *
 * Numérotation stable (suite ACAL1720) — SEUL un enregistrement (`engager: true`) engage des numéros :
 * toute autre sérialisation (sondage « modifié ? » de 1,5 s, capture du pan quitté, accès solaire) travaille
 * sur une COPIE du registre et n'en garde que ce qu'elle a montré (numéros provisoires, jamais engagés) —
 * glisser une inclinaison ne dépense plus de numéros. Les deux passages rendent les MÊMES numéros pour la
 * même pose (l'enregistrement engage ce que l'écran montrait). Puis la clé racine `plafondsNumerotation`
 * garde le plafond d'un pan dont les modules du haut sont retirés : un numéro n'est jamais redonné, même
 * après réouverture. Elle n'est écrite que dans ce cas — un document qui ne la porte pas ressort identique.
 */
export function numeroterDocument(
  document: unknown,
  etat: SaisieNumerotation = saisie,
  registre: RegistreNumerotation = registreAtelier,
  options: { pansPaves?: ReadonlySet<string>; engager?: boolean } = {},
): RefusNumerotation | null {
  const travail = options.engager === true ? registre : registre.cloner();
  const refus = numeroterSur(document, etat, travail, options.pansPaves);
  ecrirePlafonds(document, travail);
  if (travail !== registre) registre.retenirLecture(travail);
  return refus;
}

/** Suite ACAL1720 — la clé racine `plafondsNumerotation` : par pan, le plafond ENGAGÉ quand il dépasse le plus
 *  haut `n` encore posé (modules du haut retirés, ou pan supprimé) ; aucun pan dans ce cas ⇒ aucune clé. Les
 *  numéros provisoires sont tous posés : ils ne la font jamais apparaître (lecture et enregistrement concordent). */
function ecrirePlafonds(document: unknown, registre: RegistreNumerotation): void {
  if (!document || typeof document !== 'object') return;
  const doc = document as DocumentNumerotable & Record<string, unknown>;
  const plusHaut = new Map<string, number>();
  for (const zone of Array.isArray(doc.zones) ? doc.zones : []) {
    if (!zone?.id) continue;
    let haut = plusHaut.get(zone.id) ?? 0;
    const panneaux = zone.geometry?.panels;
    for (const module of Array.isArray(panneaux) ? panneaux : []) {
      if (typeof module?.n === 'number' && Number.isInteger(module.n) && module.n > haut) haut = module.n;
    }
    plusHaut.set(zone.id, haut);
  }
  const plafonds: Record<string, number> = {};
  for (const panId of registre.pans().sort()) {
    const plafond = registre.historique(panId).plafond;
    if (plafond > (plusHaut.get(panId) ?? 0)) plafonds[panId] = plafond;
  }
  if (Object.keys(plafonds).length) doc[CLE_PLAFONDS] = plafonds;
  else delete doc[CLE_PLAFONDS];
}

/**
 * Revue du lot 8 (suite ACAL1720) — INVARIANT : un numéro ENGAGÉ désigne UNE place pour toujours. Un document
 * ne peut donc jamais engager un numéro que la mémoire engagée donne à une AUTRE place, ni un numéro au plus
 * égal au plafond engagé pour une place qu'elle ne connaît pas (un numéro montré seulement à titre provisoire,
 * puis redonné et engagé ailleurs, revenait par une géométrie capturée ou une photo d'annulation).
 * Un `n` porté par le document n'est gardé que :
 *   • à la place où la mémoire engagée le donne ;
 *   • ou à une place qu'elle ne connaît pas, au-delà de son plafond, et une seule fois par pan.
 * Sinon il est retiré et le pan est renuméroté (ajouté aux pans pavés). Appliqué aux DEUX passages (lecture et
 * enregistrement) : l'écran montre ce que l'enregistrement engagera. Rend les pans pavés, complétés.
 */
function assainirNumerosPortes(
  document: unknown,
  registre: RegistreNumerotation,
  pansPaves: ReadonlySet<string> | undefined,
): ReadonlySet<string> | undefined {
  const zones = (document as DocumentNumerotable | null)?.zones;
  if (!Array.isArray(zones)) return pansPaves;
  let paves = pansPaves;
  for (const zone of zones) {
    const panId = zone?.id;
    const panneaux = zone?.geometry?.panels;
    if (!panId || !Array.isArray(panneaux)) continue;
    const engage = registre.historique(panId);
    const gardes = new Set<number>();
    let retire = false;
    const assainis = panneaux.map((module) => {
      const n = module?.n;
      if (typeof n !== 'number') return module;
      const connu = engage.numeros.get(cleEmplacement(module.cx, module.cy));
      const valide = Number.isInteger(n) && n >= 1 && !gardes.has(n)
        && (connu === n || (connu === undefined && n > engage.plafond));
      if (valide) {
        gardes.add(n);
        return module;
      }
      retire = true;
      const sansNumero: ModuleNumerote = { ...module };
      delete sansNumero.n;
      return sansNumero;
    });
    if (!retire) continue;
    zone.geometry!.panels = assainis;
    paves = new Set([...(paves ?? []), panId]);
  }
  return paves;
}

function numeroterSur(
  document: unknown,
  etat: SaisieNumerotation,
  registre: RegistreNumerotation,
  pansPaves: ReadonlySet<string> | undefined,
): RefusNumerotation | null {
  pansPaves = assainirNumerosPortes(document, registre, pansPaves); // revue lot 8 — jamais deux places pour un numéro
  registre.absorberDocument(document);
  if (!etat.actif) {
    // ACAL31 — bascule éteinte : LECTURE SEULE. Les numéros déjà absorbés (document rouvert)
    // sont réécrits sur les mêmes emplacements — aucune attribution neuve, aucun numéro
    // perdu parce que le pan actif a été re-pavé.
    reecrireNumerosAbsorbes(document, registre);
    // ACAL307 — NUMÉROTATION D'OFFICE : un pan PAVÉ dans la session (geste de pavage ou de
    // repavage, désigné par l'appelant) reçoit ses numéros sans geste de numérotation, avec
    // la convention par défaut ; un module gardé garde son `n`. Un document rouvert et
    // enregistré sans geste n'est jamais numéroté ici (aucun pan pavé).
    if (pansPaves && pansPaves.size) {
      const zones = (document as DocumentNumerotable | null)?.zones;
      if (Array.isArray(zones)) {
        for (const zone of zones) {
          const panId = zone?.id;
          const geometrie = zone?.geometry;
          if (!panId || !pansPaves.has(panId) || !numerotationPanActive(panId)) continue;
          if (!geometrie || !Array.isArray(geometrie.panels) || !geometrie.panels.length) continue;
          const saisieDefaut: SaisieNumerotation = {
            ...etat,
            depart: etat.depart ?? CONVENTION_PAR_DEFAUT.depart ?? 1,
            sens: etat.sens ?? CONVENTION_PAR_DEFAUT.sens ?? 'ligne',
          };
          const resultat = registre.appliquer(
            panId,
            geometrie.panels,
            conventionDuPan(registre.convention(panId), saisieDefaut),
            geometrie.azimuthDeg ?? 0,
          );
          if (resultat.refus) continue;
          geometrie.panels = resultat.modules;
          if (resultat.numerotation) geometrie.numerotation = resultat.numerotation;
        }
      }
    }
    return null;
  }
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

/** ACAL31 — réécrit `n`/`rangee`/`numerotation` absorbés sur les emplacements identiques. */
function reecrireNumerosAbsorbes(document: unknown, registre: RegistreNumerotation): void {
  const zones = (document as DocumentNumerotable | null)?.zones;
  if (!Array.isArray(zones)) return;
  for (const zone of zones) {
    const panId = zone?.id;
    const geometrie = zone?.geometry;
    if (!panId || !geometrie || !Array.isArray(geometrie.panels)) continue;
    const absorbes = registre.modulesEngages(panId); // suite ACAL1720 — jamais un numéro provisoire
    if (absorbes.length) {
      const parPlace = new Map(absorbes.map((m) => [cleEmplacement(m.cx, m.cy), m]));
      geometrie.panels = geometrie.panels.map((p) => {
        const m = parPlace.get(cleEmplacement(p.cx, p.cy));
        if (!m) return p;
        return {
          ...p,
          ...(typeof m.n === 'number' && p.n === undefined ? { n: m.n } : {}),
          ...(typeof m.rangee === 'string' && p.rangee === undefined ? { rangee: m.rangee } : {}),
        };
      });
    }
    const convention = registre.convention(panId);
    if (convention && !geometrie.numerotation) geometrie.numerotation = { ...convention };
  }
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

/** R3 (visuel lot 7) — les modules RENDUS du pan `panId` au dernier rendu 3D du pan actif, dans l'ordre des
 *  instances (celui de `ctx.activePanelCellIndex`, même filtre dans `scene3d.ts::buildZoneMeshes`) ; `null` si le
 *  dernier rendu n'était pas ce pan. Lecture seule : sert à apparier une cellule à SON emplacement. */
export function modulesRendus(panId: string): readonly ModulePose[] | null {
  return derniereDemande && derniereDemande.panId === panId ? derniereDemande.modules : null;
}

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
    registre.numerosAffiches(demande.panId), // suite ACAL1720 — provisoires compris (ils sont au document montré)
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
