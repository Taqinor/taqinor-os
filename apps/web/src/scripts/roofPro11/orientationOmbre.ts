/**
 * ACAL552 — sous les puces Portrait / Paysage d'un toit plat ombré : les deux poses
 * chiffrées (panneaux posés, accès solaire moyen MESURÉ). Rien n'est affiché sans
 * obstruction retenue (jamais « 100 % » sans mesure) ; aucun montant, aucune valeur
 * par défaut. Lecture dérivée du pavage : rien n'est persisté.
 */
import { $, esc } from './dom';

export interface PoseGrille {
  panels: readonly { cx: number; cy: number }[];
}
export type SensDePose = 'portrait' | 'landscape';
export interface LigneSensDePose {
  sens: SensDePose;
  n: number;
  /** Moyenne de l'accès solaire (0..1) sur les `n` premiers emplacements. */
  acces: number;
}

/** Les deux lignes chiffrées, ou `null` quand aucune source d'ombre n'est saisie
 *  (`accesDe` rend `null`) — jamais un 1 inventé. `placedDe` = plafond de pose du pan. */
export function lignesSensDePose(
  pack: { portrait: PoseGrille; landscape: PoseGrille },
  accesDe: (panels: readonly { cx: number; cy: number }[]) => number[] | null,
  placedDe: (g: PoseGrille) => number,
): LigneSensDePose[] | null {
  const lignes: LigneSensDePose[] = [];
  for (const sens of ['portrait', 'landscape'] as const) {
    const g = pack[sens];
    const n = Math.min(placedDe(g), g.panels.length);
    const vus = accesDe(g.panels.slice(0, n));
    if (!vus) return null;
    const acces = vus.length ? vus.reduce((a, b) => a + b, 0) / vus.length : 0;
    lignes.push({ sens, n, acces });
  }
  return lignes;
}

/** Mode Expert : lu dans l'adresse (`?mode=expert`, comme `Rail.jsx::useModeExpert`) ou
 *  sur `data-mode-expert` du corps de page (posé par l'écran guidé/expert). */
export function modeExpertActif(): boolean {
  try {
    if (new URLSearchParams(window.location.search).get('mode') === 'expert') return true;
    return document.body?.dataset.modeExpert === '1';
  } catch {
    return false;
  }
}

function hote(): HTMLElement | null {
  const existant = $('rp9-orient-ombre');
  if (existant) return existant;
  const rangee = document.querySelector<HTMLElement>('[data-orient]')?.parentElement;
  if (!rangee || typeof document.createElement !== 'function') return null;
  const box = document.createElement('div');
  box.id = 'rp9-orient-ombre';
  box.className = 'space-y-1 text-xs text-lune-soft';
  box.hidden = true;
  rangee.insertAdjacentElement('afterend', box);
  box.addEventListener('click', (e) => {
    const l = (e.target as HTMLElement).closest<HTMLElement>('[data-orient-ombre]');
    if (l) document.querySelector<HTMLButtonElement>(`[data-orient="${l.dataset.orientOmbre}"]`)?.click();
  });
  return box;
}

/** Affiche (ou cache) les deux lignes sous la rangée de puces `data-orient`. */
export function afficherSensDePose(lignes: LigneSensDePose[] | null): void {
  const box = hote();
  if (!box) return;
  if (!lignes || !modeExpertActif()) {
    box.hidden = true;
    box.innerHTML = '';
    return;
  }
  const choisie = document.querySelector<HTMLElement>('[data-orient][aria-pressed="true"]')?.dataset.orient;
  box.innerHTML = lignes
    .map((l) => {
      const nom = l.sens === 'portrait' ? 'Portrait' : 'Paysage';
      const txt = `${nom} : ${l.n} panneaux, accès solaire moyen ${Math.round(l.acces * 100)} %`;
      const marque = choisie === l.sens ? ' font-semibold text-brass-300' : '';
      return `<button type="button" data-orient-ombre="${l.sens}" aria-pressed="${choisie === l.sens}"
        class="block min-h-[44px] w-full text-left${marque}">${esc(txt)}</button>`;
    })
    .join('');
  box.hidden = false;
}
