/**
 * ACAL308 (D-ACAL-20) — LE JEU DE RÉGLAGES MÉMORISÉ S'APPLIQUE À CHAQUE NOUVEAU PAN.
 *
 * Un calepinage créé avec un jeu de réglages société porte, à la racine de son document,
 * `jeuReglages = { presetId, libelle, valeurs }` : un INSTANTANÉ posé côté serveur
 * (`services/creation.py::_instantane_jeu`, ACAL186), jamais une référence vivante. Ce module
 * est la moitié ATELIER : il lit cet instantané et pose ses valeurs sur un pan NEUF, avant
 * son pavage. Rien d'autre :
 *
 *  - un pan EXISTANT n'est jamais touché (le jeu ne s'applique qu'à la création d'un pan) ;
 *  - une valeur modifiée à la main PRIME : le jeu n'est posé qu'une fois, à la naissance du
 *    pan, jamais ré-imposé ensuite ;
 *  - les champs posés sont EXACTEMENT ceux que `services/gabarits.appliquer_gabarit` pose
 *    côté serveur (`CLES_DE_ZONE`) — aucune seconde définition d'un jeu : `CLES_JEU` est
 *    une COPIE lue au build de cette liste, protégée par un test de parité qui lit le
 *    fichier Python. Les autres clés d'un jeu (`orientation`, `famille`, `rives`,
 *    `allee_m`, `priorite`) sont des `regles` du traducteur, que le document ne porte pas :
 *    elles ne sont pas des champs de pan ;
 *  - une valeur illisible (type faux, hors plage) est IGNORÉE, jamais devinée : le pan garde
 *    alors sa valeur par défaut sur ce point ;
 *  - `jeuReglages` voyage à l'aller-retour tel quel (document relu, D01-T12) : ce module ne
 *    le réécrit jamais.
 *
 * PURE : aucun accès DOM, aucune écriture hors du pan reçu.
 */
import { type AreaRecord, type RoofType } from './types';

/** `appliquer_gabarit.CLES_DE_ZONE` (backend `services/gabarits.py`) — parité testée. */
export const CLES_JEU = ['roofType', 'pitchDeg', 'facingAzimuthDeg', 'facingManual', 'neededAuto'] as const;
export type CleJeu = (typeof CLES_JEU)[number];

/** Le jeu mémorisé, tel que le document le porte. */
export interface JeuReglages {
  presetId: unknown;
  libelle: string;
  valeurs: Record<string, unknown>;
}

/** Les valeurs d'un jeu que l'atelier sait poser sur un pan (déjà validées). */
export type ValeursJeuPan = Partial<Pick<AreaRecord, 'roofType' | 'pitchDeg' | 'facingAzimuthDeg' | 'facingManual' | 'neededAuto'>>;

/** Relit `jeuReglages` du document ; `null` quand il est absent ou illisible. */
export function lireJeuReglages(document: unknown): JeuReglages | null {
  if (!document || typeof document !== 'object') return null;
  const brut = (document as Record<string, unknown>).jeuReglages;
  if (!brut || typeof brut !== 'object') return null;
  const valeurs = (brut as Record<string, unknown>).valeurs;
  if (!valeurs || typeof valeurs !== 'object' || Array.isArray(valeurs)) return null;
  const libelle = (brut as Record<string, unknown>).libelle;
  return {
    presetId: (brut as Record<string, unknown>).presetId ?? null,
    libelle: typeof libelle === 'string' ? libelle.trim() : '',
    valeurs: valeurs as Record<string, unknown>,
  };
}

const fini = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** Les valeurs du jeu applicables à un pan : seulement les clés de `CLES_JEU`, bien typées. */
export function valeursPourPan(jeu: JeuReglages | null): ValeursJeuPan {
  const sortie: ValeursJeuPan = {};
  if (!jeu) return sortie;
  const v = jeu.valeurs;
  if (v.roofType === 'flat' || v.roofType === 'pitched') sortie.roofType = v.roofType as RoofType;
  if (fini(v.pitchDeg) && v.pitchDeg >= 0 && v.pitchDeg <= 90) sortie.pitchDeg = v.pitchDeg;
  if (fini(v.facingAzimuthDeg) && v.facingAzimuthDeg >= 0 && v.facingAzimuthDeg <= 360) {
    sortie.facingAzimuthDeg = v.facingAzimuthDeg;
  }
  if (typeof v.facingManual === 'boolean') sortie.facingManual = v.facingManual;
  if (typeof v.neededAuto === 'boolean') sortie.neededAuto = v.neededAuto;
  return sortie;
}

/**
 * Pose les valeurs du jeu sur un pan NEUF (mutation du pan reçu, comme le fait le builder à
 * sa création). Rend les valeurs effectivement posées (vide = rien à poser), pour que
 * l'appelant aligne ses variables vives d'édition sur le pan.
 */
export function appliquerJeuAuPan(pan: AreaRecord, jeu: JeuReglages | null): ValeursJeuPan {
  const valeurs = valeursPourPan(jeu);
  Object.assign(pan, valeurs);
  return valeurs;
}

/** La mention de l'en-tête de l'atelier ; `''` sans jeu. */
export function mentionJeuReglages(jeu: JeuReglages | null): string {
  if (!jeu) return '';
  const nom = jeu.libelle || 'sans nom';
  return `Jeu de réglages ${nom} appliqué aux nouveaux pans`;
}
