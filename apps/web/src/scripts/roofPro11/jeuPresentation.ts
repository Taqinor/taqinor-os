// ACAL1839 — le JEU DE MATÉRIAUX « présentation » de la scène 3D (« Montrer au client », maquettes TelephoneClient et
// Presentation, LANGAGE.md) : murs clairs, pignons sable, toit coloré selon son type servi (en pente : tuile ; plat :
// béton), cheminée brique, panneaux bleu nuit à cellules et cadre clairs (panelTexture.ts, jeu « presentation »).
// Teintes d'APPARENCE nommées, jamais une donnée ; l'atelier garde ses matériaux de travail (jeu « atelier »).
import { type JeuPanneau } from './panelTexture';

export const TEINTES_PRESENTATION = {
  mur: 0xf3e9d6,
  pignon: 0xe6d6ba,
  tuile: 0xb8714f,
  beton: 0xd9d5cc,
  cheminee: 0x9a7b66,
  cadre: 0xdfe5f3,
} as const;

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
