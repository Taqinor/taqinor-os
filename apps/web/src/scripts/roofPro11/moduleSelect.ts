/**
 * CALX109 — LE MODULE POSÉ SUR CHAQUE PAN, AVEC SES VRAIES COTES.
 *
 * LE CONSTAT. L'atelier ne connaissait qu'UN module, écrit en dur avec ses cotes
 * (`../../lib/roofPro2.ts`) et propagé partout ; le kWc se calculait `nombre × PANEL2_WATT`,
 * donc deux modèles sur deux pans auraient rendu un kWc faux. Le catalogue de la société
 * existe pourtant côté serveur (`GET calepinages/<pk>/modules-disponibles/`, CALX109) et le
 * document sait déjà porter plusieurs modèles (`modules[]` + `zones[].geometry.moduleId`,
 * contrat CALX82).
 *
 * CE MODULE EST PUR. Aucune dépendance à Three, à MapLibre, au DOM ni au `ctx` : il ne
 * fait que deux choses, chacune testable seule —
 *   1. LIRE la réponse serveur et en tirer le catalogue sélectionnable (CALX109) ;
 *   2. RÉSOUDRE le module d'un pan (le sien, ou le module par défaut de l'atelier, NOMMÉ)
 *      et en tirer les cotes de pavage, ou un REFUS qui nomme le champ manquant ;
 *
 * ZÉRO CHIFFRE INVENTÉ (D-CALX 7). Une cote absente de la fiche n'est jamais remplacée par
 * une dimension standard ni par celle du module d'hier : le module est REFUSÉ en nommant le
 * champ, exactement comme la porte d'import refuse un `moduleId` absent du catalogue.
 *
 * CE QUI MANQUE ENCORE, ET QUI N'EST PAS ICI. Le sélecteur VISIBLE (le contrôle DOM que le
 * constructeur crée lui-même, patron `obstaclesUi.ts`) et le pavage 3D par module
 * (`optimizer.ts` / `estimatorBrainV2.ts`) appartiennent à d'autres fichiers — voir les
 * crochets nommés dans le rapport de la lane. Tout ce dont ils ont besoin est ici, pur.
 */
import {
  MODULE_ATELIER_PAR_DEFAUT,
  type Panel2Module,
} from '../../lib/roofPro2';

/** CALX82 — UNE entrée du catalogue `modules[]` du document v2, à l'identique. */
export interface ModuleDocument {
  /** Identifiant STABLE du modèle DANS le document (`produit-<pk>` côté catalogue). */
  id: string;
  /** Fiche `stock.Produit` d'origine, ou `null` pour un modèle saisi à la main. */
  produitId: number | null;
  /** Libellé FRANÇAIS affiché dans le sélecteur. */
  libelle: string;
  /** Cotes hors-tout (mm). `null` = la fiche ne la porte pas — jamais une valeur supposée. */
  longueurMm: number | null;
  largeurMm: number | null;
  epaisseurMm: number | null;
  poidsKg: number | null;
  /** Puissance crête unitaire (Wc). `null` = non renseignée. */
  pmaxWc: number | null;
  /** D'où viennent les valeurs ci-dessus, en clair (obligatoire au schéma). */
  source: string;
}

/** CALX109 — une entrée de la réponse serveur : le module + l'état de SA fiche. */
export interface ModuleDisponible {
  module: ModuleDocument;
  selectionnable: boolean;
  champs_manquants: string[];
  motif: string | null;
}

/** CALX109 — la réponse de `GET calepinages/<pk>/modules-disponibles/`. */
export interface ModulesDisponibles {
  calepinage: number | null;
  modules: ModuleDisponible[];
  champs_requis: string[];
  motif_liste_vide: string | null;
}

/** Le catalogue tel que l'atelier le tient une fois la réponse lue. */
export interface CatalogueModules {
  /** Les modèles que l'on peut réellement poser (fiche complète). */
  choisissables: ModuleDocument[];
  /** Les modèles LISTÉS mais grisés, avec le motif serveur — jamais cachés. */
  grises: ModuleDisponible[];
  /** Pourquoi la liste choisissable est vide, ou `null`. Texte du SERVEUR, jamais inventé. */
  motifListeVide: string | null;
}

/** Un refus NOMMÉ : le champ fautif et le message affiché sous ce champ. */
export interface RefusModule {
  champ: string;
  message: string;
}

