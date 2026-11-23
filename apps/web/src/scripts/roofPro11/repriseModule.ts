/**
 * ACAL1416 — « Effacer » efface la géométrie, pas le choix de matériel : le pan retracé garde le module
 * (et le drapeau « choisi », ACAL1415) du pan effacé quand quelqu'un l'avait CHOISI. Un module « de
 * départ » (jamais choisi) n'est pas repris : le pan neuf repart du module de départ du catalogue.
 */
import { type AreaRecord } from './types';
import { type PanAuChoix } from './zones';

/** Le pan dont le module est repris : l'actif s'il a été choisi, sinon le premier pan au module choisi. */
export function panAuModuleChoisi(pans: readonly AreaRecord[], activeId: string): PanAuChoix | undefined {
  const choisi = (p: AreaRecord): boolean => !!p.moduleId && !!(p as PanAuChoix).moduleChoisi;
  return (pans.find((p) => p.id === activeId && choisi(p)) ?? pans.find(choisi)) as PanAuChoix | undefined;
}

/** Pose sur le pan neuf le module choisi du pan effacé (rien à reprendre : le pan neuf reste tel quel). */
export function reprendreModuleChoisi(neuf: AreaRecord, efface: PanAuChoix | undefined): AreaRecord {
  if (efface?.moduleId) {
    neuf.moduleId = efface.moduleId;
    (neuf as PanAuChoix).moduleChoisi = true;
  }
  return neuf;
}

/** « Effacer » : `pans` ne contient plus que le pan vierge (rendu), qui garde le module choisi du pan actif effacé. */
export function remplacerParPanVierge(pans: AreaRecord[], activeId: string, creer: () => AreaRecord): AreaRecord {
  const efface = panAuModuleChoisi(pans, activeId);
  pans.length = 0;
  const neuf = reprendreModuleChoisi(creer(), efface);
  pans.push(neuf);
  return neuf;
}
