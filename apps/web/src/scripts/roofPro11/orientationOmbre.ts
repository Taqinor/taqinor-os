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

/** La pose d'une grille : un plafond, ou (ACAL1533) la pose EFFECTIVE `poseSousSeuil` — nombre posé et cellules
 *  retenues quand le seuil d'accès solaire en a écarté. */
export type PoseDe = (g: PoseGrille) => number | { placed: number; occupied?: Set<number> };

/** Les deux lignes chiffrées, ou `null` quand aucune source d'ombre n'est saisie
 *  (`accesDe` rend `null`) — jamais un 1 inventé. `placedDe` = la pose du pan (plafond ou pose sous seuil). */
export function lignesSensDePose(
  pack: { portrait: PoseGrille; landscape: PoseGrille },
  accesDe: (panels: readonly { cx: number; cy: number }[]) => number[] | null,
  placedDe: PoseDe,
): LigneSensDePose[] | null {
  const lignes: LigneSensDePose[] = [];
  for (const sens of ['portrait', 'landscape'] as const) {
    const g = pack[sens];
    const p = placedDe(g);
    const n = Math.min(typeof p === 'number' ? p : p.placed, g.panels.length);
    const occupees = typeof p === 'number' ? undefined : p.occupied;
    // ACAL1533 — l'accès moyen des cellules RÉELLEMENT posées (seuil appliqué), sinon des `n` premières.
    const vus = accesDe(occupees ? g.panels.filter((_, i) => occupees.has(i)) : g.panels.slice(0, n));
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

/** ACAL1533 — le choix d'un sens, fourni par l'optimiseur (il tient la pose affichée et ne change que le sens) ;
 *  absent : le clic retombe sur la puce `data-orient` (comportement d'ACAL552). */
let choisirSens: ((sens: SensDePose) => void) | null = null;

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
    if (!l) return;
    const sens = l.dataset.orientOmbre as SensDePose;
    if (choisirSens) choisirSens(sens);
    else document.querySelector<HTMLButtonElement>(`[data-orient="${sens}"]`)?.click();
  });
  return box;
}

/** Affiche (ou cache) les deux lignes sous la rangée de puces `data-orient`. ACAL1533 — `affichee` = le sens de la
 *  pose DESSINÉE (la ligne marquée la suit, même en « auto ») ; `choisir` = ce que fait un clic sur une ligne. */
export function afficherSensDePose(
  lignes: LigneSensDePose[] | null,
  opts: { affichee?: string; choisir?: (sens: SensDePose) => void } = {},
): void {
  choisirSens = opts.choisir ?? null;
  const box = hote();
  if (!box) return;
  if (!lignes || !modeExpertActif()) {
    box.hidden = true;
    box.innerHTML = '';
    return;
  }
  const choisie = opts.affichee ?? document.querySelector<HTMLElement>('[data-orient][aria-pressed="true"]')?.dataset.orient;
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