/** L'affectation courante : le catalogue + le module choisi pour chaque pan. */
export interface AffectationModules {
  catalogue: readonly ModuleDocument[];
  /** id de pan -> `id` de module. Un pan absent pose le module par défaut de l'atelier. */
  parPan: Readonly<Record<string, string | undefined>>;
}

/** L'identifiant réservé au module par défaut de l'atelier — jamais celui d'une fiche. */
export const ID_MODULE_PAR_DEFAUT = 'atelier-defaut';

/**
 * CALX109 — LE MODULE PAR DÉFAUT DE L'ATELIER, sous la forme du document.
 *
 * C'est le repli EXPLICITE tant qu'aucun `moduleId` n'est choisi : ses cotes sont celles de
 * `roofPro2.ts` (converties une seule fois, ici, des mètres vers les millimètres du
 * document) et sa `source` le dit en toutes lettres. Aucune marque n'y figure : le libellé
 * décrit le module par ses cotes, qui sont ce qui change le calepinage.
 */
export const MODULE_PAR_DEFAUT_ATELIER: ModuleDocument = {
  id: ID_MODULE_PAR_DEFAUT,
  produitId: null,
  libelle: "Module par défaut de l'atelier (2,384 × 1,303 m, 720 Wc)",
  longueurMm: MODULE_ATELIER_PAR_DEFAUT.longM * 1000,
  largeurMm: MODULE_ATELIER_PAR_DEFAUT.courtM * 1000,
  epaisseurMm: (MODULE_ATELIER_PAR_DEFAUT.epaisM ?? 0) * 1000 || null,
  poidsKg: null,
  pmaxWc: MODULE_ATELIER_PAR_DEFAUT.watt,
  source: "module par défaut de l'atelier",
};

/** Les cotes SANS LESQUELLES on ne sait pas paver, et leur nom français. */
const CHAMPS_DE_PAVAGE: ReadonlyArray<[keyof ModuleDocument, string]> = [
  ['longueurMm', 'la longueur (mm)'],
  ['largeurMm', 'la largeur (mm)'],
  ['pmaxWc', 'la puissance crête (Wc)'],
];

/** `true` si la valeur est un nombre fini strictement positif — sinon NON RENSEIGNÉE. */
function positif(valeur: unknown): valeur is number {
  return typeof valeur === 'number' && Number.isFinite(valeur) && valeur > 0;
}

/** Distingue un refus d'un résultat, sans `instanceof` (tout est du JSON ici). */
export function estRefus(valeur: unknown): valeur is RefusModule {
  return !!valeur && typeof valeur === 'object'
    && typeof (valeur as RefusModule).champ === 'string'
    && typeof (valeur as RefusModule).message === 'string';
}

/** Normalise UNE entrée de catalogue venue du serveur. `null` si elle est inexploitable. */
function lireModule(brut: unknown): ModuleDocument | null {
  if (!brut || typeof brut !== 'object') return null;
  const o = brut as Record<string, unknown>;
  const id = typeof o.id === 'string' ? o.id.trim() : '';
  const libelle = typeof o.libelle === 'string' ? o.libelle.trim() : '';
  const source = typeof o.source === 'string' ? o.source.trim() : '';
  // Les trois champs OBLIGATOIRES du schéma (CALX82). Sans eux l'entrée n'est pas un
  // module du document : on la laisse tomber plutôt que de la compléter.
  if (!id || !libelle || !source) return null;
  const cote = (cle: string): number | null => (positif(o[cle]) ? (o[cle] as number) : null);
  return {
    id,
    produitId: typeof o.produitId === 'number' ? o.produitId : null,
    libelle,
    longueurMm: cote('longueurMm'),
    largeurMm: cote('largeurMm'),
    epaisseurMm: cote('epaisseurMm'),
    poidsKg: cote('poidsKg'),
    pmaxWc: cote('pmaxWc'),
    source,
  };
}

/**
 * CALX109 — lit la réponse serveur et en tire le catalogue de l'atelier.
 *
 * DÉFENSIF PAR CONSTRUCTION : une réponse absente, tronquée ou mal formée ne jette jamais —
 * elle rend un catalogue vide, et le motif du serveur quand il y en a un. Une fiche grisée
 * reste LISTÉE avec son motif : le commercial doit voir qu'elle existe et pourquoi elle ne
 * se choisit pas.
 */
