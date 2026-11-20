/**
 * ACAL411 — BARRE « PIVOTER / ALIGNER / RÉPARTIR » SUR LA SÉLECTION DU PLACEMENT LIBRE.
 *
 * `layoutEditor.ts` expose `freeRotateSelection`, `freeAlignSelection` et
 * `freeDistributeSelection` (CAL80, CAL81) mais aucun bouton ne les appelait. Cette barre
 * (posée dans le conteneur de la carte, comme `#rp9-marquee`) les appelle sur la sélection
 * courante ; aucun calcul de géométrie ici. Un refus NOMME sa raison. Visible seulement en
 * placement libre et avec au moins un panneau sélectionné (jamais en emplacements validés).
 *
 * ACAL418 — « Retirer la sélection » : le geste caché Alt + clic reçoit un bouton visible, en
 * emplacements validés (`removeCells`, refus du pan entier) comme en placement libre (photo
 * d'historique puis `hydrateLayout(reste, undefined, 'free')`) : UN pas d'historique, Ctrl + Z
 * rend les panneaux. En emplacements validés la barre ne montre que ce bouton.
 *
 * L'angle de « Pivoter » est un champ texte `step="any"`, jamais borné ni arrondi ; l'éditeur
 * remet les messages de succès (« Aligné — 3 panneaux… ») dans la note du panneau.
 */
import type { LayoutEditor } from './layoutEditor';

export type EditeurBarre = Pick<
  LayoutEditor,
  | 'isFreeMode' | 'selection' | 'freeRotateSelection' | 'freeAlignSelection' | 'freeDistributeSelection'
  | 'removeCells' | 'freePanels' | 'hydrateLayout'
>;

export interface BarreSelectionDeps {
  /** Conteneur de la carte (la barre s'y superpose). */
  hote: () => HTMLElement | null;
  editeur: EditeurBarre;
  setStatus: (msg: string) => void;
  /** ACAL418 — photographie l'atelier AVANT le retrait libre (`ctx.pushWorkshopHistory`). */
  photographier?: () => void;
}

const GARDER_UN = 'Retirer : gardez au moins un panneau.';

/** Lit l'angle saisi : refus nommé si vide ou non numérique ; aucune borne, aucun arrondi. */
export function lireAngle(brut: string): { ok: true; angleDeg: number } | { ok: false; motif: string } {
  const t = brut.trim().replace(',', '.');
  const n = t === '' ? NaN : Number(t);
  if (!Number.isFinite(n)) return { ok: false, motif: 'Pivoter : saisissez un angle en degrés (nombre).' };
  return { ok: true, angleDeg: n };
}

export function creerBarreSelection(deps: BarreSelectionDeps): { rafraichir: () => void } {
  const { editeur, setStatus, photographier } = deps;
  const hote = typeof document !== 'undefined' ? deps.hote() : null;
  if (!hote) return { rafraichir: () => {} };
  const barre = document.createElement('div');
  barre.id = 'rp9-barre-selection';
  barre.setAttribute('role', 'toolbar');
  barre.setAttribute('aria-label', 'Sélection de panneaux');
  barre.style.cssText = 'position:absolute;left:8px;bottom:8px;z-index:7;display:none;gap:6px;align-items:center;flex-wrap:wrap;padding:6px 8px;border-radius:8px;background:rgba(20,20,20,0.85);color:#fff;font-size:12px';
  const libres: HTMLElement[] = []; // boutons propres au placement libre
  const bouton = (libelle: string, agir: (m: number[]) => void, minimum: number, raison: string, libre = true) => {
    const b = document.createElement('button');
    if (libre) libres.push(b);
    b.type = 'button';
    b.textContent = libelle;
    b.addEventListener('click', () => {
      const m = editeur.selection();
      if (m.length < minimum) return setStatus(raison);
      agir(m);
    });
    barre.appendChild(b);
  };
  bouton('Aligner en rangée', (m) => void editeur.freeAlignSelection('row', m), 2, 'Aligner : sélectionnez au moins 2 panneaux.');
  bouton('Aligner en colonne', (m) => void editeur.freeAlignSelection('col', m), 2, 'Aligner : sélectionnez au moins 2 panneaux.');
  bouton('Répartir', (m) => void editeur.freeDistributeSelection(m), 3, 'Répartir : sélectionnez au moins 3 panneaux.');
  const angle = document.createElement('input');
  angle.type = 'text';
  angle.inputMode = 'decimal';
  angle.setAttribute('step', 'any');
  angle.placeholder = 'angle °';
  angle.setAttribute('aria-label', 'Angle de rotation en degrés');
  angle.style.cssText = 'width:64px';
  libres.push(angle);
  barre.appendChild(angle);
  bouton('Pivoter', (m) => {
    const a = lireAngle(angle.value);
    if (!a.ok) return setStatus(a.motif);
    editeur.freeRotateSelection(a.angleDeg, m);
  }, 1, 'Pivoter : sélectionnez au moins 1 panneau.');
  bouton('Retirer la sélection', (m) => {
    if (editeur.isFreeMode()) {
      const poses = editeur.freePanels();
      const reste = poses.filter((_, i) => !m.includes(i));
      if (reste.length === 0) return setStatus(GARDER_UN);
      photographier?.(); // un seul pas d'historique pour tout le geste
      editeur.hydrateLayout(reste, undefined, 'free');
      return setStatus(`${m.length} panneau(x) retiré(s) — Ctrl + Z les rend.`);
    }
    if (editeur.removeCells(m) === 0) return setStatus(GARDER_UN);
    setStatus(`${m.length} panneau(x) retiré(s) — Ctrl + Z les rend.`);
  }, 1, 'Retirer : sélectionnez au moins 1 panneau.', false);
  hote.appendChild(barre);
  return {
    rafraichir: () => {
      const libre = editeur.isFreeMode();
      barre.style.display = editeur.selection().length > 0 ? 'flex' : 'none';
      for (const el of libres) el.style.display = libre ? '' : 'none';
    },
  };
}
