/**
 * ACAL412 — ANNULER / RÉTABLIR JOIGNABLES DÈS LE TRACÉ.
 *
 * L'historique de l'atelier (`createWorkshopHistory`, CAL100) photographie déjà tracé,
 * obstacles, zones et pose, et `obstaclesUi.ts` y pousse une photo à chaque sommet déplacé,
 * inséré ou supprimé. Mais ses seuls déclencheurs (Ctrl+Z et les boutons du panneau de
 * disposition) n'existaient que DANS ce panneau : hors de lui, aucun moyen d'annuler.
 *
 * Ce module pose deux boutons ↶ ↷ près de « Effacer » et un Ctrl+Z / Ctrl+Y global, qui
 * appellent `LayoutEditor.undo` / `redo` puis redessinent (`apres`). Il ne touche pas à
 * l'historique : il le rend joignable. Dans un champ de saisie, Ctrl+Z reste au navigateur ;
 * quand le mode disposition est actif, c'est le keydown de `layoutEditor.ts` qui répond (pas
 * de double annulation) ; sans rien à annuler la touche reste au navigateur et le bouton dit
 * « rien à annuler ».
 */
import type { LayoutEditor } from './layoutEditor';
import { estChampDeSaisie } from './clavier';

export interface AnnulerAtelierDeps {
  /** Le bouton « Effacer » : les deux boutons se posent juste avant. */
  ancre: HTMLElement | null;
  editeur: Pick<LayoutEditor, 'undo' | 'redo'>;
  /** Mode disposition actif : son propre keydown répond, on cède la place. */
  modeDisposition: () => boolean;
  /** Redessine ligne, obstacles et pavage après une restauration. */
  apres: () => void;
  setStatus: (msg: string) => void;
  /** ACAL1901 — reçoit `annulerGeste` : les boutons Annuler / Rétablir de la barre passent par le MÊME geste que Ctrl+Z. */
  ctx?: { annulerGeste?: { annuler: () => boolean; retablir: () => boolean } };
}

interface Frappe {
  key: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  target?: unknown;
  preventDefault?: () => void;
}

export function creerAnnulerAtelier(deps: AnnulerAtelierDeps): {
  annuler: () => boolean;
  retablir: () => boolean;
  surFrappe: (e: Frappe) => boolean;
} {
  const geste = (agir: () => boolean, fait: string, rien: string): boolean => {
    const ok = agir();
    if (ok) deps.apres();
    deps.setStatus(ok ? fait : rien);
    return ok;
  };
  const annuler = () => geste(deps.editeur.undo, 'Action annulée.', 'Rien à annuler.');
  const retablir = () => geste(deps.editeur.redo, 'Action rétablie.', 'Rien à rétablir.');
  if (deps.ctx) deps.ctx.annulerGeste = { annuler, retablir }; // ACAL1901
  const surFrappe = (e: Frappe): boolean => {
    if (!(e.ctrlKey || e.metaKey) || estChampDeSaisie(e.target) || deps.modeDisposition()) return false;
    const k = String(e.key).toLowerCase();
    const ok = k === 'z' && !e.shiftKey ? annuler() : k === 'y' || (k === 'z' && e.shiftKey) ? retablir() : false;
    if (ok) e.preventDefault?.();
    return ok;
  };
  const ancre = deps.ancre;
  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', (e) => void surFrappe(e));
    if (ancre?.parentElement) {
      for (const [libelle, nom, agir] of [
        ['↶', 'Annuler la dernière action', annuler],
        ['↷', 'Rétablir', retablir],
      ] as const) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = ancre.className;
        b.textContent = libelle;
        b.title = nom;
        b.setAttribute('aria-label', nom);
        b.addEventListener('click', () => void agir());
        ancre.parentElement.insertBefore(b, ancre);
      }
    }
  }
  return { annuler, retablir, surFrappe };
}
