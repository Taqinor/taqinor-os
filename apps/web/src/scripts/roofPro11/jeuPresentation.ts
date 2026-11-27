// ACAL1839 — le JEU DE MATÉRIAUX « présentation » de la scène 3D (« Montrer au client », maquettes TelephoneClient et
// Presentation, LANGAGE.md) : murs clairs, pignons sable, toit coloré selon son type servi (en pente : tuile ; plat :
// béton), cheminée brique, panneaux bleu nuit à cellules et cadre clairs (panelTexture.ts, jeu « presentation »).
// Teintes d'APPARENCE nommées, jamais une donnée ; l'atelier garde ses matériaux de travail (jeu « atelier »).
import * as THREE from 'three';
import { DEG2RAD } from './constants';
import { type JeuPanneau } from './panelTexture';
import { ELEVATION_AFFICHAGE_MIN_DEG, ringsBBox } from './threeShared';

export const TEINTES_PRESENTATION = {
  mur: 0xf3e9d6,
  pignon: 0xe6d6ba,
  tuile: 0xb8714f,
  beton: 0xd9d5cc,
  cheminee: 0x9a7b66,
  cadre: 0xdfe5f3,
} as const;

type OptsPresentation = { productionAtelier?: unknown; presentationClient?: boolean } | null | undefined;

/** Lot 8 (D-ACAL-132) — la visionneuse des liens de CONFIANCE porte l'habit « Montrer au client » ; l'ERP
 *  (`productionAtelier`) ignore ce drapeau : il a son propre interrupteur (`enPresentation`). */
export function presentationClient(opts: OptsPresentation): boolean {
  return opts?.productionAtelier === undefined && opts?.presentationClient === true;
}

/** Les boîtes d'obstacle portent et reçoivent les ombres (assises sur la dalle) : l'atelier ERP, et le lien de confiance
 *  (lot 8 — sans quoi un panneau teinté « ombragé » n'a aucune cause visible). Lien standard : inchangé, sans ombre. */
export function ombresObstacles(opts: OptsPresentation): boolean {
  return opts?.productionAtelier !== undefined || presentationClient(opts);
}

/** Le jeu de matériaux de la scène : « presentation » dans l'ERP montré au client, ou sur un lien de confiance. */
export function jeuDeLaScene(opts: OptsPresentation, erpEnPresentation: boolean): JeuPanneau {
  return erpEnPresentation || presentationClient(opts) ? 'presentation' : 'atelier';
}

// ── Lot 8 (B2) — le SOL qui reçoit les ombres, sur le lien de confiance ──
// La carte satellite est dessinée par MapLibre, HORS de la scène Three : rien n'y recevait l'ombre du bâtiment ni
// des rangées. Un plan au sol en matériau d'OMBRE seule (transparent là où il n'y a pas d'ombre : l'imagerie n'est
// ni couverte ni teintée) la reçoit. Son étendue suit l'ombre la plus longue que la lecture montre : le soleil le
// plus bas affiché (`ELEVATION_AFFICHAGE_MIN_DEG`) sur la hauteur du bâtiment, châssis compris, plafonnée.

/** Hauteur ajoutée au mur pour le haut des châssis et des panneaux (m) — borne d'APPARENCE de l'étendue d'ombre. */
export const MARGE_POSE_M = 1.5;
/** Plafond de la longueur d'ombre au sol (m) : au-delà, une carte d'ombre de 2 048 px deviendrait trop grossière. */
export const PORTEE_OMBRE_SOL_MAX_M = 80;
/** Opacité de l'ombre portée au sol (apparence). */
export const OPACITE_OMBRE_SOL = 0.32;

/** Longueur de l'ombre la plus longue au sol (m) : (mur + pose) ÷ tan(soleil le plus bas affiché), plafonnée. */
export function porteeOmbreSolM(murM: number): number {
  return Math.min(PORTEE_OMBRE_SOL_MAX_M, (murM + MARGE_POSE_M) / Math.tan(ELEVATION_AFFICHAGE_MIN_DEG * DEG2RAD));
}

/** Centre et demi-côté du carré qui contient les pans et leur ombre la plus longue, dans toutes les directions. */
function etendueOmbre(rings: readonly (readonly [number, number])[][], murM: number) {
  const { minX, minY, maxX, maxY } = ringsBBox(rings as [number, number][][]);
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, demi: Math.hypot(maxX - minX, maxY - minY) / 2 + porteeOmbreSolM(murM) };
}

/** Demi-côté du cadre d'ombre du soleil : celui de la scène, élargi au sol sur le lien de confiance (ERP : inchangé). */
export function cadreOmbreClient(opts: OptsPresentation, span: number, rings: readonly (readonly [number, number])[][], murM: number): number {
  return presentationClient(opts) && rings.length ? Math.max(span, etendueOmbre(rings, murM).demi) : span;
}

/** Le sol qui reçoit les ombres (lien de confiance seulement ; ERP et liens standard : aucun). */
export function solOmbreClient(opts: OptsPresentation, rings: readonly (readonly [number, number])[][], murM: number): THREE.Mesh[] {
  if (!presentationClient(opts) || !rings.length) return [];
  const { cx, cy, demi } = etendueOmbre(rings, murM);
  const sol = new THREE.Mesh(new THREE.PlaneGeometry(2 * demi, 2 * demi), new THREE.ShadowMaterial({ opacity: OPACITE_OMBRE_SOL, depthWrite: false }));
  sol.name = 'sol-ombre-client';
  sol.position.set(cx, cy, 0.02); // au sol (le bâtiment monte de z = 0), juste au-dessus pour éviter le scintillement
  sol.receiveShadow = true;
  sol.castShadow = false;
  return [sol];
}

/** Teintes du bâtiment d'un pan : `null` = les matériaux de travail (atelier), inchangés. */
export function teintesBatiment(jeu: JeuPanneau, enPente: boolean): { mur: number; pignon: number; dalle: number } | null {
  if (jeu !== 'presentation') return null;
  const t = TEINTES_PRESENTATION;
  return { mur: t.mur, pignon: t.pignon, dalle: enPente ? t.tuile : t.beton };
}

/** Les murs d'un client sont CLAIRS même à l'ombre du soleil affiché (maquette) : une lueur propre de leur teinte. Vide hors
 *  présentation (aucune teinte) : matériau de travail inchangé. */
export function eclatPresentation(teinte: number | undefined): { emissive?: number; emissiveIntensity?: number } {
  return teinte == null ? {} : { emissive: teinte, emissiveIntensity: 0.38 };
}