export function lireModulesDisponibles(reponse: unknown): CatalogueModules {
  const vide: CatalogueModules = { choisissables: [], grises: [], motifListeVide: null };
  if (!reponse || typeof reponse !== 'object') return vide;
  const o = reponse as Partial<ModulesDisponibles>;
  const lignes = Array.isArray(o.modules) ? o.modules : [];
  const choisissables: ModuleDocument[] = [];
  const grises: ModuleDisponible[] = [];
  for (const ligne of lignes) {
    if (!ligne || typeof ligne !== 'object') continue;
    const module = lireModule((ligne as ModuleDisponible).module);
    if (!module) continue;
    const manquants = CHAMPS_DE_PAVAGE.filter(([cle]) => !positif(module[cle])).map(([cle]) => cle);
    // Le serveur tranche ; on ne re-décide pas à sa place — mais une entrée dont une cote
    // de pavage manque n'est JAMAIS choisissable, même si le serveur le prétendait.
    const ok = (ligne as ModuleDisponible).selectionnable !== false && manquants.length === 0;
    if (ok) choisissables.push(module);
    else {
      grises.push({
        module,
        selectionnable: false,
        champs_manquants: Array.isArray((ligne as ModuleDisponible).champs_manquants)
          ? (ligne as ModuleDisponible).champs_manquants
          : (manquants as string[]),
        motif: typeof (ligne as ModuleDisponible).motif === 'string'
          ? (ligne as ModuleDisponible).motif
          : null,
      });
    }
  }
  return {
    choisissables,
    grises,
    motifListeVide: choisissables.length
      ? null
      : (typeof o.motif_liste_vide === 'string' ? o.motif_liste_vide : null),
  };
}

/**
 * CALX109 — les cotes de pavage d'un module, ou un REFUS qui nomme le champ.
 *
 * Le grand côté est la plus grande des deux dimensions : un pavage se raisonne en
 * « le long de la rangée » / « dans le sens de la pente », pas en longueur/largeur de fiche.
 * Une cote manquante ne retombe JAMAIS sur le module d'aujourd'hui.
 */
export function cotesDeModule(module: ModuleDocument): Panel2Module | RefusModule {
  const manquants = CHAMPS_DE_PAVAGE.filter(([cle]) => !positif(module[cle]));
  if (manquants.length) {
    return {
      champ: manquants[0][0] as string,
      message: `« ${module.libelle} » ne peut pas être calepiné : ${manquants
        .map(([, nom]) => nom)
        .join(', ')} ${manquants.length === 1 ? "n'est pas renseignée" : 'ne sont pas renseignées'}`
        + ' sur sa fiche produit. Complétez la fiche, puis rechargez le catalogue.',
    };
  }
  const a = module.longueurMm as number;
  const b = module.largeurMm as number;
  return {
    longM: Math.max(a, b) / 1000,
    courtM: Math.min(a, b) / 1000,
    epaisM: positif(module.epaisseurMm) ? (module.epaisseurMm as number) / 1000 : null,
    watt: module.pmaxWc as number,
  };
}

/**
 * CALX82/CALX109 — le module POSÉ sur un pan.
 *
 * Aucun `moduleId` ⇒ le module par défaut de l'atelier, NOMMÉ (jamais un repli muet).
 * Un `moduleId` ABSENT du catalogue ⇒ REFUS nommant `moduleId` : c'est exactement la règle
 * de la porte d'import (`services/io_layout.py`, CALX82) — un pan qui désigne un modèle
 * introuvable n'a ni cotes ni poids, donc aucune surface vérifiable ; mieux vaut un refus
 * lisible qu'un pan repavé en silence avec le module d'un autre.
 */
export function resoudreModuleDuPan(
  catalogue: readonly ModuleDocument[],
  moduleId: string | null | undefined,
): ModuleDocument | RefusModule {
  const id = typeof moduleId === 'string' ? moduleId.trim() : '';
  if (!id) return MODULE_PAR_DEFAUT_ATELIER;
  if (id === ID_MODULE_PAR_DEFAUT) return MODULE_PAR_DEFAUT_ATELIER;
  const trouve = catalogue.find((m) => m.id === id);
  if (trouve) return trouve;
  return {
    champ: 'moduleId',
    message: `Le module « ${id} » ne figure pas dans le catalogue de ce document :`
      + ' choisissez un module de la liste, ou rechargez le catalogue de la société.',
  };
}

/** CALX109 — les cotes à paver pour un pan, ou le refus nommé qui l'en empêche. */
export function cotesPourPan(
  catalogue: readonly ModuleDocument[],
  moduleId: string | null | undefined,
): Panel2Module | RefusModule {
  const module = resoudreModuleDuPan(catalogue, moduleId);
  return estRefus(module) ? module : cotesDeModule(module);
}
